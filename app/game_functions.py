from random import choice, sample
from secrets import compare_digest, token_hex

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
                "connection_status": "offline",
            }
        ],
        "player_tokens": {host_id: token_hex(24)},
        "current_player_index": None,
        "turn_number": 0,
        "available_themes": [],
        "selected_theme": None,
        "selected_difficulty": None,
        "question_generation_status": None,
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


def get_session_player(room, player_id, session_token):
    expected_token = room["player_tokens"].get(player_id)
    if expected_token is None or not session_token.isascii() or not compare_digest(expected_token, session_token):
        return None

    return next((player for player in room["players"] if player["id"] == player_id), None)


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
            "connection_status": "offline",
        }
    )
    room["player_tokens"][player_id] = token_hex(24)

    return room, player_id

def choose_themes(amount=5):
    return sample(THEMES_POOL, amount)


def prepare_turn(room, player_index):
    room["current_player_index"] = player_index
    room["turn_number"] += 1
    room["available_themes"] = choose_themes() if player_index is not None else []
    room["selected_theme"] = None
    room["selected_difficulty"] = None
    room["question_generation_status"] = None
    room["current_question"] = None


def start_random_turn(room):
    online_indices = [
        index for index, player in enumerate(room["players"])
        if player["connection_status"] == "online"
    ]
    prepare_turn(room, choice(online_indices) if online_indices else None)


def advance_turn(room, start_index):
    players = room["players"]
    for offset in range(len(players)):
        index = (start_index + offset) % len(players)
        if players[index]["connection_status"] == "online":
            prepare_turn(room, index)
            return

    prepare_turn(room, None)


def start_game(room_code, player_id):
    room = get_room(room_code)

    if room is None:
        return None

    if room["host_id"] != player_id:
        return None

    room["status"] = "playing"
    start_random_turn(room)
    room["winner"] = None
    room["last_answer_result"] = None

    return room

def get_current_player(room):
    player_index = room["current_player_index"]
    if player_index is None or not room["players"]:
        return None

    return room["players"][player_index]

def serialize_room(room):
    if room is None:
        return None

    room_data = room.copy()
    room_data.pop("asked_questions", None)
    room_data.pop("player_tokens", None)
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

    if room["selected_difficulty"] is not None:
        return None

    if theme not in room["available_themes"]:
        return None

    room["selected_theme"] = theme

    return room


def set_current_question(room, question, *, regenerated=False):
    question["id"] = token_hex(8)
    question["regenerated"] = regenerated
    base_points = POINTS_BY_DIFFICULTY[question["difficulty"]]
    question["points"] = max(1, base_points - 1) if regenerated else base_points
    room["current_question"] = question
    room["question_generation_status"] = None
    room["asked_questions"].append(question["question"])


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
    
    if difficulty not in POINTS_BY_DIFFICULTY:
        return None

    previous_difficulty = room["selected_difficulty"]
    if previous_difficulty is not None and (
        room["question_generation_status"] != "failed" or difficulty != previous_difficulty
    ):
        return None

    room["selected_difficulty"] = difficulty
    room["question_generation_status"] = "generating"
    return room

def next_turn(room_code):
    room = get_room(room_code)

    if room is None:
        return None

    current_index = room["current_player_index"]
    advance_turn(room, 0 if current_index is None else current_index + 1)

    return room


def answer_question(room_code, player_id, answer, question_id=None):
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

    question = room["current_question"]
    if question is None or question.get("regenerating"):
        return None

    if (question_id is not None or question.get("regenerated")) and question["id"] != question_id:
        return None

    correct_answer = question["correct_answer"]
    is_correct = answer == correct_answer

    result = {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "answered_by": current_player["name"],
    }

    if is_correct:
        points = question.get("points", POINTS_BY_DIFFICULTY[room["selected_difficulty"]])
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

    current_index = room["current_player_index"]
    removed_player = room["players"].pop(player_index)
    del room["player_tokens"][player_id]

    if not room["players"]:
        del rooms[room["code"]]
        return None

    if removed_player["is_host"]:
        room["host_id"] = room["players"][0]["id"]
        room["players"][0]["is_host"] = True

    if current_index == player_index:
        if room["status"] == "playing":
            advance_turn(room, player_index)
        else:
            room["current_player_index"] = None
    elif current_index is not None and player_index < current_index:
        room["current_player_index"] -= 1

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
    start_random_turn(room)
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

    question = room["current_question"]
    if question is None or question.get("regenerating"):
        return None

    if question.get("id") != question_id:
        return None

    current_player = get_current_player(room)

    if current_player is None:
        return None

    correct_answer = question["correct_answer"]

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
