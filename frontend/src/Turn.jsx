import { useRef, useState } from "react";
import QuestionDialog from "./QuestionDialog.jsx";
import { postRoom } from "./room.js";

const difficulties = {
  facil: "Fácil",
  medio: "Médio",
  dificil: "Difícil",
};

const errors = {
  theme: "Não foi possível escolher esse tema.",
  difficulty: "Não foi possível escolher essa dificuldade.",
};

export default function Turn({ room, playerId, connected, busy, onRemovePlayer }) {
  const [pending, setPending] = useState("");
  const [failure, setFailure] = useState(null);
  const request = useRef("");
  const player = room.current_player;
  const yourTurn = player?.id === playerId;
  const selectedTheme = room.selected_theme;
  const difficulty = room.selected_difficulty;
  const questionReady = Boolean(room.current_question);
  const generating = !questionReady && (pending === "difficulty" || (difficulty && !failure));
  const phase = questionReady ? "question" : generating ? "generating" : selectedTheme ? "difficulty" : "theme";

  async function choose(action, fields) {
    if (!yourTurn || !connected || busy || phase !== action || request.current === action) return;

    request.current = action;
    setPending(action);
    setFailure(null);
    try {
      await postRoom(
        "/rooms/" + encodeURIComponent(room.code) + "/" + action,
        { player_id: playerId, ...fields },
        errors[action],
      );
    } catch (error) {
      if (request.current === action) {
        request.current = "";
        setPending("");
        setFailure({ action, message: error.message });
      }
    }
  }

  if (!player) {
    return (
      <section className="turn-panel" aria-labelledby="turn-title">
        <h3 id="turn-title">Turno</h3>
        <p className="turn-hint" role="status">Aguardando um jogador se conectar.</p>
      </section>
    );
  }

  const disabled = !connected || Boolean(busy);
  return (
    <section className="turn-panel" aria-labelledby="turn-title">
      <h3 id="turn-title" className="turn-title">{yourTurn ? "Sua vez" : "Vez de " + player.name}</h3>
      {player.connection_status === "reconnecting" && (
        <p className="turn-hint" role="status">{player.name} está reconectando.</p>
      )}
      {selectedTheme && (
        <p className="turn-selection">
          {selectedTheme}
          {difficulty && <span> · {difficulties[difficulty]}</span>}
        </p>
      )}
      {failure?.action === phase && <p className="error" role="alert">{failure.message}</p>}

      {phase === "theme" && (
        yourTurn ? (
          <>
            <p id="theme-label">{pending === "theme" ? "Salvando tema…" : "Escolha um tema"}</p>
            <div className="turn-options" role="group" aria-labelledby="theme-label">
              {room.available_themes.map((theme) => (
                <button
                  key={theme}
                  type="button"
                  className="secondary"
                  disabled={disabled || pending === "theme"}
                  onClick={() => choose("theme", { theme })}
                >
                  {theme}
                </button>
              ))}
            </div>
          </>
        ) : <p className="turn-hint">Aguardando a escolha do tema.</p>
      )}

      {phase === "difficulty" && (
        yourTurn ? (
          <>
            <p id="difficulty-label">Escolha a dificuldade</p>
            <div className="turn-options" role="group" aria-labelledby="difficulty-label">
              {Object.entries(difficulties).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className="secondary"
                  disabled={disabled}
                  onClick={() => choose("difficulty", { difficulty: value })}
                >
                  {label}
                </button>
              ))}
            </div>
          </>
        ) : <p className="turn-hint">Aguardando a escolha da dificuldade.</p>
      )}

      {phase === "generating" && <p className="turn-hint" role="status">Gerando pergunta…</p>}
      {phase === "question" && (
        <>
          <p className="turn-hint" role="status">Pergunta em andamento.</p>
          {connected && (
            <QuestionDialog
              question={room.current_question}
              roomCode={room.code}
              player={player}
              playerId={playerId}
              difficultyLabel={difficulties[difficulty]}
              busy={busy}
              onRemovePlayer={room.host_id === playerId && !yourTurn ? onRemovePlayer : null}
            />
          )}
        </>
      )}
    </section>
  );
}
