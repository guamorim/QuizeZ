function formatPoints(score) {
  return score + (score === 1 ? " ponto" : " pontos");
}

export function MatchResult({ winner, isHost, disabled, restarting, onRestart }) {
  return (
    <section className="match-result" aria-labelledby="match-result-title">
      <div role="status">
        <h3 id="match-result-title">{winner ? "Vencedor" : "Fim de partida"}</h3>
        {winner && <p className="match-winner">{winner.name} · {formatPoints(winner.score)}</p>}
      </div>
      {isHost && (
        <button type="button" disabled={disabled} onClick={onRestart}>
          {restarting ? "Reiniciando…" : "Nova partida"}
        </button>
      )}
    </section>
  );
}

export default function Scoreboard({ room, playerId, disabled, onRemovePlayer }) {
  const playing = room.status === "playing";
  const finished = room.status === "finished";
  const ranked = playing || finished;
  const isHost = room.host_id === playerId;
  const players = ranked ? [...room.players].sort((a, b) => b.score - a.score) : room.players;
  let rank = 0;

  return (
    <section className="scoreboard" aria-labelledby="scoreboard-title">
      <h3 id="scoreboard-title">
        {finished ? "Classificação final" : playing ? "Placar" : "Jogadores"}
        {!ranked && <span className="count">{players.length}</span>}
      </h3>
      <ul className={ranked ? "player-list ranked" : "player-list"} role="list">
        {players.map((player, index) => {
          if (index === 0 || player.score !== players[index - 1].score) {
            rank = index + 1;
          }

          const isCurrent = playing && player.id === room.current_player?.id;
          const isWinner = finished && player.id === room.winner?.id;
          const rowClass = isWinner ? "is-winner" : isCurrent ? "is-current" : undefined;

          return (
            <li key={player.id} className={rowClass}>
              <span className="player-slot" aria-hidden={!ranked}>
                {ranked ? rank + "º" : "P" + (index + 1)}
              </span>
              <span className="player-name">{player.name}</span>
              {ranked && <span className="player-score">{formatPoints(player.score)}</span>}
              <div className="player-row-actions">
                <span className="player-labels">
                  {player.id === playerId && <span>Você</span>}
                  {player.is_host && <span className="host-label">Host</span>}
                  {isCurrent && <span className="current-label">Na vez</span>}
                  {isWinner && <span className="winner-label">Vencedor</span>}
                  {player.connection_status === "reconnecting" && <span>Reconectando</span>}
                  {player.connection_status === "offline" && <span>Offline</span>}
                </span>
                {isHost && player.id !== playerId && (
                  <button
                    type="button"
                    className="secondary remove-button"
                    aria-label={"Remover " + player.name + " da sala"}
                    onClick={() => onRemovePlayer(player)}
                    disabled={disabled}
                  >
                    Remover
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
