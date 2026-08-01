import json
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
import asyncio
from datetime import datetime, timedelta, timezone

from app.game_functions import update_room_settings,restart_game,timeout_question, answer_question, leave_room, create_room, get_room, join_room, select_difficulty, select_theme, serialize_room, start_game

app = FastAPI()
websocket_connections = {}
QUESTION_TIME_LIMIT = 30
question_timeout_tasks = {}
async def broadcast_room(room_code):
    room = get_room(room_code)

    if room is None:
        return

    message = json.dumps(
        {
            "type": "room_updated",
            "room": serialize_room(room),
        }
    )

    connections = websocket_connections.get(room_code.upper(), [])

    for websocket in connections:
        await websocket.send_text(message)

async def expire_question_later(room_code, question_id, time_limit):
    await asyncio.sleep(time_limit)

    room = timeout_question(room_code, question_id)

    if room is not None:
        await broadcast_room(room_code)

def schedule_question_timeout(room_code, question_id):
    old_task = question_timeout_tasks.get(room_code.upper())

    if old_task is not None:
        old_task.cancel()

    room = get_room(room_code)
    time_limit = QUESTION_TIME_LIMIT

    if room is not None:
        time_limit = room.get("question_time_limit", QUESTION_TIME_LIMIT)

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
        
app.mount("/static", StaticFiles(directory="static"), name="static")


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

class AnswerQuestionRequest(BaseModel):
    player_id: str
    answer: str

class LeaveRoomRequest(BaseModel):
    player_id: str

class UpdateRoomSettingsRequest(BaseModel):
    player_id: str
    points_to_win: int
    question_time_limit: int

@app.get("/")
def home():
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

    await broadcast_room(room["code"])

    return {
        "room": serialize_room(room),
        "player_id": host_id,
    }

@app.post("/rooms/{room_code}/join")
async def join_existing_room(room_code: str, payload: JoinRoomRequest):
    room, player_id = join_room(room_code, payload.player_name)

    if room is None:
        raise HTTPException(status_code=400, detail="Sala nao encontrada ou nome invalido/repetido")
    
    await broadcast_room(room_code)

    return {
        "room": serialize_room(room),
        "player_id": player_id,
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
    room = select_difficulty(room_code, payload.player_id, payload.difficulty)

    if room is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel escolher essa dificuldade")
    
    schedule_question_timeout(room_code, room["current_question"]["id"])
    
    await broadcast_room(room_code)

    return serialize_room(room)

@app.post("/rooms/{room_code}/answer")
async def answer_room_question(room_code: str, payload: AnswerQuestionRequest):
    room = answer_question(room_code, payload.player_id, payload.answer)

    if room is None:
        raise HTTPException(status_code=400, detail="Nao foi possivel responder essa pergunta")

    cancel_question_timeout(room_code)

    await broadcast_room(room_code)

    return serialize_room(room)

@app.websocket("/ws/{room_code}")
async def room_websocket(websocket: WebSocket, room_code: str):

    await websocket.accept()

    room_code = room_code.upper()

    if room_code not in websocket_connections:
        websocket_connections[room_code] = []

    websocket_connections[room_code].append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_connections[room_code].remove(websocket)

@app.post("/rooms/{room_code}/leave")
async def leave_existing_room(room_code: str, payload: LeaveRoomRequest):
    cancel_question_timeout(room_code)
    room = leave_room(room_code, payload.player_id)

    if room is not None:
        if room["current_question"] is not None:
            schedule_question_timeout(room_code, room["current_question"]["id"])

        await broadcast_room(room_code)
        return {"room": serialize_room(room)}
    return {"room": None}

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