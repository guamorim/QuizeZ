import { useState } from "react";
import mark from "./mark.svg";
import { postRoom, postRoomAction, useRoom } from "./room.js";
import Scoreboard, { MatchResult } from "./Scoreboard.jsx";
import Turn from "./Turn.jsx";

const roomStates = {
  waiting: "Aguardando início",
  playing: "Partida em andamento",
  finished: "Partida encerrada",
};

const hostErrors = {
  settings: "Não foi possível salvar as configurações.",
  start: "Não foi possível iniciar a partida.",
  kick: "Não foi possível remover o jogador.",
  restart: "Não foi possível iniciar uma nova partida.",
};

function getInviteCode() {
  const code = new URLSearchParams(window.location.search).get("room")?.trim().toUpperCase();
  return /^[A-F0-9]{6}$/.test(code ?? "") ? code : "";
}

function Lobby({ busy, onEnter }) {
  const [inviteCode] = useState(getInviteCode);

  function submit(event, action) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    onEnter(action, fields.get("name").trim(), fields.get("code")?.trim().toUpperCase());
  }

  return (
    <div className="lobby">
      <form className="lobby-form" onSubmit={(event) => submit(event, "create")}>
        <h2>Criar sala</h2>
        <label htmlFor="host-name">Seu nome</label>
        <input id="host-name" name="name" autoComplete="nickname" required />
        <button type="submit" disabled={Boolean(busy)}>
          {busy === "create" ? "Criando…" : "Criar sala"}
        </button>
      </form>
      <form className="lobby-form" onSubmit={(event) => submit(event, "join")}>
        <h2>Entrar na sala</h2>
        <label htmlFor="player-name">Seu nome</label>
        <input id="player-name" name="name" autoComplete="nickname" autoFocus={Boolean(inviteCode)} required />
        <label htmlFor="room-code">Código da sala</label>
        <input id="room-code" name="code" className="code-input" defaultValue={inviteCode}
          autoCapitalize="characters" autoComplete="off" spellCheck={false} maxLength={6}
          pattern="[0-9A-Fa-f]{6}" required />
        <button type="submit" disabled={Boolean(busy)}>
          {busy === "join" ? "Entrando…" : "Entrar na sala"}
        </button>
      </form>
    </div>
  );
}

function HostSettings({ room, busy, connected, onAction }) {
  function submit(event) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const action = event.nativeEvent.submitter?.value === "start" ? "start" : "settings";
    onAction(action, {
      points_to_win: Number(fields.get("points")),
      question_time_limit: Number(fields.get("seconds")),
    });
  }

  const disabled = !connected || Boolean(busy);
  return (
    <form className="host-settings" aria-labelledby="host-settings-title" onSubmit={submit}>
      <h3 id="host-settings-title">Configurações da partida</h3>
      <div className="settings-fields">
        <label>
          Pontos para vencer
          <input type="number" name="points" min={1} max={100} step={1}
            defaultValue={room.points_to_win} disabled={disabled} required />
        </label>
        <label>
          Tempo por pergunta (s)
          <input type="number" name="seconds" min={5} max={180} step={1}
            defaultValue={room.question_time_limit} disabled={disabled} required />
        </label>
      </div>
      <div className="actions">
        <button type="submit" value="settings" className="secondary" disabled={disabled}>
          {busy === "settings" ? "Salvando…" : "Salvar configurações"}
        </button>
        <button type="submit" value="start" disabled={disabled}>
          {busy === "start" ? "Iniciando…" : "Iniciar partida"}
        </button>
      </div>
    </form>
  );
}

function AnswerResult({ result }) {
  const points = result.points_earned + (result.points_earned === 1 ? " ponto" : " pontos");
  const message = result.timed_out
    ? result.answered_by + " ficou sem tempo."
    : result.is_correct
      ? result.answered_by + " acertou e ganhou " + points + "."
      : result.answered_by + " errou.";

  return (
    <section className="answer-result" aria-labelledby="answer-result-title">
      <h3 id="answer-result-title">Última resposta</h3>
      <div role="status">
        <p>{message}</p>
        {!result.is_correct && <p className="turn-hint">Resposta correta: {result.correct_answer}</p>}
      </div>
    </section>
  );
}

function Room({ room, session, busy, connected, feedback, onLeave, onHostAction }) {
  const [copyState, setCopyState] = useState("");
  const isHost = room.host_id === session.playerId;
  const hostControlsDisabled = !connected || Boolean(busy);
  const invite = new URL("/", window.location.origin);
  invite.searchParams.set("room", room.code);

  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(invite.href);
      setCopyState("copied");
    } catch {
      setCopyState("manual");
    }
  }

  function removePlayer(player) {
    if (window.confirm("Remover " + player.name + " da sala?")) {
      return onHostAction("kick", { target_player_id: player.id });
    }
  }

  return (
    <section className="room" aria-labelledby="room-title">
      <div className="room-header">
        <div>
          <p className="room-state">{roomStates[room.status]}</p>
          <h2 id="room-title">
            <span className="room-code-label">Código da sala</span>
            <span className="room-code">{room.code}</span>
          </h2>
        </div>
        <div className="room-meta">
          <dl className="room-rules">
            <div><dt>Meta</dt><dd>{room.points_to_win} {room.points_to_win === 1 ? "ponto" : "pontos"}</dd></div>
            <div><dt>Tempo</dt><dd>{room.question_time_limit} s</dd></div>
          </dl>
          <div className="actions">
            <button type="button" className="secondary" onClick={copyInvite}>Copiar link</button>
            <button type="button" className="secondary" onClick={onLeave} disabled={Boolean(busy)}>Sair da sala</button>
          </div>
        </div>
      </div>
      {copyState === "copied" && <p className="notice" role="status">Link copiado.</p>}
      {copyState === "manual" && (
        <label className="invite-field">
          Link da sala
          <input value={invite.href} onFocus={(event) => event.target.select()} readOnly />
        </label>
      )}
      {isHost && room.status === "waiting" && (
        <HostSettings
          key={room.points_to_win + ":" + room.question_time_limit}
          room={room}
          busy={busy}
          connected={connected}
          onAction={onHostAction}
        />
      )}
      {feedback && <p className="notice" role="status">{feedback}</p>}
      {room.status === "finished" && (
        <MatchResult
          winner={room.winner}
          isHost={isHost}
          disabled={hostControlsDisabled}
          restarting={busy === "restart"}
          onRestart={() => onHostAction("restart")}
        />
      )}
      {room.last_answer_result && <AnswerResult result={room.last_answer_result} />}
      {room.status === "playing" && (
        <Turn
          key={room.turn_number}
          room={room}
          session={session}
          connected={connected}
          busy={busy}
          onRemovePlayer={removePlayer}
        />
      )}
      <Scoreboard
        room={room}
        playerId={session.playerId}
        disabled={hostControlsDisabled}
        onRemovePlayer={removePlayer}
      />
    </section>
  );
}

export default function App() {
  const { session, room, notice, activateSession } = useRoom();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");

  async function enterRoom(action, name, code) {
    if (busy) return;
    setError("");
    setFeedback("");
    if (!name) {
      setError("Digite seu nome.");
      return;
    }

    setBusy(action);
    try {
      const creating = action === "create";
      const path = creating ? "/rooms" : "/rooms/" + encodeURIComponent(code) + "/join";
      const body = creating ? { host_name: name } : { player_name: name };
      const fallback = creating ? "Não foi possível criar a sala." : "Não foi possível entrar na sala.";
      const data = await postRoom(path, body, fallback);
      activateSession(
        { code: data.room.code, playerId: data.player_id, token: data.session_token },
        data.room,
      );
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy("");
    }
  }

  async function leaveRoom() {
    if (busy || !session) return;
    setBusy("leave");
    setError("");
    setFeedback("");
    activateSession(null);
    try {
      await postRoomAction(
        session,
        "leave",
        {},
        "Não foi possível avisar o servidor da saída.",
      );
    } catch {
      setError("Você saiu. O servidor não recebeu a saída.");
    } finally {
      setBusy("");
    }
  }

  async function runHostAction(action, fields = {}) {
    if (busy || notice || !session || room?.host_id !== session.playerId) return;
    if ((action === "start" || action === "settings") && room.status !== "waiting") return;
    if (action === "restart" && room.status !== "finished") return;

    setBusy(action);
    setError("");
    setFeedback("");

    try {
      if (action === "start" && (
        fields.points_to_win !== room.points_to_win ||
        fields.question_time_limit !== room.question_time_limit
      )) {
        await postRoomAction(session, "settings", fields, hostErrors.settings);
      }

      await postRoomAction(session, action, action === "start" ? {} : fields, hostErrors[action]);

      if (action === "settings") {
        setFeedback("Configurações salvas.");
      }
    } catch (failure) {
      setError(failure.message);
      return failure.message;
    } finally {
      setBusy("");
    }
  }

  return (
    <main className="shell">
      <header className="brand">
        <img src={mark} width="44" height="44" alt="" />
        <h1>quiZeZ</h1>
      </header>
      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {!session && <Lobby busy={busy} onEnter={enterRoom} />}
      {session && room && (
        <Room
          key={room.code}
          room={room}
          session={session}
          busy={busy}
          connected={!notice}
          feedback={feedback}
          onLeave={leaveRoom}
          onHostAction={runHostAction}
        />
      )}
      {session && !room && <button type="button" className="secondary" onClick={leaveRoom}>Sair da sala</button>}
    </main>
  );
}
