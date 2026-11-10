import json
import os
from random import shuffle
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv


load_dotenv()


class QuestionGenerationError(RuntimeError):
    pass


def extract_json_object(text):
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("Nenhum JSON encontrado na resposta do modelo")

    json_text = text[start : end + 1]
    return json.loads(json_text)


def validate_question_data(data):
    required_keys = ["question", "alternatives", "correct_answer"]

    for key in required_keys:
        if key not in data:
            raise ValueError(f"Campo ausente na pergunta: {key}")

    if not isinstance(data["question"], str) or not data["question"].strip():
        raise ValueError("O texto da pergunta nao pode estar vazio")

    if not isinstance(data["alternatives"], list):
        raise ValueError("Alternativas precisam ser uma lista")

    if len(data["alternatives"]) != 4:
        raise ValueError("A pergunta precisa ter exatamente 4 alternativas")

    if any(not isinstance(answer, str) or not answer.strip() for answer in data["alternatives"]):
        raise ValueError("As alternativas precisam ser textos nao vazios")
    if len({answer.strip().casefold() for answer in data["alternatives"]}) != 4:
        raise ValueError("As alternativas precisam ser diferentes")

    if data["correct_answer"] not in data["alternatives"]:
        raise ValueError("Resposta correta precisa estar dentro das alternativas")

def shuffle_question_alternatives(question):
    alternatives = question["alternatives"].copy()
    shuffle(alternatives)

    question["alternatives"] = alternatives

    return question

def get_difficulty_instruction(difficulty):
    if difficulty == "facil":
        return """
Nivel facil:
- Use conhecimento comum.
- A pergunta deve ser direta.
- Evite pegadinhas.
- As alternativas podem ser mais simples.
"""

    if difficulty == "medio":
        return """
Nivel medio:
- Exija conhecimento especifico, mas ainda acessivel.
- Use alternativas plausiveis.
- Evite perguntas obvias.
"""

    if difficulty == "dificil":
        return """
Nivel dificil:
- Crie uma pergunta para jogadores experientes no tema.
- Exija conhecimento especifico, tecnico, historico ou conceitual.
- Nao pergunte definicoes basicas.
- Nao pergunte fatos amplamente conhecidos.
- Evite perguntas cuja resposta seja reconhecivel por eliminacao.
- Use alternativas incorretas altamente plausiveis.
- Todas as alternativas devem pertencer ao mesmo contexto.
- A pergunta deve exigir comparar detalhes proximos, excecoes, causas, consequencias, datas, obras, autores, termos tecnicos ou classificacoes.
- Se o tema for amplo, escolha um subtema menos obvio.
"""

    return "Nivel nao especificado."


def generate_fake_question(theme, difficulty, *, replacement=False):
    label = "Pergunta alternativa de exemplo" if replacement else "Pergunta de exemplo"
    question = {
        "theme": theme,
        "difficulty": difficulty,
        "question": f"{label} sobre {theme} na dificuldade {difficulty}.",
        "alternatives": [
            "Alternativa A",
            "Alternativa B",
            "Alternativa C",
            "Alternativa D",
        ],
        "correct_answer": "Alternativa A",
    }

    return shuffle_question_alternatives(question)


def get_ollama_connection():
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    try:
        url = urlsplit(base_url)
    except ValueError:
        raise QuestionGenerationError("OLLAMA_BASE_URL invalida") from None

    if not url.hostname or url.username is not None or url.path not in ("", "/") or url.query or url.fragment:
        raise QuestionGenerationError("OLLAMA_BASE_URL deve conter apenas o endereco base, sem credenciais")

    endpoint = f"{url.scheme}://{url.netloc}/api/generate"
    user = os.getenv("OLLAMA_TUNNEL_USER")
    password = os.getenv("OLLAMA_TUNNEL_PASSWORD")

    if url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1") and not (user or password):
        return endpoint, None
    if url.scheme == "https" and user and password:
        return endpoint, (user, password)

    raise QuestionGenerationError("O acesso remoto ao Ollama exige HTTPS e as duas credenciais do tunel")


def generate_ollama_question(theme, difficulty, asked_questions):
    endpoint, auth = get_ollama_connection()
    recent_questions = asked_questions[-10:]

    avoid_repetition_instruction = ""

    if recent_questions:
        avoid_repetition_instruction = "Nao repita perguntas iguais ou muito parecidas com estas:\n"
    for question in recent_questions:
        avoid_repetition_instruction += f"- {question}\n"
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    difficulty_instruction = get_difficulty_instruction(difficulty)
    

    prompt = f"""
Voce e um gerador de perguntas para um jogo multiplayer de quiz.

Crie uma pergunta original em portugues do Brasil.

Tema: {theme}
Dificuldade: {difficulty}
{avoid_repetition_instruction}

{difficulty_instruction}

Antes de responder, escolha mentalmente um subtema menos comum dentro do tema.
Nao explique esse raciocinio.

Regras obrigatorias:
- Responda apenas com JSON valido.
- Nao use markdown.
- Nao escreva explicacoes.
- Nao escreva texto antes ou depois do JSON.
- Gere exatamente 4 alternativas.
- Apenas uma alternativa deve estar correta.
- A resposta correta deve ser exatamente igual a uma das alternativas.
- As alternativas devem ter tamanho parecido.
- Evite alternativas obviamente absurdas.
- A pergunta deve ser objetiva.
- A pergunta deve ter apenas uma resposta correta.
- Nao repita o texto da resposta correta na pergunta.
- mantenha os nomes proprios e termos tecnicos originais, sem traducoes.

Formato exato:
{{
  "question": "texto da pergunta",
  "alternatives": ["alternativa 1", "alternativa 2", "alternativa 3", "alternativa 4"],
  "correct_answer": "alternativa correta"
}}
"""

    response = requests.post(
        endpoint,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        auth=auth,
        allow_redirects=False,
        timeout=60,
    )

    if response.status_code in (401, 403):
        raise QuestionGenerationError("O tunel negou o acesso ao Ollama. Confira a politica e as credenciais.")
    if 300 <= response.status_code < 400:
        raise QuestionGenerationError("O endereco do Ollama respondeu com um redirecionamento inesperado")

    response.raise_for_status()

    ollama_data = response.json()
    text = ollama_data["response"].strip()

    data = extract_json_object(text)
    validate_question_data(data)

    question = {
    "theme": theme,
    "difficulty": difficulty,
    "question": data["question"],
    "alternatives": data["alternatives"],
    "correct_answer": data["correct_answer"],
}

    return shuffle_question_alternatives(question)


def generate_question(theme, difficulty, asked_questions=None, *, different_from=None):
    asked_questions = asked_questions or []
    provider = os.getenv("QUESTION_PROVIDER", "fake")

    if provider == "ollama":
        last_error = None

        for attempt in range(3):
            try:
                question = generate_ollama_question(theme, difficulty, asked_questions)
                if different_from is not None and (
                    question["question"].strip().casefold() == different_from.strip().casefold()
                ):
                    raise ValueError("O Ollama repetiu a pergunta atual")
                return question
            except QuestionGenerationError as error:
                print(f"Erro ao conectar ao Ollama: {error}")
                raise
            except Exception as error:
                last_error = error
                print(f"Tentativa {attempt + 1} falhou ao gerar pergunta com Ollama: {error}")

        raise QuestionGenerationError("Nao foi possivel gerar a pergunta com Ollama") from last_error

    return generate_fake_question(theme, difficulty, replacement=different_from is not None)
