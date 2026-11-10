import asyncio
import json
import os
from contextlib import asynccontextmanager
from time import time

from redis.asyncio import Redis

from app.game_functions import reconcile_room, serialize_room


ROOM_TTL_SECONDS = 6 * 60 * 60

# Save the state and notify listeners in the same atomic Redis operation.
REPLACE_ROOM = """
local current = redis.call('GET', KEYS[1])
if (current or '') ~= ARGV[1] then return 0 end
if ARGV[2] == '' then
    redis.call('DEL', KEYS[1])
else
    redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
end
if ARGV[4] == '1' then redis.call('PUBLISH', KEYS[2], 'changed') end
return 1
"""


class RoomStoreUnavailable(Exception):
    pass


def encode(room):
    return json.dumps(room, ensure_ascii=False, separators=(",", ":")) if room is not None else None


class RoomStore:
    def __init__(self):
        environment = os.getenv("VERCEL_ENV") or "local"
        self.prefix = os.getenv("ROOM_STORE_PREFIX") or f"quizez:{environment}"
        url = os.getenv("REDIS_URL") or os.getenv("KV_URL")
        try:
            self.redis = Redis.from_url(
                url, decode_responses=True, socket_connect_timeout=5, socket_timeout=15
            ) if url else None
        except ValueError:
            raise RoomStoreUnavailable("Use a URL TCP do Redis em REDIS_URL, nao a URL REST.") from None
        self.redis_required = environment in ("production", "preview")
        self.memory = {}
        self.listeners = {}

    def room_key(self, code):
        return f"{self.prefix}:room:{{{code}}}"

    def change_channel(self, code):
        return self.room_key(code) + ":changes"

    def check_config(self):
        if self.redis_required and self.redis is None:
            raise RoomStoreUnavailable("Configure REDIS_URL para o ambiente da Vercel.")

    async def close(self):
        if self.redis is not None:
            await self.redis.aclose()

    async def create(self, room):
        self.check_config()
        code = room["code"]
        snapshot = encode(room)
        if self.redis is not None:
            return bool(await self.redis.set(self.room_key(code), snapshot, nx=True, ex=ROOM_TTL_SECONDS))
        if code in self.memory:
            return False
        self.memory[code] = snapshot
        return True

    async def replace(self, code, before, after, notify):
        if self.redis is not None:
            return bool(await self.redis.eval(
                REPLACE_ROOM, 2, self.room_key(code), self.change_channel(code),
                before, after or "", ROOM_TTL_SECONDS, "1" if notify else "0",
            ))
        if after is None:
            self.memory.pop(code, None)
        else:
            self.memory[code] = after
        if notify:
            for event in self.listeners.get(code, ()):
                event.set()
        return True

    async def update(self, code, change=None):
        self.check_config()
        code = code.upper()
        for attempt in range(10):
            before = (
                await self.redis.get(self.room_key(code))
                if self.redis is not None else self.memory.get(code)
            )
            room = json.loads(before) if before is not None else None
            previous_view = encode(serialize_room(room))
            now = time()
            if room is not None:
                reconcile_room(room, now)
            # The callback can be retried after a conflict. Keep side effects outside it.
            result = change(room, now) if change is not None else None
            if room is not None and not room["players"]:
                room = None
            after = encode(room)
            if before == after:
                return room, result
            notify = previous_view != encode(serialize_room(room))
            if await self.replace(code, before, after, notify):
                return room, result
            await asyncio.sleep(0.005 * (attempt + 1))
        raise RoomStoreUnavailable("A sala recebeu muitas acoes simultaneas. Tente novamente.")

    @asynccontextmanager
    async def subscribe(self, code):
        self.check_config()
        if self.redis is not None:
            async with self.redis.pubsub() as subscription:
                await subscription.subscribe(self.change_channel(code))
                ready = await subscription.get_message(timeout=5)
                if ready is None or ready["type"] != "subscribe":
                    raise RoomStoreUnavailable("Nao foi possivel assinar as atualizacoes da sala.")

                async def wait(timeout):
                    await subscription.get_message(ignore_subscribe_messages=True, timeout=timeout)

                yield wait
            return

        event = asyncio.Event()
        listeners = self.listeners.setdefault(code, set())
        listeners.add(event)

        async def wait(timeout):
            if timeout > 0 and not event.is_set():
                try:
                    await asyncio.wait_for(event.wait(), timeout)
                except TimeoutError:
                    pass
            event.clear()

        try:
            yield wait
        finally:
            listeners.discard(event)
            if not listeners:
                self.listeners.pop(code, None)
