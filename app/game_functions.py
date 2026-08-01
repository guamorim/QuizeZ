from random import randrange, sample
from secrets import token_hex
from app.ai_questions import generate_question

rooms = {}
THEMES_POOL = [
    "Historia",
    "Geografia",
    "Ciencia",
    "Tecnologia",
    "Esportes",
    "Cinema",
    "Musica",
    "Literatura",
    "Matematica",
    "Games",
    "Mitologia",
    "Arte",
    "Biologia",
    "Fisica",
    "Quimica",
    "Astronomia",
    "Politica",
    "Cultura pop",
    "Comida",
    "Series",
    "Animes",
    "Brasil",
    "Mundo",
    "Logica",
]

POINTS_BY_DIFFICULTY = {
    "facil": 1,
    "medio": 2,
    "dificil": 3,
}

POINTS_TO_WIN = 25
DEFAULT_QUESTION_TIME_LIMIT = 30

def generate_room_code():
    return token_hex(3).upper()


def create_room(host_name):
    host_name = normalize_player_name(host_name)

    if not host_name:
        return None, None
    
    room_code = generate_room_code()
    host_id = token_hex(8)

    rooms[room_code] = {
        "code": room_code,
        "host_id": host_id, 
        "status": "waiting",
        "players": [
            {
                "id": host_id,
                "name": host_name,
                "score": 0,
                "is_host": True,
            }
        ],
        "current_player_index": 0,
        "available_themes": [],
        "selected_theme": None,
        "selected_difficulty": None,
        "current_question": None,
        "last_answer_result": None,
        "winner": None,
        "asked_questions": [],
        "points_to_win": POINTS_TO_WIN,
        "question_time_limit": DEFAULT_QUESTION_TIME_LIMIT,
    
    }

    return rooms[room_code], host_id

def get_room(room_code):
    return rooms.get(room_code.upper())


def join_room(room_code, player_name):
    room = get_room(room_code)

    if room is None:
        return None, None

    player_name = normalize_player_name(player_name)

    if not player_name:
        return None, None
    
    for player in room["players"]:
        if player["name"].lower() == player_name.lower():
            return None, None
        
    player_id = token_hex(8)

    room["players"].append(
        {
            "id": player_id,
            "name": player_name,
            "score": 0,
            "is_host": False,
        }
    )

    return room, player_id

def choose_themes(amount=5):
    return sample(THEMES_POOL, amount)


def start_game(room_code, player_id):
    room = get_room(room_code)

    if room is None:
        return None

    if room["host_id"] != player_id:
        return None

    room["status"] = "playing"
    room["current_player_index"] = randrange(len(room["players"]))
    room["available_themes"] = choose_themes()
    room["selected_theme"] = None
    room["selected_difficulty"] = None
    room["current_question"] = None
    room["winner"] = None
    room["last_answer_result"] = None

    return room

def get_current_player(room):
    if not room["players"]:
        return None

    return room["players"][room["current_player_index"]]

def serialize_room(room):
    if room is None:
        return None

    room_data = room.copy()
    room_data.pop("asked_questions", None)
    room_data["current_player"] = get_current_player(room)

    if room_data["current_question"] is not None:
        question_data = room_data["current_question"].copy()
        question_data.pop("correct_answer", None)
        room_data["current_question"] = question_data

    return room_data

def select_theme(room_code, player_id, theme):
    room = get_room(room_code)

    if room is None:
        return None

    if room["status"] != "playing":
        return None

    current_player = get_current_player(room)

    if current_player is None:
        return None

    if current_player["id"] != player_id:
        return None

    if theme not in room["available_themes"]:
        return None

    room["selected_theme"] = theme
    room["current_question"] = None

    return room


def select_difficulty(room_code, player_id, difficulty):

    room = get_room(room_code)

    if room is None:
        return None

    if room["status"] != "playing":
        return None

    current_player = get_current_player(room)

    if current_player is None:
        return None

    if current_player["id"] != player_id:
        return None

    if room["selected_theme"] is None:
        return None
    
    if room["current_question"] is not None:
        return None

    if difficulty not in ["facil", "medio", "dificil"]:
        return None

    room["selected_difficulty"] = difficulty
    question = generate_question(
    room["selected_theme"],
    difficulty,
    room["asked_questions"],
)
    question["id"] = token_hex(8)

    room["selected_difficulty"] = difficulty
    room["current_question"] = question
    room["asked_questions"].append(question["question"])

    return room

def next_turn(room_code):
    room = get_room(room_code)

    if room is None:
        return None

    room["current_player_index"] += 1
    room["current_player_index"] %= len(room["players"])

    room["available_themes"] = choose_themes()
    room["selected_theme"] = None
    room["selected_difficulty"] = None
    room["current_question"] = None

    return room


def answer_question(room_code, player_id, answer):
    room = get_room(room_code)

    if room is None:
        return None

    if room["status"] != "playing":
        return None

    current_player = get_current_player(room)

    if current_player is None:
        return None

    if current_player["id"] != player_id:
        return None

    if room["current_question"] is None:
        return None

    correct_answer = room["current_question"]["correct_answer"]
    is_correct = answer == correct_answer

    result = {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "answered_by": current_player["name"],
    }

    if is_correct:
        points = POINTS_BY_DIFFICULTY[room["selected_difficulty"]]
        current_player["score"] += points
        result["points_earned"] = points
    else:
        result["points_earned"] = 0

    room["last_answer_result"] = result

    if current_player["score"] >= room["points_to_win"]:
        room["status"] = "finished"
        room["winner"] = current_player
        room["available_themes"] = []
        room["selected_theme"] = None
        room["selected_difficulty"] = None
        room["current_question"] = None
        return room

    next_turn(room_code)

    return room

def leave_room(room_code, player_id):
    room = get_room(room_code)

    if room is None:
        return None

    player_index = None

    for index, player in enumerate(room["players"]):
        if player["id"] == player_id:
            player_index = index
            break

    if player_index is None:
        return None

    was_current_player = (
        room["players"][player_index]["id"] == get_current_player(room)["id"]
    )

    removed_player = room["players"].pop(player_index)

    if not room["players"]:
        del rooms[room["code"]]
        return None

    if removed_player["is_host"]:
        room["host_id"] = room["players"][0]["id"]
        room["players"][0]["is_host"] = True

    if player_index < room["current_player_index"]:
        room["current_player_index"] -= 1

    if room["current_player_index"] >= len(room["players"]):
        room["current_player_index"] = 0

    if was_current_player:
        room["available_themes"] = choose_themes()
        room["selected_theme"] = None
        room["selected_difficulty"] = None
        room["current_question"] = None

    return room

def restart_game(room_code, player_id):
    room = get_room(room_code)

    if room is None:
        return None

    if room["host_id"] != player_id:
        return None

    for player in room["players"]:
        player["score"] = 0

    room["status"] = "playing"
    room["current_player_index"] = randrange(len(room["players"]))
    room["available_themes"] = choose_themes()
    room["selected_theme"] = None
    room["selected_difficulty"] = None
    room["current_question"] = None
    room["last_answer_result"] = None
    room["winner"] = None
    room["asked_questions"] = []

    return room

def timeout_question(room_code, question_id):
    room = get_room(room_code)

    if room is None:
        return None

    if room["status"] != "playing":
        return None

    if room["current_question"] is None:
        return None

    if room["current_question"].get("id") != question_id:
        return None

    current_player = get_current_player(room)

    if current_player is None:
        return None

    correct_answer = room["current_question"]["correct_answer"]

    room["last_answer_result"] = {
        "is_correct": False,
        "correct_answer": correct_answer,
        "answered_by": current_player["name"],
        "points_earned": 0,
        "timed_out": True,
    }

    next_turn(room_code)

    return room

def normalize_player_name(player_name):
    return player_name.strip()

def update_room_settings(room_code, player_id, points_to_win, question_time_limit):
    room = get_room(room_code)

    if room is None:
        return None

    if room["host_id"] != player_id:
        return None

    if room["status"] != "waiting":
        return None

    if points_to_win < 1 or points_to_win > 100:
        return None

    if question_time_limit < 5 or question_time_limit > 180:
        return None

    room["points_to_win"] = points_to_win
    room["question_time_limit"] = question_time_limit

    return room