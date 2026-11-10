from datetime import datetime, timezone
from random import choice, sample
from secrets import compare_digest, token_hex

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
DISCONNECT_GRACE_PERIOD = 10
SOCKET_HEARTBEAT_SECONDS = 10
SOCKET_LEASE_SECONDS = 30
QUESTION_GENERATION_SECONDS = 210

def generate_room_code():
    return token_hex(3).upper()


def create_room(host_name):
    host_name = normalize_player_name(host_name)

    if not host_name:
        return None, None

    room_code = generate_room_code()
    host_id = token_hex(8)

    room = {
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
        "connections": {},
        "reconnect_deadlines": {},
        "current_player_index": None,
        "turn_number": 0,
        "available_themes": [],
        "selected_theme": None,
        "selected_difficulty": None,
        "question_generation_status": None,
        "generation": None,
        "current_question": None,
        "last_answer_result": None,
        "winner": None,
        "asked_questions": [],
        "points_to_win": POINTS_TO_WIN,
        "question_time_limit": DEFAULT_QUESTION_TIME_LIMIT,

    }

    return room, host_id


def get_session_player(room, player_id, session_token):
    expected_token = room["player_tokens"].get(player_id)
    if expected_token is None or not session_token.isascii() or not compare_digest(expected_token, session_token):
        return None

    return next((player for player in room["players"] if player["id"] == player_id), None)


def join_room(room, player_name):
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
    room["generation"] = None
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


def start_game(room, player_id):
    if room["host_id"] != player_id or room["status"] != "waiting":
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
    room_data.pop("connections", None)
    room_data.pop("reconnect_deadlines", None)
    room_data.pop("generation", None)
    room_data["current_player"] = get_current_player(room)

    if room_data["current_question"] is not None:
        question_data = room_data["current_question"].copy()
        question_data.pop("correct_answer", None)
        room_data["current_question"] = question_data

    return room_data

def select_theme(room, player_id, theme):
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


def set_question_deadline(question, deadline):
    question["expires_at"] = datetime.fromtimestamp(deadline, timezone.utc).isoformat()


def question_deadline(question):
    return datetime.fromisoformat(question["expires_at"]).timestamp()


def set_current_question(room, question, now, *, regenerated=False):
    question = question.copy()
    question["id"] = token_hex(8)
    question["regenerated"] = regenerated
    base_points = POINTS_BY_DIFFICULTY[question["difficulty"]]
    question["points"] = max(1, base_points - 1) if regenerated else base_points
    set_question_deadline(question, now + room["question_time_limit"])
    room["current_question"] = question
    room["question_generation_status"] = None
    room["asked_questions"].append(question["question"])
    del room["asked_questions"][:-10]


def select_difficulty(room, player_id, difficulty):
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

def next_turn(room):
    current_index = room["current_player_index"]
    advance_turn(room, 0 if current_index is None else current_index + 1)

    return room


def answer_question(room, player_id, answer, question_id):
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

    if question["id"] != question_id:
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

    next_turn(room)

    return room

def leave_room(room, player_id):
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
    room["connections"].pop(player_id, None)
    room["reconnect_deadlines"].pop(player_id, None)

    if not room["players"]:
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

def restart_game(room, player_id):
    if room["host_id"] != player_id or room["status"] != "finished":
        return None

    for player in room["players"]:
        player["score"] = 0

    room["status"] = "playing"
    start_random_turn(room)
    room["last_answer_result"] = None
    room["winner"] = None
    room["asked_questions"] = []

    return room

def timeout_question(room):
    if room["status"] != "playing":
        return None

    question = room["current_question"]
    if question is None or question.get("regenerating"):
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

    next_turn(room)

    return room

def normalize_player_name(player_name):
    return player_name.strip()

def update_room_settings(room, player_id, points_to_win, question_time_limit):
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


def start_generation(room, now, *, remaining_time=None):
    generation = {
        "id": token_hex(12),
        "deadline": now + QUESTION_GENERATION_SECONDS,
        "remaining_time": remaining_time,
    }
    room["generation"] = generation
    return generation["id"]


def finish_generation(room, generation_id, question, now):
    generation = room["generation"] if room is not None else None
    if generation is None or generation["id"] != generation_id:
        return False

    room["generation"] = None
    remaining_time = generation["remaining_time"]
    if question is not None:
        set_current_question(room, question, now, regenerated=remaining_time is not None)
    elif remaining_time is not None:
        previous_question = room["current_question"]
        previous_question.pop("regenerating", None)
        set_question_deadline(previous_question, now + remaining_time)
    else:
        room["question_generation_status"] = "failed"
    return True


def connect_player(room, player, connection_id, now):
    player_id = player["id"]
    leases = room["connections"].setdefault(player_id, {})
    leases[connection_id] = now + SOCKET_LEASE_SECONDS
    room["reconnect_deadlines"].pop(player_id, None)
    player["connection_status"] = "online"
    if room["status"] == "playing" and get_current_player(room) is None:
        next_turn(room)


def disconnect_player(room, player_id, connection_id, now):
    leases = room["connections"].get(player_id)
    if not leases or connection_id not in leases:
        return
    del leases[connection_id]
    if not leases:
        del room["connections"][player_id]
        player = next(player for player in room["players"] if player["id"] == player_id)
        player["connection_status"] = "reconnecting"
        room["reconnect_deadlines"][player_id] = now + DISCONNECT_GRACE_PERIOD


def reconcile_room(room, now):
    active_player = get_current_player(room)
    active_disconnect_at = None
    for player in room["players"]:
        player_id = player["id"]
        leases = room["connections"].get(player_id)
        if leases:
            last_expiry = max(leases.values())
            for connection_id, expires_at in list(leases.items()):
                if expires_at <= now:
                    del leases[connection_id]
            if not leases:
                del room["connections"][player_id]
                player["connection_status"] = "reconnecting"
                room["reconnect_deadlines"][player_id] = last_expiry + DISCONNECT_GRACE_PERIOD
        reconnect_at = room["reconnect_deadlines"].get(player_id)
        if reconnect_at is not None and reconnect_at <= now:
            del room["reconnect_deadlines"][player_id]
            player["connection_status"] = "offline"
            if player is active_player:
                active_disconnect_at = reconnect_at

    if room["status"] != "playing":
        return
    generation = room["generation"]
    if generation is not None and generation["deadline"] <= now:
        finish_generation(room, generation["id"], None, generation["deadline"])

    # If both deadlines passed while the room was idle, apply the first one.
    question = room["current_question"]
    if question is not None and not question.get("regenerating"):
        expires_at = question_deadline(question)
        if expires_at <= now and (active_disconnect_at is None or expires_at <= active_disconnect_at):
            timeout_question(room)
            return
    if active_player is not None and active_player["connection_status"] == "offline":
        next_turn(room)


def next_room_deadline(room):
    deadlines = list(room["reconnect_deadlines"].values())
    deadlines.extend(max(leases.values()) for leases in room["connections"].values() if leases)
    generation = room["generation"]
    if generation is not None:
        deadlines.append(generation["deadline"])
    question = room["current_question"]
    if question is not None and not question.get("regenerating"):
        deadlines.append(question_deadline(question))
    return min(deadlines, default=float("inf"))
