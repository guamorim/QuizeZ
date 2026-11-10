import { useEffect, useRef, useState } from "react";
import { postRoomAction } from "./room.js";

function secondsUntil(deadline) {
  return Number.isFinite(deadline)
    ? Math.max(0, Math.ceil((deadline - Date.now()) / 1000))
    : null;
}

function useQuestionTimer(expiresAt, paused) {
  const deadline = Date.parse(expiresAt);
  const [clock, setClock] = useState(() => ({ expiresAt, seconds: secondsUntil(deadline) }));

  useEffect(() => {
    if (paused || !Number.isFinite(deadline)) return;

    function tick() {
      const seconds = secondsUntil(deadline);
      setClock((previous) =>
        previous.expiresAt === expiresAt && previous.seconds === seconds
          ? previous
          : { expiresAt, seconds },
      );
      if (seconds === 0) window.clearInterval(interval);
    }

    const interval = window.setInterval(tick, 200);
    tick();
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [deadline, expiresAt, paused]);

  return clock.expiresAt === expiresAt ? clock.seconds : secondsUntil(deadline);
}

const errors = {
  answer: "Não foi possível responder a pergunta.",
  regenerate: "Não foi possível trocar a pergunta.",
};

function Question({ question, player, session, difficultyLabel, busy, onRemovePlayer }) {
  const [pending, setPending] = useState("");
  const [failure, setFailure] = useState("");
  const request = useRef("");
  const yourTurn = player.id === session.playerId;
  const regenerating = question.regenerating || pending === "regenerate";
  const seconds = useQuestionTimer(question.expires_at, regenerating);
  const canAnswer = yourTurn && !busy && !pending && !regenerating && seconds > 0;
  const timeLabel = regenerating ? "Pausado" : seconds === null ? "—" : seconds + " s";
  const pointsLabel = question.points + (question.points === 1 ? " ponto" : " pontos");

  async function submit(action, fields = {}) {
    if (!canAnswer || request.current || secondsUntil(Date.parse(question.expires_at)) <= 0) return;
    if (action === "regenerate" && question.regenerated) return;

    request.current = action;
    setPending(action);
    setFailure("");
    try {
      await postRoomAction(
        session,
        action,
        { question_id: question.id, ...fields },
        errors[action],
      );
    } catch (error) {
      request.current = "";
      setPending("");
      setFailure(error.message);
    }
  }

  async function removePlayer() {
    const message = await onRemovePlayer(player);
    if (message) setFailure(message);
  }

  return (
    <>
      <header className="question-header">
        <div>
          <p className="question-owner">{yourTurn ? "Sua vez" : "Vez de " + player.name}</p>
          <p className="question-meta">{question.theme} · {difficultyLabel} · Vale {pointsLabel}</p>
        </div>
        <span className="question-timer" data-low={seconds <= 5 && !regenerating} role="timer" aria-label="Tempo restante">
          {timeLabel}
        </span>
      </header>
      <h2 id="question-title">{question.question}</h2>
      <div className="question-options" role="group" aria-label="Alternativas">
        {question.alternatives.map((answer, index) => (
          <button
            key={index}
            type="button"
            className="secondary question-option"
            disabled={!canAnswer}
            onClick={() => submit("answer", { answer })}
          >
            <span className="question-option-key" aria-hidden="true">{"ABCD"[index]}</span>
            <span>{answer}</span>
          </button>
        ))}
      </div>
      {failure && <p className="error" role="alert">{failure}</p>}
      {regenerating && <p className="turn-hint" role="status">Gerando nova pergunta…</p>}
      {!regenerating && pending === "answer" && (
        <p className="turn-hint" role="status">Enviando resposta…</p>
      )}
      {!regenerating && !pending && seconds === 0 && (
        <p className="turn-hint" role="status">Tempo esgotado.</p>
      )}
      <div className="actions">
        {yourTurn && !question.regenerated && (
          <button type="button" className="secondary" disabled={!canAnswer}
            onClick={() => submit("regenerate")}>
            {question.points > 1 ? "Trocar pergunta (-1 ponto)" : "Trocar pergunta"}
          </button>
        )}
        {onRemovePlayer && (
          <button type="button" className="secondary remove-button" disabled={Boolean(busy)}
            onClick={removePlayer}>
            Remover jogador da vez
          </button>
        )}
      </div>
    </>
  );
}

export default function QuestionDialog(props) {
  const dialogRef = useRef(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className="question-dialog"
      aria-labelledby="question-title"
      onCancel={(event) => event.preventDefault()}
    >
      <div className="question-content">
        <Question key={props.question.id} {...props} />
      </div>
    </dialog>
  );
}
