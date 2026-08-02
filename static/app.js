let currentRoom = null;
let currentPlayerId = null;
let roomSocket = null;
let timerInterval = null;
let activeTimerExpiresAt = null;
let isGeneratingQuestion = false;
let isAnsweringQuestion = false;

function isHost() {
  return currentRoom && currentRoom.host_id === currentPlayerId;
}

function isCurrentPlayer() {
  return currentRoom && currentRoom.current_player?.id === currentPlayerId;
}

function saveSession(roomCode, playerId) {
  localStorage.setItem("quizez_room_code", roomCode);
  localStorage.setItem("quizez_player_id", playerId);
}

function clearSession() {
  localStorage.removeItem("quizez_room_code");
  localStorage.removeItem("quizez_player_id");
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
const playersList = document.getElementById("playersList");
const playerNameInput = document.getElementById("playerNameInput");
const joinRoomCodeInput = document.getElementById("joinRoomCodeInput");
const joinRoomButton = document.getElementById("joinRoomButton");
const startGameButton = document.getElementById("startGameButton");
const roomStatus = document.getElementById("roomStatus");
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
const timerText = document.getElementById("timerText");
const questionModal = document.getElementById("questionModal");
const modalQuestionMeta = document.getElementById("modalQuestionMeta");
const modalTimerText = document.getElementById("modalTimerText");
const modalQuestionText = document.getElementById("modalQuestionText");
const modalAlternativesList = document.getElementById("modalAlternativesList");
const modalCurrentPlayer = document.getElementById("modalCurrentPlayer");
const questionLoadingText = document.getElementById("questionLoadingText");
const roomSettings = document.getElementById("roomSettings");
const pointsToWinInput = document.getElementById("pointsToWinInput");
const saveSettingsButton = document.getElementById("saveSettingsButton");
const questionTimeLimitInput = document.getElementById(
  "questionTimeLimitInput",
);
const roomRules = document.getElementById("roomRules");

function renderRoom(room) {
  currentRoom = room;
  createRoomSection.style.display = "none";
  joinRoomSection.style.display = "none";
  roomSection.style.display = "block";

  roomCodeElement.textContent = room.code;

  playersList.innerHTML = "";

  for (const player of room.players) {
    const item = document.createElement("li");
    item.textContent = `${player.name} - ${player.score} pontos`;

    if (player.is_host) {
      item.textContent += " (host)";
    }

    playersList.appendChild(item);
  }

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
    room.status === "playing" && isCurrentPlayer() && !room.selected_theme;

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
    room.status === "playing" &&
    isCurrentPlayer() &&
    room.selected_theme &&
    !room.current_question &&
    !isGeneratingQuestion;

  if (canChooseDifficulty) {
    difficultyButtons.style.display = "block";
  } else {
    difficultyButtons.style.display = "none";
  }

  if (room.current_question) {
    questionText.textContent = room.current_question.question;

    alternativesList.innerHTML = "";

    for (const alternative of room.current_question.alternatives) {
      const item = document.createElement("li");
      const button = document.createElement("button");

      button.textContent = alternative;
      button.disabled = room.status !== "playing" || !isCurrentPlayer();
      button.addEventListener("click", () => answerQuestion(alternative));

      item.appendChild(button);
      alternativesList.appendChild(item);
    }
  } else {
    questionText.textContent = "-";
    alternativesList.innerHTML = "";
  }
  if (room.current_question?.expires_at && room.status === "playing") {
    startTimerDisplay(room.current_question.expires_at);
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
  connectWebSocket(data.room.code);
  saveSession(data.room.code, currentPlayerId);
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
  connectWebSocket(data.room.code);
  saveSession(data.room.code, currentPlayerId);
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
  if (!currentRoom || !currentPlayerId) {
    alert("Crie ou entre em uma sala primeiro.");
    return;
  }

  if (isGeneratingQuestion) {
    return;
  }

  setQuestionLoading(true);

  try {
    const response = await fetch(`/rooms/${currentRoom.code}/difficulty`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        player_id: currentPlayerId,
        difficulty: difficulty,
      }),
    });

    if (!response.ok) {
      const message = await getErrorMessage(
        response,
        "Não foi possível escolher essa dificuldade.",
      );

      alert(message);
      return;
    }

    const room = await response.json();
    renderRoom(room);
  } finally {
    setQuestionLoading(false);
  }
}

for (const button of difficultyButtons.querySelectorAll("button")) {
  button.addEventListener("click", () => {
    selectDifficulty(button.dataset.difficulty);
  });
}

async function answerQuestion(answer) {
  if (!currentRoom || !currentPlayerId) {
    alert("Crie ou entre em uma sala primeiro.");
    return;
  }

  if (isAnsweringQuestion) {
    return;
  }

  isAnsweringQuestion = true;
  setAlternativeButtonsDisabled(true);

  try {
    const response = await fetch(`/rooms/${currentRoom.code}/answer`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        player_id: currentPlayerId,
        answer: answer,
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
    renderRoom(room);
  } finally {
    isAnsweringQuestion = false;
    setAlternativeButtonsDisabled(false);
  }
}

function connectWebSocket(roomCode) {
  if (roomSocket) {
    roomSocket.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  roomSocket = new WebSocket(
    `${protocol}://${window.location.host}/ws/${roomCode}`,
  );

  roomSocket.addEventListener("open", () => {
    console.log("WebSocket conectado.");
  });

  roomSocket.addEventListener("close", () => {
    console.log("WebSocket desconectado.");
  });

  roomSocket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "room_updated") {
      renderRoom(message.room);
    }
  });
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
    return "Aguardando jogador da vez.";
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
  const roomCode = currentRoom?.code;
  const playerId = currentPlayerId;

  if (roomCode && playerId) {
    const response = await fetch(`/rooms/${roomCode}/leave`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        player_id: playerId,
      }),
    });

    if (!response.ok) {
      const message = await getErrorMessage(
        response,
        "Não foi possível sair da sala.",
      );

      alert(message);
      return;
    }
  }

  if (roomCode && playerId) {
    await fetch(`/rooms/${roomCode}/leave`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        player_id: playerId,
      }),
    });
  }

  if (roomSocket) {
    roomSocket.close();
    roomSocket = null;
  }

  currentRoom = null;
  currentPlayerId = null;
  clearSession();

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

async function restoreSession() {
  const roomCode = localStorage.getItem("quizez_room_code");
  const playerId = localStorage.getItem("quizez_player_id");

  if (!roomCode || !playerId) {
    return;
  }

  const response = await fetch(`/rooms/${roomCode}`);

  if (!response.ok) {
    clearSession();
    return;
  }

  const room = await response.json();

  const playerStillExists = room.players.some(
    (player) => player.id === playerId,
  );

  if (!playerStillExists) {
    clearSession();
    return;
  }

  currentPlayerId = playerId;
  renderRoom(room);
  connectWebSocket(room.code);
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
  if (!room.current_question || room.status !== "playing") {
    questionModal.classList.remove("is-open");
    modalCurrentPlayer.textContent = "-";
    modalQuestionText.textContent = "-";
    modalAlternativesList.innerHTML = "";
    return;
  }

  questionModal.classList.add("is-open");

  modalQuestionMeta.textContent = `${room.selected_theme} | ${room.selected_difficulty}`;
  modalCurrentPlayer.textContent = room.current_player
    ? `Respondendo: ${room.current_player.name}`
    : "Respondendo: -";
  modalQuestionText.textContent = room.current_question.question;

  modalAlternativesList.innerHTML = "";

  for (const alternative of room.current_question.alternatives) {
    const item = document.createElement("li");
    const button = document.createElement("button");

    button.textContent = alternative;
    button.disabled = room.status !== "playing" || !isCurrentPlayer();
    button.addEventListener("click", () => answerQuestion(alternative));

    item.appendChild(button);
    modalAlternativesList.appendChild(item);
  }
}

function setQuestionLoading(isLoading) {
  isGeneratingQuestion = isLoading;
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
restartGameButton.addEventListener("click", restartGame);
restoreSession();
copyRoomCodeButton.addEventListener("click", copyRoomCode);
saveSettingsButton.addEventListener("click", saveRoomSettings);
// teste2//
