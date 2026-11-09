import json
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from app.ai_questions import generate_question
from app.game_functions import (
    answer_question,
    create_room,
    get_current_player,
    get_room,
    get_session_player,
    join_room,
    leave_room,
    next_turn,
    restart_game,
    select_difficulty,
    select_theme,
    serialize_room,
    set_current_question,
    start_game,
    timeout_question,
    update_room_settings,
)

app = FastAPI()
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
websocket_connections = {}
QUESTION_TIME_LIMIT = 30
DISCONNECT_GRACE_PERIOD = 10
question_timeout_tasks = {}
disconnect_tasks = {}

def room_update_message(room):
    if room is None:
        return json.dumps({"type": "room_closed"})
    return json.dumps({"type": "room_updated", "room": serialize_room(room)})

async def broadcast_room(room_code):
    connections = websocket_connections.get(room_code.upper(), {})
    sockets = [socket for player_sockets in connections.values() for socket in player_sockets]
    if not sockets:
        return

    message = room_update_message(get_room(room_code))

    for websocket in sockets:
        try:
            await websocket.send_text(message)
        except (WebSocketDisconnect, OSError, RuntimeError):
            continue

async def expire_question_later(room_code, question_id, time_limit):
    await asyncio.sleep(time_limit)

    room = timeout_question(room_code, question_id)

    if room is not None:
        await broadcast_room(room_code)

def schedule_question_timeout(room_code, question_id, time_limit=None):
    old_task = question_timeout_tasks.get(room_code.upper())

    if old_task is not None:
        old_task.cancel()

    room = get_room(room_code)
    if time_limit is None:
        time_limit = room.get("question_time_limit", QUESTION_TIME_LIMIT) if room else QUESTION_TIME_LIMIT

    if room is not None and room["current_question"] is not None:
        room["current_question"]["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=time_limit)
        ).isoformat()

    question_timeout_tasks[room_code.upper()] = asyncio.create_task(
        expire_question_later(room_code, question_id, time_limit)
    )
    
def cancel_question_timeout(room_code):
    task = question_timeout_tasks.pop(room_code.upper(), None)

    if task is not None:
        task.cancel()


def cancel_disconnect_timeout(room_code, player_id):
    task = disconnect_tasks.pop((room_code, player_id), None)
    if task is not None:
        task.cancel()


async def expire_disconnected_player(room_code, room, player):
    await asyncio.sleep(DISCONNECT_GRACE_PERIOD)
    player_id = player["id"]
    disconnect_tasks.pop((room_code, player_id), None)

    if get_room(room_code) is not room or player_id not in room["player_tokens"]:
        return
    if player["connection_status"] != "reconnecting":
        return

    player["connection_status"] = "offline"
    if room["status"] == "playing" and get_current_player(room) is player:
        next_turn(room_code)
        cancel_question_timeout(room_code)

    await broadcast_room(room_code)


async def remove_player_from_room(room_code, player_id):
    room_code = room_code.upper()
    room = leave_room(room_code, player_id)
    cancel_disconnect_timeout(room_code, player_id)
    if room is None or room["current_question"] is None:
        cancel_question_timeout(room_code)

    connections = websocket_connections.get(room_code, {})
    for websocket in tuple(connections.get(player_id, ())):
        try:
            await websocket.close(code=4403)
        except (WebSocketDisconnect, OSError, RuntimeError):
            continue

    await broadcast_room(room_code)
    return room
        
# Old invite links must be matched before the static file mount.
@app.get("/static/index.html", include_in_schema=False)
def redirect_legacy_invite(room: str | None = None):
    destination = "/"
    if room:
        destination += "?" + urlencode({"room": room})
    return RedirectResponse(destination)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CreateRoomRequest(BaseModel):
    host_name: str

class JoinRoomRequest(BaseModel):
    player_name: str

class StartGameRequest(BaseModel):
    player_id: str

class SelectThemeRequest(BaseModel):
    player_id: str
    theme: str

class SelectDifficultyRequest(BaseModel):
    player_id: str
    difficulty: str

class RegenerateQuestionRequest(BaseModel):
    player_id: str
    question_id: str

class AnswerQuestionRequest(BaseModel):
    player_id: str
    answer: str
    question_id: str | None = None

class PlayerSessionRequest(BaseModel):
    player_id: str
    session_token: str

class RemovePlayerRequest(PlayerSessionRequest):
    target_player_id: str

class UpdateRoomSettingsRequest(BaseModel):
    player_id: str
    points_to_win: int
    question_time_limit: int

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
    return {"message": "Servidor do quizeZ rodando"}




@app.get("/rooms/{room_code}")
def read_room(room_code: str):
    room = get_room(room_code)

    if room is None:
        raise HTTPException(status_code=404, detail="Sala nao encontrada")

    return serialize_room(room)

@app.post("/rooms")
async def create_new_room(payload: CreateRoomRequest):
    room, host_id = create_room(payload.host_name)

    if room is None:
        raise HTTPException(status_code=400, detail="Nome do host invalido")

    session_token = room["player_tokens"][host_id]
    await broadcast_room(room["code"])

    return {
        "room": serialize_room(room),
        "player_id": host_id,
        "session_token": session_token,
    }

@app.post("/rooms/{room_code}/join")
async def join_existing_room(room_code: str, payload: JoinRoomRequest):
    room, player_id = join_room(room_code, payload.player_name)

    if room is None:
        raise HTTPException(status_code=400, detail="Sala nao encontrada ou nome invalido/repetido")

    session_token = room["player_tokens"][player_id]
    
    await broadcast_room(room_code)

    return {
        "room": serialize_room(room),
        "player_id": player_id,
        "session_token": session_token,
    }

@app.post("/rooms/{room_code}/start")
async def start_existing_game(room_code: str, payload: StartGameRequest):
    room = start_game(room_code, payload.player_id)

    if room is None:
        raise HTTPException(status_code=403, detail="Apenas o host pode iniciar a partida")
    
    await broadcast_room(room_code)

    return serialize_room(room)

@app.post("/rooms/{room_code}/theme")
async def select_room_theme(room_code: str, payload: SelectThemeRequest):
    room = select_theme(room_code, payload.player_id, payload.theme)

    if room is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel escolher esse tema")
    
    await broadcast_room(room_code)

    return serialize_room(room)

@app.post("/rooms/{room_code}/difficulty")
async def select_room_difficulty(room_code: str, payload: SelectDifficultyRequest):
    room = await select_difficulty(room_code, payload.player_id, payload.difficulty)

    if room is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel escolher essa dificuldade")
    
    schedule_question_timeout(room_code, room["current_question"]["id"])
    
    await broadcast_room(room_code)

    return serialize_room(room)

@app.post("/rooms/{room_code}/answer")
async def answer_room_question(room_code: str, payload: AnswerQuestionRequest):
    room = answer_question(room_code, payload.player_id, payload.answer, payload.question_id)

    if room is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel responder essa pergunta")

    cancel_question_timeout(room_code)

    await broadcast_room(room_code)

    return serialize_room(room)

@app.post("/rooms/{room_code}/regenerate")
async def regenerate_room_question(room_code: str, payload: RegenerateQuestionRequest):
    room = get_room(room_code)
    if room is None:
        raise HTTPException(status_code=404, detail="Sala nao encontrada")

    question = room["current_question"]
    if room["status"] != "playing" or question is None or question["id"] != payload.question_id:
        raise HTTPException(status_code=409, detail="A pergunta ja mudou")

    current_player = get_current_player(room)
    if current_player is None or current_player["id"] != payload.player_id:
        raise HTTPException(status_code=403, detail="Apenas o jogador da vez pode trocar a pergunta")

    if question.get("regenerated") or question.get("regenerating"):
        raise HTTPException(status_code=409, detail="Cada pergunta pode ser trocada uma vez")

    deadline = datetime.fromisoformat(question["expires_at"])
    remaining_time = (deadline - datetime.now(timezone.utc)).total_seconds()
    if remaining_time <= 0:
        raise HTTPException(status_code=409, detail="O tempo desta pergunta ja acabou")

    question["regenerating"] = True
    cancel_question_timeout(room_code)
    replacement = None

    try:
        await broadcast_room(room_code)
        replacement = await asyncio.to_thread(
            generate_question,
            question["theme"],
            question["difficulty"],
            room["asked_questions"].copy(),
            different_from=question["question"],
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail="Nao foi possivel gerar outra pergunta. O tempo da anterior foi retomado.",
        ) from error
    finally:
        # A room or turn can change while the model is generating.
        still_current = get_room(room_code) is room and room["current_question"] is question
        if still_current:
            question.pop("regenerating", None)
            if replacement is None:
                schedule_question_timeout(room_code, question["id"], remaining_time)
            else:
                set_current_question(room, replacement, regenerated=True)
                schedule_question_timeout(room_code, replacement["id"])
            await broadcast_room(room_code)

    if not still_current:
        raise HTTPException(status_code=409, detail="A pergunta ja mudou")

    return serialize_room(room)

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

    room = get_room(room_code)
    if room is None:
        await websocket.close(code=4404)
        return

    player_id = payload.player_id
    player = get_session_player(room, player_id, payload.session_token)
    if player is None:
        await websocket.close(code=4403)
        return

    connections = websocket_connections.setdefault(room_code, {})
    player_sockets = connections.setdefault(player_id, [])
    player_sockets.append(websocket)
    was_online = player["connection_status"] == "online"
    player["connection_status"] = "online"
    cancel_disconnect_timeout(room_code, player_id)
    if room["status"] == "playing" and get_current_player(room) is None:
        next_turn(room_code)

    try:
        if was_online:
            await websocket.send_text(room_update_message(room))
        else:
            await broadcast_room(room_code)
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, OSError, RuntimeError):
        pass
    finally:
        player_sockets.remove(websocket)
        if not player_sockets:
            del connections[player_id]
            if not connections:
                del websocket_connections[room_code]

            if get_room(room_code) is room and player_id in room["player_tokens"]:
                player["connection_status"] = "reconnecting"
                disconnect_tasks[(room_code, player_id)] = asyncio.create_task(
                    expire_disconnected_player(room_code, room, player)
                )
                await broadcast_room(room_code)

@app.post("/rooms/{room_code}/leave")
async def leave_existing_room(room_code: str, payload: PlayerSessionRequest):
    room = get_room(room_code)
    if room is None or payload.player_id not in room["player_tokens"]:
        return {"room": None}
    if get_session_player(room, payload.player_id, payload.session_token) is None:
        raise HTTPException(status_code=403, detail="Sessao do jogador invalida")

    room = await remove_player_from_room(room_code, payload.player_id)
    return {"room": serialize_room(room)}

@app.post("/rooms/{room_code}/kick")
async def kick_room_player(room_code: str, payload: RemovePlayerRequest):
    room = get_room(room_code)
    if room is None:
        raise HTTPException(status_code=404, detail="Sala nao encontrada")
    host = get_session_player(room, payload.player_id, payload.session_token)
    if host is None or not host["is_host"]:
        raise HTTPException(status_code=403, detail="Apenas o host pode remover jogadores")
    if payload.target_player_id == payload.player_id:
        raise HTTPException(status_code=400, detail="Use Sair da sala para remover seu jogador")
    if payload.target_player_id not in room["player_tokens"]:
        raise HTTPException(status_code=404, detail="Jogador nao encontrado")

    room = await remove_player_from_room(room_code, payload.target_player_id)
    return serialize_room(room)

@app.post("/rooms/{room_code}/restart")
async def restart_existing_game(room_code: str, payload: StartGameRequest):
    room = restart_game(room_code, payload.player_id)

    if room is None:
        raise HTTPException(status_code=403, detail="Apenas o host pode reiniciar a partida")

    cancel_question_timeout(room_code)
    
    await broadcast_room(room_code)

    return serialize_room(room)

@app.post("/rooms/{room_code}/settings")
async def update_existing_room_settings(room_code: str, payload: UpdateRoomSettingsRequest):
    room = update_room_settings(
        room_code,
        payload.player_id,
        payload.points_to_win,
        payload.question_time_limit,
)

    if room is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel atualizar as configuracoes")

    await broadcast_room(room_code)

    return serialize_room(room)
