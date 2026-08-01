import json
import os
from random import shuffle

import requests
from dotenv import load_dotenv


load_dotenv()


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

    if not isinstance(data["alternatives"], list):
        raise ValueError("Alternativas precisam ser uma lista")

    if len(data["alternatives"]) != 4:
        raise ValueError("A pergunta precisa ter exatamente 4 alternativas")

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


def generate_fake_question(theme, difficulty):
    question = {
        "theme": theme,
        "difficulty": difficulty,
        "question": f"Pergunta de exemplo sobre {theme} na dificuldade {difficulty}.",
        "alternatives": [
            "Alternativa A",
            "Alternativa B",
            "Alternativa C",
            "Alternativa D",
        ],
        "correct_answer": "Alternativa A",
    }

    return shuffle_question_alternatives(question)


def generate_ollama_question(theme, difficulty, asked_questions):
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
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=60,
    )

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


def generate_question(theme, difficulty, asked_questions=None):
    asked_questions = asked_questions or []
    provider = os.getenv("QUESTION_PROVIDER", "fake")

    if provider == "ollama":
        last_error = None

        for attempt in range(3):
            try:
                return generate_ollama_question(theme, difficulty, asked_questions)
            except Exception as error:
                last_error = error
                print(f"Tentativa {attempt + 1} falhou ao gerar pergunta com Ollama: {error}")

        print(f"Todas as tentativas com Ollama falharam. Usando pergunta fake. Ultimo erro: {last_error}")
        return generate_fake_question(theme, difficulty)

    return generate_fake_question(theme, difficulty)