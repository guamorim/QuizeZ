import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from secrets import token_hex
from time import time
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from redis.exceptions import RedisError

from app.ai_questions import QuestionGenerationError, generate_question
from app.game_functions import (
    SOCKET_HEARTBEAT_SECONDS,
    answer_question,
    connect_player,
    create_room,
    disconnect_player,
    finish_generation,
    get_current_player,
    get_session_player,
    join_room,
    leave_room,
    next_room_deadline,
    question_deadline,
    restart_game,
    select_difficulty,
    select_theme,
    serialize_room,
    start_game,
    start_generation,
    update_room_settings,
)
from app.room_store import RoomStore, RoomStoreUnavailable


rooms = RoomStore()
logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app):
    try:
        yield
    finally:
        await rooms.close()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RedisError)
@app.exception_handler(RoomStoreUnavailable)
async def handle_room_store_error(_request, error):
    if isinstance(error, RedisError):
        logger.warning("Redis: falha na requisicao HTTP (%s)", type(error).__name__)
    detail = (
        str(error) if isinstance(error, RoomStoreUnavailable)
        else "O armazenamento das salas esta indisponivel. Tente novamente."
    )
    return JSONResponse(status_code=503, content={"detail": detail})


# Old invite links must be matched before the static file mount.
@app.get("/static/index.html", include_in_schema=False)
def redirect_legacy_invite(room: str | None = None):
    destination = "/"
    if room:
        destination += "?" + urlencode({"room": room})
    return RedirectResponse(destination)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CreateRoomRequest(BaseModel):
    host_name: str


class JoinRoomRequest(BaseModel):
    player_name: str


class PlayerSessionRequest(BaseModel):
    player_id: str
    session_token: str


class SelectThemeRequest(PlayerSessionRequest):
    theme: str


class SelectDifficultyRequest(PlayerSessionRequest):
    difficulty: str


class RegenerateQuestionRequest(PlayerSessionRequest):
    question_id: str


class AnswerQuestionRequest(PlayerSessionRequest):
    answer: str
    question_id: str


class RemovePlayerRequest(PlayerSessionRequest):
    target_player_id: str


class UpdateRoomSettingsRequest(PlayerSessionRequest):
    points_to_win: int
    question_time_limit: int


def require_room_session(room, payload: PlayerSessionRequest):
    if room is None:
        raise HTTPException(status_code=404, detail="Sala nao encontrada")
    player = get_session_player(room, payload.player_id, payload.session_token)
    if player is None:
        raise HTTPException(status_code=403, detail="Sessao do jogador invalida")
    return player


def session_response(room, player_id):
    return {
        "room": serialize_room(room),
        "player_id": player_id,
        "session_token": room["player_tokens"][player_id],
    }


async def apply_player_action(room_code, payload, action, error, status_code=400):
    def change(room, _now):
        player = require_room_session(room, payload)
        if action(room, player["id"]) is None:
            raise HTTPException(status_code=status_code, detail=error)

    room, _ = await rooms.update(room_code, change)
    return serialize_room(room)


async def generate_for_room(room_code, room, generation_id, *, previous_question=None):
    question = None
    try:
        question = await asyncio.to_thread(
            generate_question,
            room["selected_theme"],
            room["selected_difficulty"],
            room["asked_questions"],
            different_from=previous_question,
        )
    except QuestionGenerationError:
        pass
    finally:
        # The saved generation ID prevents a late result from replacing another turn.
        room, applied = await rooms.update(
            room_code, lambda state, now: finish_generation(state, generation_id, question, now)
        )

    if not applied:
        raise HTTPException(status_code=409, detail="A geracao ja expirou ou o turno mudou")
    if previous_question is not None and question is None:
        raise HTTPException(
            status_code=503,
            detail="Nao foi possivel gerar outra pergunta. O tempo da anterior foi retomado.",
        )
    return serialize_room(room)


@app.get("/", include_in_schema=False)
def home():
    index = STATIC_DIR / "react" / "index.html"
    if not index.is_file():
        return PlainTextResponse(
            "O Arcade ainda nao foi compilado. Na raiz do projeto, execute:\n\n"
            "Windows (PowerShell):\n"
            "npm.cmd --prefix frontend ci\n"
            "npm.cmd --prefix frontend run build\n\n"
            "Linux ou macOS:\n"
            "npm --prefix frontend ci\n"
            "npm --prefix frontend run build\n\n"
            "Depois, recarregue a pagina.",
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health():
    rooms.check_config()
    return {
        "message": "Servidor do quizeZ rodando",
        "room_store": "redis" if rooms.redis is not None else "memory",
    }


@app.get("/rooms/{room_code}")
async def read_room(room_code: str):
    room, _ = await rooms.update(room_code)
    if room is None:
        raise HTTPException(status_code=404, detail="Sala nao encontrada")
    return serialize_room(room)


@app.post("/rooms")
async def create_new_room(payload: CreateRoomRequest):
    for _ in range(8):
        room, host_id = create_room(payload.host_name)
        if room is None:
            raise HTTPException(status_code=400, detail="Nome do host invalido")
        if await rooms.create(room):
            return session_response(room, host_id)
    raise HTTPException(status_code=503, detail="Nao foi possivel reservar um codigo de sala")


@app.post("/rooms/{room_code}/join")
async def join_existing_room(room_code: str, payload: JoinRoomRequest):
    def join(room, _now):
        _, player_id = join_room(room, payload.player_name)
        if player_id is None:
            raise HTTPException(status_code=400, detail="Sala nao encontrada ou nome invalido/repetido")
        return player_id

    room, player_id = await rooms.update(room_code, join)
    return session_response(room, player_id)


@app.post("/rooms/{room_code}/start")
async def start_existing_game(room_code: str, payload: PlayerSessionRequest):
    return await apply_player_action(
        room_code, payload, start_game, "Apenas o host pode iniciar a partida no lobby", 403
    )


@app.post("/rooms/{room_code}/theme")
async def select_room_theme(room_code: str, payload: SelectThemeRequest):
    return await apply_player_action(
        room_code, payload, lambda room, player_id: select_theme(room, player_id, payload.theme),
        "Nao foi possivel escolher esse tema",
    )


@app.post("/rooms/{room_code}/difficulty")
async def select_room_difficulty(room_code: str, payload: SelectDifficultyRequest):
    def begin(room, now):
        player = require_room_session(room, payload)
        if select_difficulty(room, player["id"], payload.difficulty) is None:
            raise HTTPException(status_code=400, detail="Nao foi possivel escolher essa dificuldade")
        return start_generation(room, now)

    room, generation_id = await rooms.update(room_code, begin)
    return await generate_for_room(room_code, room, generation_id)


@app.post("/rooms/{room_code}/answer")
async def answer_room_question(room_code: str, payload: AnswerQuestionRequest):
    return await apply_player_action(
        room_code, payload,
        lambda room, player_id: answer_question(room, player_id, payload.answer, payload.question_id),
        "Nao foi possivel responder essa pergunta",
    )


@app.post("/rooms/{room_code}/regenerate")
async def regenerate_room_question(room_code: str, payload: RegenerateQuestionRequest):
    def begin(room, now):
        player = require_room_session(room, payload)
        question = room["current_question"]
        if room["status"] != "playing" or question is None or question["id"] != payload.question_id:
            raise HTTPException(status_code=409, detail="A pergunta ja mudou")
        if get_current_player(room) is not player:
            raise HTTPException(status_code=403, detail="Apenas o jogador da vez pode trocar a pergunta")
        if question.get("regenerated") or question.get("regenerating"):
            raise HTTPException(status_code=409, detail="Cada pergunta pode ser trocada uma vez")
        remaining_time = question_deadline(question) - now
        if remaining_time <= 0:
            raise HTTPException(status_code=409, detail="O tempo desta pergunta ja acabou")

        question["regenerating"] = True
        return start_generation(room, now, remaining_time=remaining_time)

    room, generation_id = await rooms.update(room_code, begin)
    return await generate_for_room(
        room_code, room, generation_id, previous_question=room["current_question"]["question"]
    )


async def wait_for_disconnect(websocket):
    while (await websocket.receive())["type"] != "websocket.disconnect":
        pass


async def wait_for_room_update(wait_for_change, disconnect, timeout):
    change = asyncio.create_task(wait_for_change(timeout))
    try:
        await asyncio.wait((change, disconnect), return_when=asyncio.FIRST_COMPLETED)
        if disconnect.done():
            await disconnect
            return False
        await change
        return True
    finally:
        change.cancel()
        await asyncio.gather(change, return_exceptions=True)


@app.websocket("/ws/{room_code}")
async def room_websocket(websocket: WebSocket, room_code: str):
    await websocket.accept()
    room_code = room_code.upper()
    try:
        credentials = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        payload = PlayerSessionRequest(**credentials)
    except (TimeoutError, ValueError, TypeError, KeyError):
        await websocket.close(code=4403)
        return
    except (WebSocketDisconnect, OSError, RuntimeError):
        return

    player_id = payload.player_id
    connection_id = token_hex(12)
    disconnect = None
    registered = False

    def session_player(room):
        return get_session_player(room, player_id, payload.session_token) if room else None

    def renew(room, now):
        player = session_player(room)
        if player is not None:
            connect_player(room, player, connection_id, now)
        return player is not None

    def release(room, now):
        if room is not None:
            disconnect_player(room, player_id, connection_id, now)

    try:
        room, _ = await rooms.update(room_code)
        if room is None or session_player(room) is None:
            await websocket.close(code=4404 if room is None else 4403)
            return

        async with rooms.subscribe(room_code) as wait_for_change:
            room, registered = await rooms.update(room_code, renew)
            disconnect = asyncio.create_task(wait_for_disconnect(websocket))
            last_message = None
            renew_at = time() + SOCKET_HEARTBEAT_SECONDS
            while True:
                if room is None or session_player(room) is None:
                    await websocket.close(code=4404 if room is None else 4403)
                    return
                message = json.dumps({"type": "room_updated", "room": serialize_room(room)})
                if message != last_message:
                    await websocket.send_text(message)
                    last_message = message

                timeout = max(0, min(renew_at, next_room_deadline(room)) - time())
                if not await wait_for_room_update(wait_for_change, disconnect, timeout):
                    return
                if time() >= renew_at:
                    room, _ = await rooms.update(room_code, renew)
                    renew_at = time() + SOCKET_HEARTBEAT_SECONDS
                else:
                    room, _ = await rooms.update(room_code)
    except (RedisError, RoomStoreUnavailable) as error:
        logger.warning("Armazenamento da sala: falha no WebSocket (%s)", type(error).__name__)
        with suppress(WebSocketDisconnect, OSError, RuntimeError):
            await websocket.close(code=1013)
    except (WebSocketDisconnect, OSError, RuntimeError):
        pass
    finally:
        if disconnect is not None:
            disconnect.cancel()
            await asyncio.gather(disconnect, return_exceptions=True)
        if registered:
            with suppress(RedisError, RoomStoreUnavailable):
                await rooms.update(room_code, release)


@app.post("/rooms/{room_code}/leave")
async def leave_existing_room(room_code: str, payload: PlayerSessionRequest):
    def remove(room, _now):
        if room is not None and payload.player_id in room["player_tokens"]:
            player = require_room_session(room, payload)
            leave_room(room, player["id"])

    room, _ = await rooms.update(room_code, remove)
    return {"room": serialize_room(room)}


@app.post("/rooms/{room_code}/kick")
async def kick_room_player(room_code: str, payload: RemovePlayerRequest):
    def kick(room, _now):
        host = require_room_session(room, payload)
        if not host["is_host"]:
            raise HTTPException(status_code=403, detail="Apenas o host pode remover jogadores")
        if payload.target_player_id == host["id"]:
            raise HTTPException(status_code=400, detail="Use Sair da sala para remover seu jogador")
        if leave_room(room, payload.target_player_id) is None:
            raise HTTPException(status_code=404, detail="Jogador nao encontrado")

    room, _ = await rooms.update(room_code, kick)
    return serialize_room(room)


@app.post("/rooms/{room_code}/restart")
async def restart_existing_game(room_code: str, payload: PlayerSessionRequest):
    return await apply_player_action(
        room_code, payload, restart_game, "Apenas o host pode reiniciar uma partida encerrada", 403
    )


@app.post("/rooms/{room_code}/settings")
async def update_existing_room_settings(room_code: str, payload: UpdateRoomSettingsRequest):
    return await apply_player_action(
        room_code, payload,
        lambda room, player_id: update_room_settings(
            room, player_id, payload.points_to_win, payload.question_time_limit
        ),
        "Nao foi possivel atualizar as configuracoes",
    )
