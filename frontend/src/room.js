import { useCallback, useEffect, useState } from "react";

const sessionKeys = {
  code: "quizez_room_code",
  playerId: "quizez_player_id",
  token: "quizez_session_token",
};

function readSession() {
  const session = Object.fromEntries(
    Object.entries(sessionKeys).map(([field, key]) => [field, localStorage.getItem(key)]),
  );
  return session.code && session.playerId && session.token ? session : null;
}

function storeSession(session) {
  for (const [field, key] of Object.entries(sessionKeys)) {
    if (session) {
      localStorage.setItem(key, session[field]);
    } else {
      localStorage.removeItem(key);
    }
  }
}

export async function postRoom(path, body, fallback) {
  let response;
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Não foi possível conectar ao servidor.");
  }

  const data = await response.json().catch(() => null);
  if (!response.ok || !data) {
    throw new Error(typeof data?.detail === "string" ? data.detail : fallback);
  }
  return data;
}

export function postRoomAction(session, action, fields, fallback) {
  return postRoom(
    "/rooms/" + encodeURIComponent(session.code) + "/" + action,
    { ...fields, player_id: session.playerId, session_token: session.token },
    fallback,
  );
}

export function useRoom() {
  const [session, setSession] = useState(readSession);
  const [room, setRoom] = useState(null);
  const [notice, setNotice] = useState(session ? "Conectando à sala…" : "");

  const activateSession = useCallback((next, snapshot = null, message = "") => {
    storeSession(next);
    setSession(next);
    setRoom(snapshot);
    setNotice(next ? "Conectando à sala…" : message);
  }, []);

  useEffect(() => {
    if (!session) return;

    let socket;
    let retryTimer;
    let syncTimer;
    let disposed = false;
    let retryDelay = 1000;

    function connect() {
      const url = new URL("/ws/" + encodeURIComponent(session.code), window.location.href);
      url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const connection = new WebSocket(url);
      socket = connection;
      const active = () => !disposed && socket === connection;

      syncTimer = window.setTimeout(() => {
        if (active()) connection.close();
      }, 10000);

      connection.addEventListener("open", () => {
        if (active()) {
          connection.send(JSON.stringify({ player_id: session.playerId, session_token: session.token }));
        }
      });

      connection.addEventListener("message", (event) => {
        if (!active()) return;
        const message = JSON.parse(event.data);
        if (message.type === "room_closed") {
          activateSession(null, null, "A sala foi encerrada.");
          return;
        }
        if (message.type !== "room_updated") return;
        if (!message.room.players.some((player) => player.id === session.playerId)) {
          activateSession(null, null, "Você não faz mais parte desta sala.");
          return;
        }

        window.clearTimeout(syncTimer);
        retryDelay = 1000;
        setNotice("");
        setRoom(message.room);
      });

      connection.addEventListener("close", ({ code }) => {
        if (!active()) return;
        window.clearTimeout(syncTimer);
        if (code === 4403 || code === 4404) {
          const message = code === 4404 ? "A sala foi encerrada." : "Você não faz mais parte desta sala.";
          activateSession(null, null, message);
          return;
        }

        setNotice("Reconectando…");
        retryTimer = window.setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 10000);
      });
    }

    connect();
    return () => {
      disposed = true;
      window.clearTimeout(retryTimer);
      window.clearTimeout(syncTimer);
      socket?.close();
    };
  }, [session, activateSession]);

  return { session, room, notice, activateSession };
}
