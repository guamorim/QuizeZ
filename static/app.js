let currentRoom = null;
let currentPlayerId = null;
let roomConnection = null;
let timerInterval = null;
let activeTimerExpiresAt = null;
let difficultyRequest = null;
let isAnsweringQuestion = false;
let pendingRegenerationQuestionId = null;

function isHost() {
  return currentRoom && currentRoom.host_id === currentPlayerId;
}

function isCurrentPlayer() {
  return currentRoom && currentRoom.current_player?.id === currentPlayerId;
}

function isQuestionRegenerating(question) {
  return question?.regenerating === true || question?.id === pendingRegenerationQuestionId;
}

function canAnswerQuestion(room) {
  return (
    roomConnection?.ready &&
    room?.status === "playing" &&
    room.current_question &&
    isCurrentPlayer() &&
    !isAnsweringQuestion &&
    !isQuestionRegenerating(room.current_question)
  );
}

function saveSession(roomCode, playerId, sessionToken) {
  localStorage.setItem("quizez_room_code", roomCode);
  localStorage.setItem("quizez_player_id", playerId);
  localStorage.setItem("quizez_session_token", sessionToken);
}

function clearSession() {
  localStorage.removeItem("quizez_room_code");
  localStorage.removeItem("quizez_player_id");
  localStorage.removeItem("quizez_session_token");
}

async function getErrorMessage(response, fallbackMessage) {
  try {
    const data = await response.json();

    if (data.detail) {
      return data.detail;
    }
  } catch (error) {
    // Usa a mensagem padrao abaixo.
  }

  return fallbackMessage;
}

function setDifficultyButtonsDisabled(disabled) {
  for (const button of difficultyButtons.querySelectorAll("button")) {
    button.disabled = disabled;
  }
}

function setAlternativeButtonsDisabled(disabled) {
  for (const button of modalAlternativesList.querySelectorAll("button")) {
    button.disabled = disabled;
  }

  for (const button of alternativesList.querySelectorAll("button")) {
    button.disabled = disabled;
  }
}

const hostNameInput = document.getElementById("hostNameInput");
const createRoomButton = document.getElementById("createRoomButton");
const roomCodeElement = document.getElementById("roomCode");
const playersHeading = document.getElementById("playersHeading");
const playersList = document.getElementById("playersList");
const playerNameInput = document.getElementById("playerNameInput");
const joinRoomCodeInput = document.getElementById("joinRoomCodeInput");
const joinRoomButton = document.getElementById("joinRoomButton");
const startGameButton = document.getElementById("startGameButton");
const roomStatus = document.getElementById("roomStatus");
const roomConnectionNotice = document.getElementById("roomConnectionNotice");
const cancelRoomReconnectButton = document.getElementById("cancelRoomReconnectButton");
const currentPlayer = document.getElementById("currentPlayer");
const themesList = document.getElementById("themesList");
const selectedTheme = document.getElementById("selectedTheme");
const difficultyButtons = document.getElementById("difficultyButtons");
const questionText = document.getElementById("questionText");
const alternativesList = document.getElementById("alternativesList");
const lastAnswerResult = document.getElementById("lastAnswerResult");
const gameMessage = document.getElementById("gameMessage");
const createRoomSection = document.getElementById("createRoomSection");
const joinRoomSection = document.getElementById("joinRoomSection");
const roomSection = document.getElementById("roomSection");
const leaveRoomButton = document.getElementById("leaveRoomButton");
const winnerText = document.getElementById("winnerText");
const restartGameButton = document.getElementById("restartGameButton");
const copyRoomCodeButton = document.getElementById("copyRoomCodeButton");
const copyRoomLinkButton = document.getElementById("copyRoomLinkButton");
const roomInviteFallback = document.getElementById("roomInviteFallback");
const roomInviteLink = document.getElementById("roomInviteLink");
const timerText = document.getElementById("timerText");
const questionModal = document.getElementById("questionModal");
const modalQuestionMeta = document.getElementById("modalQuestionMeta");
const modalTimerText = document.getElementById("modalTimerText");
const modalQuestionText = document.getElementById("modalQuestionText");
const modalAlternativesList = document.getElementById("modalAlternativesList");
const regenerateQuestionButton = document.getElementById("regenerateQuestionButton");
const regenerateQuestionStatus = document.getElementById("regenerateQuestionStatus");
const removeCurrentPlayerButton = document.getElementById("removeCurrentPlayerButton");
const modalCurrentPlayer = document.getElementById("modalCurrentPlayer");
const questionLoadingText = document.getElementById("questionLoadingText");
const roomSettings = document.getElementById("roomSettings");
const pointsToWinInput = document.getElementById("pointsToWinInput");
const saveSettingsButton = document.getElementById("saveSettingsButton");
const questionTimeLimitInput = document.getElementById(
  "questionTimeLimitInput",
);
const roomRules = document.getElementById("roomRules");

function renderPlayers(room) {
  const playing = room.status === "playing";
  const finished = room.status === "finished";
  const ranked = playing || finished;
  const players = ranked ? [...room.players].sort((a, b) => b.score - a.score) : room.players;

  playersHeading.textContent = finished ? "Classificação final" : playing ? "Placar" : "Jogadores";
  playersList.classList.toggle("is-ranked", ranked);
  playersList.replaceChildren();

  let rank = 0;
  for (const [index, player] of players.entries()) {
    const item = document.createElement("li");
    item.className = "player-entry";

    const playerName = document.createElement("span");
    playerName.className = "ranking-name";
    playerName.textContent = player.is_host ? `${player.name} (host)` : player.name;

    if (player.connection_status !== "online") {
      const connectionLabel = document.createElement("span");
      connectionLabel.className = "player-connection-label";
      connectionLabel.textContent = player.connection_status === "reconnecting" ? "Reconectando" : "Offline";
      playerName.append(" ", connectionLabel);
    }

    const score = document.createElement("span");
    score.className = "ranking-score";
    score.textContent = `${player.score} ${player.score === 1 ? "ponto" : "pontos"}`;

    const actions = document.createElement("span");
    actions.className = "player-entry-actions";
    actions.append(score);

    if (isHost() && player.id !== currentPlayerId) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "remove-player-button";
      button.textContent = "Remover";
      button.setAttribute("aria-label", `Remover ${player.name} da sala`);
      button.disabled = !roomConnection.ready;
      button.addEventListener("click", () => removePlayer(player, button));
      actions.append(button);
    }

    if (ranked) {
      if (index === 0 || player.score !== players[index - 1].score) {
        rank = index + 1;
      }

      const position = document.createElement("span");
      position.className = "ranking-position";
      position.textContent = `${rank}º`;

      const onTurn = playing && player.id === room.current_player?.id;
      const winner = finished && player.id === room.winner?.id;
      item.classList.add("ranking-row");

      if (onTurn || winner) {
        const label = document.createElement("span");
        label.className = "ranking-label";
        label.textContent = winner ? "Vencedor" : "Na vez";
        playerName.append(" ", label);
        item.classList.add("ranking-highlight");
      }

      item.append(position);
    }

    item.append(playerName, actions);
    playersList.append(item);
  }
}

function renderRoom(room) {
  if (
    roomConnection?.roomCode !== room.code ||
    !room.players.some((player) => player.id === currentPlayerId) ||
    (currentRoom?.code === room.code && room.turn_number < currentRoom.turn_number)
  ) {
    return;
  }

  if (difficultyRequest && (
    difficultyRequest.connection !== roomConnection ||
    difficultyRequest.turnNumber !== room.turn_number
  )) {
    difficultyRequest = null;
    setQuestionLoading(false);
  }

  const connected = roomConnection.ready;
  currentRoom = room;
  createRoomSection.style.display = "none";
  joinRoomSection.style.display = "none";
  roomSection.style.display = "block";
  cancelRoomReconnectButton.hidden = true;
  startGameButton.disabled = !connected;
  restartGameButton.disabled = !connected;
  saveSettingsButton.disabled = !connected;

  roomCodeElement.textContent = room.code;

  renderPlayers(room);

  roomStatus.textContent = room.status;

  if (room.current_player) {
    if (isCurrentPlayer()) {
      currentPlayer.textContent = `${room.current_player.name} (sua vez)`;
      currentPlayer.classList.add("is-you");
    } else {
      currentPlayer.textContent = room.current_player.name;
      currentPlayer.classList.remove("is-you");
    }
  } else {
    currentPlayer.textContent = "-";
    currentPlayer.classList.remove("is-you");
  }

  themesList.innerHTML = "";

  const canChooseTheme =
    connected && room.status === "playing" && isCurrentPlayer() && !room.selected_theme;

  for (const theme of room.available_themes || []) {
    const item = document.createElement("li");
    const button = document.createElement("button");

    button.textContent = theme;
    button.addEventListener("click", () => selectTheme(theme));

    item.appendChild(button);
    themesList.appendChild(item);
    button.disabled = !canChooseTheme;
  }
  selectedTheme.textContent = room.selected_theme || "-";

  const canChooseDifficulty =
    connected &&
    room.status === "playing" &&
    isCurrentPlayer() &&
    room.selected_theme &&
    !room.current_question &&
    !difficultyRequest;

  if (canChooseDifficulty) {
    difficultyButtons.style.display = "block";
  } else {
    difficultyButtons.style.display = "none";
  }

  const question = room.current_question;
  if (question) {
    questionText.textContent = question.question;

    alternativesList.innerHTML = "";

    for (const alternative of question.alternatives) {
      const item = document.createElement("li");
      const button = document.createElement("button");

      button.textContent = alternative;
      button.disabled = !canAnswerQuestion(room);
      button.addEventListener("click", () => answerQuestion(alternative, question.id));

      item.appendChild(button);
      alternativesList.appendChild(item);
    }
  } else {
    questionText.textContent = "-";
    alternativesList.innerHTML = "";
  }
  if (!connected) {
    stopTimerDisplay();
  } else if (isQuestionRegenerating(question)) {
    stopTimerDisplay();
    timerText.textContent = "Pausado";
    modalTimerText.textContent = "Pausado";
  } else if (question?.expires_at && room.status === "playing") {
    startTimerDisplay(question.expires_at);
  } else {
    stopTimerDisplay();
  }
  if (room.last_answer_result) {
    const result = room.last_answer_result;

    if (result.timed_out) {
      lastAnswerResult.textContent = `${result.answered_by} ficou sem tempo. Resposta correta: ${result.correct_answer}.`;
    } else if (result.is_correct) {
      lastAnswerResult.textContent = `${result.answered_by} acertou e ganhou ${result.points_earned} ponto(s).`;
    } else {
      lastAnswerResult.textContent = `${result.answered_by} errou. Resposta correta: ${result.correct_answer}.`;
    }
  } else {
    lastAnswerResult.textContent = "-";
  }
  if (isHost() && room.status === "waiting") {
    startGameButton.style.display = "inline-block";
  } else {
    startGameButton.style.display = "none";
  }
  gameMessage.textContent = getGameMessage(room);

  if (room.winner) {
    winnerText.textContent = `${room.winner.name} venceu com ${room.winner.score} pontos.`;
  } else {
    winnerText.textContent = "-";
  }

  if (room.status === "finished" && isHost()) {
    restartGameButton.style.display = "inline-block";
  } else {
    restartGameButton.style.display = "none";
  }
  if (isHost() && room.status === "waiting") {
    roomSettings.style.display = "block";
  } else {
    roomSettings.style.display = "none";
  }

  if (room.points_to_win) {
    pointsToWinInput.value = room.points_to_win;
  }
  if (room.question_time_limit) {
    questionTimeLimitInput.value = room.question_time_limit;
  }
  roomRules.textContent = `${room.points_to_win} pontos para vencer | ${room.question_time_limit}s por pergunta`;
  renderQuestionModal(room);
}

async function createRoom() {
  const hostName = hostNameInput.value.trim();

  if (!hostName) {
    alert("Digite o nome do host.");
    return;
  }

  const response = await fetch("/rooms", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      host_name: hostName,
    }),
  });

  if (!response.ok) {
    const message = await getErrorMessage(
      response,
      "Não foi possível criar a sala. Verifique o nome.",
    );

    alert(message);
    return;
  }
  const data = await response.json();

  currentPlayerId = data.player_id;
  connectWebSocket(data.room.code, data.session_token);
  saveSession(data.room.code, currentPlayerId, data.session_token);
  renderRoom(data.room);
}

async function joinRoom() {
  const playerName = playerNameInput.value.trim();
  const roomCode = joinRoomCodeInput.value.trim();

  if (!playerName) {
    alert("Digite seu nome.");
    return;
  }

  if (!roomCode) {
    alert("Digite o código da sala.");
    return;
  }

  const response = await fetch(`/rooms/${roomCode}/join`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      player_name: playerName,
    }),
  });

  if (!response.ok) {
    const message = await getErrorMessage(
      response,
      "Não foi possível entrar. Verifique o código ou use outro nome.",
    );

    alert(message);
    return;
  }

  const data = await response.json();

  currentPlayerId = data.player_id;
  connectWebSocket(data.room.code, data.session_token);
  saveSession(data.room.code, currentPlayerId, data.session_token);
  renderRoom(data.room);
}

async function startGame() {
  if (!currentRoom || !currentPlayerId) {
    alert("Crie ou entre em uma sala primeiro.");
    return;
  }

  const response = await fetch(`/rooms/${currentRoom.code}/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      player_id: currentPlayerId,
    }),
  });

  if (!response.ok) {
    const message = await getErrorMessage(
      response,
      "Apenas o host pode iniciar a partida.",
    );

    alert(message);
    return;
  }

  const room = await response.json();
  renderRoom(room);
}

async function selectTheme(theme) {
  if (!currentRoom || !currentPlayerId) {
    alert("Crie ou entre em uma sala primeiro.");
    return;
  }

  const response = await fetch(`/rooms/${currentRoom.code}/theme`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      player_id: currentPlayerId,
      theme: theme,
    }),
  });

  if (!response.ok) {
    const message = await getErrorMessage(
      response,
      "Não foi possível escolher esse tema. Verifique se é sua vez.",
    );

    alert(message);
    return;
  }

  const room = await response.json();
  renderRoom(room);
}

async function selectDifficulty(difficulty) {
  if (!roomConnection?.ready || !isCurrentPlayer() || difficultyRequest) {
    return;
  }

  const request = { connection: roomConnection, turnNumber: currentRoom.turn_number };
  difficultyRequest = request;
  setQuestionLoading(true);

  try {
    const response = await fetch(`/rooms/${request.connection.roomCode}/difficulty`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        player_id: currentPlayerId,
        difficulty: difficulty,
      }),
    });

    if (difficultyRequest !== request) {
      return;
    }

    if (!response.ok) {
      const message = await getErrorMessage(
        response,
        "Não foi possível escolher essa dificuldade.",
      );

      if (difficultyRequest === request) {
        alert(message);
      }
      return;
    }

    const room = await response.json();
    if (difficultyRequest === request) {
      renderRoom(room);
    }
  } catch {
    if (difficultyRequest === request && request.connection.ready) {
      alert("Não foi possível gerar a pergunta.");
    }
  } finally {
    if (difficultyRequest === request) {
      difficultyRequest = null;
      setQuestionLoading(false);
      if (currentRoom) {
        renderRoom(currentRoom);
      }
    }
  }
}

for (const button of difficultyButtons.querySelectorAll("button")) {
  button.addEventListener("click", () => {
    selectDifficulty(button.dataset.difficulty);
  });
}

async function answerQuestion(answer, questionId) {
  if (!canAnswerQuestion(currentRoom) || currentRoom.current_question.id !== questionId) {
    return;
  }

  const roomCode = currentRoom.code;
  isAnsweringQuestion = true;
  setAlternativeButtonsDisabled(true);
  regenerateQuestionButton.disabled = true;

  try {
    const response = await fetch(`/rooms/${roomCode}/answer`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        player_id: currentPlayerId,
        answer: answer,
        question_id: questionId,
      }),
    });

    if (!response.ok) {
      const message = await getErrorMessage(
        response,
        "Não foi possível responder. Verifique se é sua vez.",
      );

      alert(message);
      return;
    }

    const room = await response.json();
    if (currentRoom?.code === roomCode && currentRoom.current_question?.id === questionId) {
      renderRoom(room);
    }
  } finally {
    isAnsweringQuestion = false;
    setAlternativeButtonsDisabled(!canAnswerQuestion(currentRoom));
    regenerateQuestionButton.disabled = isQuestionRegenerating(currentRoom?.current_question);
  }
}

async function regenerateQuestion() {
  const room = currentRoom;
  const question = room?.current_question;
  if (
    !roomConnection?.ready ||
    !question ||
    room.status !== "playing" ||
    !isCurrentPlayer() ||
    question.regenerated ||
    isQuestionRegenerating(question) ||
    isAnsweringQuestion
  ) {
    return;
  }

  pendingRegenerationQuestionId = question.id;
  renderRoom(room);

  try {
    const response = await fetch(`/rooms/${room.code}/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: currentPlayerId, question_id: question.id }),
    });

    if (!response.ok) {
      alert(await getErrorMessage(response, "Não foi possível trocar a pergunta."));
      return;
    }

    const updatedRoom = await response.json();
    if (currentRoom?.code === room.code && currentRoom.current_question?.id === question.id) {
      renderRoom(updatedRoom);
    }
  } catch {
    alert("Não foi possível confirmar a troca da pergunta.");
  } finally {
    if (pendingRegenerationQuestionId === question.id) {
      pendingRegenerationQuestionId = null;
    }
    if (currentRoom?.code === room.code) {
      renderRoom(currentRoom);
    }
  }
}

function setRoomConnectionNotice(message) {
  roomConnectionNotice.textContent = message;
  roomConnectionNotice.hidden = !message;
  cancelRoomReconnectButton.hidden = !message || !roomConnection || Boolean(currentRoom);
}

function closeRoomConnection() {
  const connection = roomConnection;
  roomConnection = null;
  if (connection) {
    clearTimeout(connection.retryTimer);
    connection.socket?.close();
  }
}

function openRoomSocket(connection) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(
    `${protocol}://${window.location.host}/ws/${encodeURIComponent(connection.roomCode)}`,
  );
  connection.socket = socket;

  const syncTimer = setTimeout(() => {
    if (connection.socket === socket) {
      scheduleRoomReconnect(connection);
    }
  }, 10000);

  socket.addEventListener("open", () => {
    if (roomConnection === connection && connection.socket === socket) {
      socket.send(JSON.stringify({
        player_id: connection.playerId,
        session_token: connection.sessionToken,
      }));
    }
  });

  socket.addEventListener("close", (event) => {
    clearTimeout(syncTimer);
    if (roomConnection !== connection || connection.socket !== socket) {
      return;
    }

    if (event.code === 4404) {
      returnToLobby("A sala foi encerrada ou o servidor reiniciou.");
    } else if (event.code === 4403) {
      returnToLobby("Você não faz mais parte desta sala.");
    } else {
      scheduleRoomReconnect(connection);
    }
  });

  socket.addEventListener("message", (event) => {
    if (roomConnection !== connection || connection.socket !== socket) {
      return;
    }

    const message = JSON.parse(event.data);
    if (message.type === "room_closed") {
      returnToLobby("A sala foi encerrada.");
      return;
    }
    if (message.type !== "room_updated") {
      return;
    }

    if (!message.room.players.some((player) => player.id === connection.playerId)) {
      returnToLobby("Você não faz mais parte desta sala.");
      return;
    }

    clearTimeout(syncTimer);
    connection.ready = true;
    connection.retryDelay = 1000;
    setRoomConnectionNotice("");
    renderRoom(message.room);
  });
}

function scheduleRoomReconnect(connection) {
  if (roomConnection !== connection || connection.retryTimer !== null) {
    return;
  }

  const socket = connection.socket;
  connection.socket = null;
  connection.ready = false;
  socket?.close();
  setRoomConnectionNotice("Reconectando…");
  if (currentRoom) {
    renderRoom(currentRoom);
  }

  connection.retryTimer = setTimeout(() => {
    connection.retryTimer = null;
    if (roomConnection === connection) {
      openRoomSocket(connection);
    }
  }, connection.retryDelay);
  connection.retryDelay = Math.min(connection.retryDelay * 2, 10000);
}

function connectWebSocket(roomCode, sessionToken) {
  closeRoomConnection();
  roomConnection = {
    roomCode,
    playerId: currentPlayerId,
    sessionToken,
    socket: null,
    ready: false,
    retryTimer: null,
    retryDelay: 1000,
  };
  setRoomConnectionNotice("Conectando à sala…");
  openRoomSocket(roomConnection);
}

function getGameMessage(room) {
  if (!room) {
    return "Crie ou entre em uma sala para começar.";
  }

  if (room.status === "finished") {
    if (room.winner) {
      return `Fim de jogo! ${room.winner.name} venceu.`;
    }

    return "Fim de jogo.";
  }

  if (room.status === "waiting") {
    if (isHost()) {
      return "Aguardando jogadores. Inicie a partida quando todos estiverem prontos.";
    }

    return "Aguardando o host iniciar a partida.";
  }

  if (!room.current_player) {
    return "Aguardando um jogador se conectar.";
  }

  if (room.current_player.connection_status === "reconnecting") {
    return `${room.current_player.name} está reconectando.`;
  }

  if (!room.selected_theme) {
    if (isCurrentPlayer()) {
      return "Sua vez. Escolha um tema.";
    }

    return `${room.current_player.name} está escolhendo um tema.`;
  }

  if (!room.current_question) {
    if (isCurrentPlayer()) {
      return `Tema escolhido: ${room.selected_theme}. Escolha a dificuldade.`;
    }

    return `${room.current_player.name} escolheu ${room.selected_theme} e está escolhendo a dificuldade.`;
  }

  if (isCurrentPlayer()) {
    return "Responda a pergunta.";
  }

  return `${room.current_player.name} está respondendo a pergunta.`;
}

async function leaveRoom() {
  const connection = roomConnection;
  if (!connection) {
    return;
  }

  returnToLobby();
  try {
    const { roomCode, playerId, sessionToken } = connection;
    const response = await fetch(`/rooms/${roomCode}/leave`, {
      method: "POST",
      keepalive: true,
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        player_id: playerId,
        session_token: sessionToken,
      }),
    });

    if (!response.ok) {
      throw new Error("Falha ao avisar o servidor.");
    }
  } catch {
    if (!roomConnection) {
      setRoomConnectionNotice("Você saiu. O servidor não recebeu a saída.");
    }
  }
}

async function removePlayer(player, button) {
  const connection = roomConnection;
  if (!connection?.ready || !isHost() || player.id === currentPlayerId) {
    return;
  }
  if (!window.confirm(`Remover ${player.name} da sala?`)) {
    return;
  }

  button.disabled = true;
  try {
    const response = await fetch(`/rooms/${connection.roomCode}/kick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_id: connection.playerId,
        session_token: connection.sessionToken,
        target_player_id: player.id,
      }),
    });

    if (!response.ok) {
      alert(await getErrorMessage(response, "Não foi possível remover o jogador."));
      return;
    }

    const room = await response.json();
    if (roomConnection === connection) {
      renderRoom(room);
    }
  } catch {
    alert("Não foi possível remover o jogador.");
  } finally {
    button.disabled = !connection.ready;
  }
}

function returnToLobby(message = "") {
  closeRoomConnection();
  currentRoom = null;
  currentPlayerId = null;
  clearSession();
  difficultyRequest = null;
  setQuestionLoading(false);
  setRoomConnectionNotice(message);
  roomInviteFallback.hidden = true;
  questionModal.classList.remove("is-open");
  stopTimerDisplay();

  roomCodeElement.textContent = "-";
  playersList.innerHTML = "";
  roomStatus.textContent = "-";
  currentPlayer.textContent = "-";
  themesList.innerHTML = "";
  selectedTheme.textContent = "-";
  questionText.textContent = "-";
  alternativesList.innerHTML = "";
  lastAnswerResult.textContent = "-";
  gameMessage.textContent = "-";

  createRoomSection.style.display = "block";
  joinRoomSection.style.display = "block";
  roomSection.style.display = "none";
}

async function restartGame() {
  if (!currentRoom || !currentPlayerId) {
    alert("Você precisa estar em uma sala.");
    return;
  }

  const response = await fetch(`/rooms/${currentRoom.code}/restart`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      player_id: currentPlayerId,
    }),
  });

  if (!response.ok) {
    const message = await getErrorMessage(
      response,
      "Apenas o host pode reiniciar a partida.",
    );

    alert(message);
    return;
  }

  const room = await response.json();
  renderRoom(room);
}

function restoreSession() {
  const roomCode = localStorage.getItem("quizez_room_code");
  const playerId = localStorage.getItem("quizez_player_id");
  const sessionToken = localStorage.getItem("quizez_session_token");

  if (!roomCode || !playerId) {
    return;
  }
  if (!sessionToken) {
    returnToLobby("A sessão anterior expirou. Entre na sala novamente.");
    return;
  }

  currentPlayerId = playerId;
  connectWebSocket(roomCode.toUpperCase(), sessionToken);
}

async function copyRoomCode() {
  if (!currentRoom) {
    alert("Você ainda não está em uma sala.");
    return;
  }

  await navigator.clipboard.writeText(currentRoom.code);
  copyRoomCodeButton.textContent = "Copiado!";

  setTimeout(() => {
    copyRoomCodeButton.textContent = "Copiar código";
  }, 1500);
}

async function copyRoomLink() {
  const roomCode = currentRoom?.code;

  if (!roomCode) {
    return;
  }

  const inviteUrl = new URL(window.location.href);
  inviteUrl.search = "";
  inviteUrl.hash = "";
  inviteUrl.searchParams.set("room", roomCode);
  const link = inviteUrl.href;

  try {
    await navigator.clipboard.writeText(link);
  } catch {
    if (currentRoom?.code === roomCode) {
      roomInviteLink.value = link;
      roomInviteFallback.hidden = false;
      roomInviteLink.focus();
      roomInviteLink.select();
    }
    return;
  }

  if (currentRoom?.code !== roomCode) {
    return;
  }

  roomInviteFallback.hidden = true;
  copyRoomLinkButton.textContent = "Link copiado!";

  setTimeout(() => {
    copyRoomLinkButton.textContent = "Copiar link da sala";
  }, 1500);
}

function loadRoomInvite() {
  const params = new URLSearchParams(window.location.search);
  const roomCode = params.get("room")?.trim().toUpperCase();

  if (!/^[0-9A-F]{6}$/.test(roomCode)) {
    return;
  }

  joinRoomCodeInput.value = roomCode;
  playerNameInput.focus();
}

function stopTimerDisplay() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }

  activeTimerExpiresAt = null;
  timerText.textContent = "-";
  modalTimerText.textContent = "-";
}

function startTimerDisplay(expiresAt) {
  if (activeTimerExpiresAt === expiresAt) {
    return;
  }

  activeTimerExpiresAt = expiresAt;
  stopTimerDisplay();
  activeTimerExpiresAt = expiresAt;

  function updateTimer() {
    const expiresTime = new Date(expiresAt).getTime();
    const now = Date.now();
    const remaining = Math.max(0, Math.ceil((expiresTime - now) / 1000));

    timerText.textContent = `${remaining}s`;
    modalTimerText.textContent = `${remaining}s`;

    if (remaining <= 0) {
      clearInterval(timerInterval);
      timerInterval = null;
      timerText.textContent = "Tempo esgotado";
      modalTimerText.textContent = "0s";
    }
  }

  updateTimer();
  timerInterval = setInterval(updateTimer, 1000);
}

function renderQuestionModal(room) {
  const question = room.current_question;
  if (!roomConnection?.ready || !question || room.status !== "playing") {
    questionModal.classList.remove("is-open");
    modalCurrentPlayer.textContent = "-";
    modalQuestionText.textContent = "-";
    modalAlternativesList.innerHTML = "";
    regenerateQuestionButton.hidden = true;
    regenerateQuestionStatus.hidden = true;
    removeCurrentPlayerButton.hidden = true;
    return;
  }

  questionModal.classList.add("is-open");

  const pointsLabel = question.points === 1 ? "1 ponto" : `${question.points} pontos`;
  modalQuestionMeta.textContent = `${room.selected_theme} | ${room.selected_difficulty} | Vale ${pointsLabel}`;
  modalCurrentPlayer.textContent = room.current_player
    ? `Respondendo: ${room.current_player.name}`
    : "Respondendo: -";
  if (room.current_player?.connection_status === "reconnecting") {
    modalCurrentPlayer.textContent += " (reconectando)";
  }
  removeCurrentPlayerButton.hidden = !isHost() || !room.current_player || isCurrentPlayer();
  modalQuestionText.textContent = question.question;

  const regenerating = isQuestionRegenerating(question);
  regenerateQuestionButton.hidden = !isCurrentPlayer() || question.regenerated;
  regenerateQuestionButton.disabled = regenerating || isAnsweringQuestion;
  regenerateQuestionButton.textContent = question.points > 1
    ? "Trocar pergunta (-1 ponto)"
    : "Trocar pergunta";
  regenerateQuestionStatus.hidden = !regenerating;

  modalAlternativesList.innerHTML = "";

  for (const alternative of question.alternatives) {
    const item = document.createElement("li");
    const button = document.createElement("button");

    button.textContent = alternative;
    button.disabled = !canAnswerQuestion(room);
    button.addEventListener("click", () => answerQuestion(alternative, question.id));

    item.appendChild(button);
    modalAlternativesList.appendChild(item);
  }
}

function setQuestionLoading(isLoading) {
  setDifficultyButtonsDisabled(isLoading);
  questionLoadingText.style.display = isLoading ? "block" : "none";
}

async function saveRoomSettings() {
  if (!currentRoom || !currentPlayerId) {
    alert("Você precisa estar em uma sala.");
    return;
  }

  const pointsToWin = Number(pointsToWinInput.value);

  if (!Number.isInteger(pointsToWin) || pointsToWin < 1 || pointsToWin > 100) {
    alert("Os pontos para vencer precisam estar entre 1 e 100.");
    return;
  }

  const questionTimeLimit = Number(questionTimeLimitInput.value);

  if (
    !Number.isInteger(questionTimeLimit) ||
    questionTimeLimit < 5 ||
    questionTimeLimit > 180
  ) {
    alert("O tempo por pergunta precisa estar entre 5 e 180 segundos.");
    return;
  }

  const response = await fetch(`/rooms/${currentRoom.code}/settings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      player_id: currentPlayerId,
      points_to_win: pointsToWin,
      question_time_limit: questionTimeLimit,
    }),
  });

  if (!response.ok) {
    const message = await getErrorMessage(
      response,
      "Não foi possível salvar as configurações.",
    );

    alert(message);
    return;
  }

  const room = await response.json();
  renderRoom(room);
}

createRoomButton.addEventListener("click", createRoom);
joinRoomButton.addEventListener("click", joinRoom);
startGameButton.addEventListener("click", startGame);
leaveRoomButton.addEventListener("click", leaveRoom);
cancelRoomReconnectButton.addEventListener("click", leaveRoom);
restartGameButton.addEventListener("click", restartGame);
copyRoomCodeButton.addEventListener("click", copyRoomCode);
copyRoomLinkButton.addEventListener("click", copyRoomLink);
regenerateQuestionButton.addEventListener("click", regenerateQuestion);
removeCurrentPlayerButton.addEventListener("click", () => {
  if (currentRoom?.current_player) {
    removePlayer(currentRoom.current_player, removeCurrentPlayerButton);
  }
});
saveSettingsButton.addEventListener("click", saveRoomSettings);
window.addEventListener("offline", () => {
  if (roomConnection) {
    scheduleRoomReconnect(roomConnection);
  }
});
window.addEventListener("online", () => {
  const connection = roomConnection;
  if (connection && connection.retryTimer !== null) {
    clearTimeout(connection.retryTimer);
    connection.retryTimer = null;
    openRoomSocket(connection);
  }
});
loadRoomInvite();
restoreSession();
