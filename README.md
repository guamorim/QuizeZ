# quiZeZ

Quiz multiplayer em português para jogar com amigos pelo navegador. O host cria uma sala, compartilha o código ou o link de convite e inicia a partida. Cada jogador entra só com um nome.

O servidor usa Python e FastAPI. A interface Arcade usa React, Vite e CSS, e as atualizações da sala chegam por WebSocket. As perguntas podem ser geradas pelo Ollama local ou vir de um modo de demonstração.

## Como jogar

1. Crie uma sala e envie o código ou use **Copiar link da sala**. O convite preenche o código no formulário de entrada.
2. Antes de começar, o host pode ajustar a meta de pontos e o tempo de resposta. O primeiro jogador é sorteado entre os conectados.
3. Na sua vez, escolha um dos cinco temas sorteados e depois a dificuldade. Quando a pergunta aparecer, selecione uma das quatro alternativas antes que o tempo acabe.
4. Ao acertar, você ganha os pontos da pergunta. Um erro ou o fim do tempo vale zero, e a vez passa adiante.
5. Quem atingir a meta vence. A classificação final aparece na sala, e o host pode iniciar uma nova partida com o placar zerado.

### Pontuação

| Dificuldade | Acerto na pergunta original | Acerto após trocar a pergunta |
| --- | ---: | ---: |
| Fácil | 1 | 1 |
| Médio | 2 | 1 |
| Difícil | 3 | 2 |

O jogador da vez pode trocar a própria pergunta uma vez. A troca mantém o tema e a dificuldade, reinicia o timer e desconta um ponto do valor da pergunta, com mínimo de um ponto. Se a geração falhar, o jogo volta à pergunta anterior com o tempo que restava e mantém a troca disponível.

O tempo padrão é de **30 segundos** (ajustável de 5 a 180) e a meta padrão é de **25 pontos** (ajustável de 1 a 100). O servidor controla o prazo, que começa quando a pergunta fica pronta. No placar, jogadores empatados dividem a posição, por exemplo `1º`, `1º`, `3º`.

### Conexão e controle da sala

- Quem chega com a partida em andamento entra no fim da fila.
- Ao detectar uma queda do jogador da vez, o servidor dá até **10 segundos** para ele voltar. Se a pergunta vencer pelo timer antes disso, a partida segue normalmente.
- Jogadores offline ficam fora da rotação enquanto estiverem desconectados. Ao reconectar, recuperam o estado atual da sala e a pontuação. Se todos caírem, a partida aguarda alguém voltar.
- O host pode remover outro jogador online ou offline após confirmar pelo nome. Quem for removido volta ao lobby. Se estava na vez, o turno passa para o próximo conectado.

## Rodar localmente

Use **Python 3.11 ou superior**, **Node.js 22.12 ou superior** para compilar o Arcade e um navegador. O Ollama é opcional e só é necessário para gerar perguntas por IA.

Na raiz do projeto, crie o ambiente virtual e instale as dependências.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Linux e macOS**

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

### Configurar as perguntas

O modo padrão é `fake`, com perguntas de exemplo. Você pode usá-lo sem arquivo `.env` para testar salas, turnos, pontuação e reconexão.

Para gerar perguntas por IA, instale o [Ollama](https://docs.ollama.com/windows), deixe o serviço local em execução e baixe o modelo padrão. Consulte a [referência da CLI](https://docs.ollama.com/cli) e a [página do modelo](https://ollama.com/library/llama3.1:8b).

```text
ollama pull llama3.1:8b
```

Na raiz do projeto, configure um arquivo local `.env` com estes valores.

```dotenv
QUESTION_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
```

O backend chama o Ollama em `http://localhost:11434/api/generate`. Ele valida a estrutura da pergunta, embaralha as alternativas e usa as últimas dez perguntas como contexto para reduzir repetições. Se o Ollama falhar ao gerar uma pergunta inicial, o jogo pode usar uma pergunta de exemplo. Para voltar ao modo de demonstração, use `QUESTION_PROVIDER=fake` e reinicie o servidor.

### Compilar o Arcade

Na raiz do projeto, instale as dependências do frontend e gere os arquivos que o FastAPI vai servir.

**Windows (PowerShell)**

```powershell
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
```

**Linux e macOS**

```bash
npm --prefix frontend ci
npm --prefix frontend run build
```

O build fica em `static/react/`. Execute o build novamente após alterar o código React.

### Iniciar o servidor

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**Linux e macOS**

```bash
./.venv/bin/python -m uvicorn app.main:app --reload
```

Abra o [Arcade](http://127.0.0.1:8000/) no navegador. Os convites abrem esse endereço com o código da sala preenchido. Convites antigos que usam `/static/index.html` redirecionam para o Arcade. Se o build estiver ausente, a página mostra os comandos de compilação.

A [documentação da API](http://127.0.0.1:8000/docs) e o [status do servidor](http://127.0.0.1:8000/health) têm endereços próprios. Use `Ctrl+C` para parar.

## Estrutura do projeto

| Arquivo | Responsabilidade |
| --- | --- |
| [`app/main.py`](app/main.py) | Rotas HTTP, arquivos estáticos, WebSocket e timers do servidor |
| [`app/game_functions.py`](app/game_functions.py) | Estado das salas, ordem dos turnos, regras e pontuação |
| [`app/ai_questions.py`](app/ai_questions.py) | Geração, validação e embaralhamento de perguntas |
| [`frontend/src/`](frontend/src/) | Lobby Arcade, turnos, popup, placar e sessão React |
| [`frontend/vite.config.js`](frontend/vite.config.js) | Build do Arcade e proxy de desenvolvimento para o FastAPI |
| [`requirements.txt`](requirements.txt) | FastAPI, Uvicorn com suporte a WebSocket, python-dotenv e Requests |

O navegador envia ações por HTTP e recebe o estado da sala pelo WebSocket em `/ws/{room_code}`. Ao reconectar, a sessão identifica o mesmo jogador e o servidor envia o estado atual. As salas ficam na memória de **um processo** do servidor. Reiniciar o processo encerra as partidas abertas.

O endereço `127.0.0.1` funciona apenas no próprio computador. Para jogar de outros dispositivos, abra o jogo por um endereço acessível a todos e que encaminhe também o WebSocket. Os convites usam o endereço pelo qual você abriu o jogo.

## Teste manual

1. Use um navegador normal e uma janela anônima, ou perfis separados, para simular jogadores com sessões independentes.
2. Crie uma sala, copie o convite e entre na outra janela digitando só o nome.
3. Troque uma pergunta difícil e confira se o acerto soma dois pontos.
4. Coloque a janela do jogador da vez em modo offline antes de escolher o tema. Após o prazo de reconexão, confira se o turno avança e se o jogador recupera a sessão ao voltar.
5. No host, cancele uma confirmação de remoção e confirme outra. Verifique se o jogador removido volta ao lobby.
6. Termine a partida, confira a classificação final e inicie uma nova para verificar se o placar zera.

## Problemas comuns

- **O navegador não conecta à sala.** Abra o jogo pelo endereço do Uvicorn e confira se as dependências foram instaladas com `requirements.txt`. O pacote `uvicorn[standard]` inclui o suporte a WebSocket.
- **Só aparecem perguntas de exemplo.** Confira `QUESTION_PROVIDER=ollama`, o nome em `OLLAMA_MODEL` e se o Ollama está rodando. O terminal do servidor mostra as falhas de geração.
- **Uma mudança na interface não apareceu.** Recarregue com `Ctrl+F5` para buscar os arquivos estáticos atualizados.
