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

O backend chama o Ollama em `http://localhost:11434/api/generate`. Ele valida a estrutura da pergunta, embaralha as alternativas e usa as últimas dez perguntas como contexto para reduzir repetições. Se as três tentativas de gerar a pergunta falharem, o jogador da vez pode clicar em **Tentar novamente** sem mudar o tema, a dificuldade ou a pontuação. O timer só começa quando a pergunta fica pronta. Para usar perguntas de exemplo, configure `QUESTION_PROVIDER=fake` e reinicie o servidor.

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

## Vercel Services

O [Vercel Services](https://vercel.com/docs/services) compila o React e o FastAPI separadamente. O serviço `frontend` serve a interface na raiz do domínio. O serviço `app` recebe `/rooms`, `/rooms/*`, `/ws/*`, `/health` e o redirecionamento de convites antigos em `/static/index.html`. O navegador usa caminhos relativos nesse mesmo domínio, sem bindings internos.

Para testar o roteamento localmente no Windows, instale as dependências das duas partes conforme os passos acima. Na raiz do repositório, com o ambiente Python ativo, rode:

```powershell
npx.cmd vercel@latest dev --local
```

Se o CLI no Windows falhar com `Cannot find module '@vercel/python/package.json'`, o teste local também foi validado com `npx.cmd vercel@60.1.3 dev --local`.

Abra a URL que o CLI mostrar. Confira a tela inicial, `/health` e o convite de uma sala em outra janela. Esse teste local pode usar o Ollama da sua máquina ou o modo `fake`.

### Configurar o Redis

Sem `REDIS_URL`, o modo local usa a memória de um processo. Para rodar em múltiplas instâncias, conecte [Upstash Redis](https://vercel.com/marketplace/upstash) ao projeto. No painel do Redis, copie a URL da seção **Connect > TCP** e configure-a em `REDIS_URL` no ambiente do FastAPI. Use a URL `rediss://...`, com TLS; a URL HTTPS do REST não funciona nesse campo. Se a integração já fornecer a URL TCP em `KV_URL`, o backend também aceita esse nome.

Nunca coloque a URL no Git nem em variáveis com prefixo `VITE_`. O backend separa as salas locais, de preview e de produção pelo prefixo das chaves. Use bancos separados por ambiente ou defina `ROOM_STORE_PREFIX` para isolar um ambiente de teste no mesmo banco.

O Redis guarda salas, sessões e prazos e notifica os WebSockets em todas as instâncias. As salas expiram após seis horas sem alterações; conexões ativas renovam o prazo de armazenamento. Se o último WebSocket cair sem aviso, o servidor detecta a queda quando vencer a presença da conexão. Depois disso valem os dez segundos para reconectar.

Para validar antes de publicar, instale a dependência nova com `pip install -r requirements.txt`, coloque a URL TCP no `.env` local e inicie o servidor. `/health` deve mostrar `"room_store": "redis"`. Jogue com duas janelas e confira se o turno avança ao deixar o timer vencer. Para provar que o estado é compartilhado, inicie outro Uvicorn na porta `8001` com o mesmo `.env`, crie a sala na porta `8000` e entre na sala pelo código na porta `8001`. Criação, pontuação e reconexão devem aparecer nas duas janelas. [WebSockets na Vercel](https://vercel.com/docs/functions/websockets#manage-persistent-state)

**Antes de publicar:** configure o Redis na Vercel e valide uma partida completa com o Ollama acessado pelo túnel abaixo. Não envie o `.env` local nem exponha a porta do Ollama diretamente.

### Usar o Ollama do PC com a Vercel

O FastAPI usa `http://localhost:11434` por padrão. Para o FastAPI na Vercel acessar o modelo no seu PC, mantenha o Ollama escutando apenas em `127.0.0.1:11434` e use um túnel HTTPS autenticado.

1. [Instale o ngrok e configure o token da sua conta](https://ngrok.com/docs/gateway/endpoints/agent-cli-quickstart). Esse token é do agente e fica no PC.
2. Na raiz do projeto, crie `ngrok-ollama.local.yml` com a política abaixo. Antes de iniciar o túnel, troque `SENHA_ALEATORIA_AQUI` por uma senha longa e única. Por exemplo, gere uma com `node -e "console.log(require('node:crypto').randomBytes(24).toString('hex'))"`. Esse arquivo é ignorado pelo Git e pela Vercel.

```yaml
on_http_request:
  - expressions:
      - "req.url.scheme != 'https' || req.method != 'POST' || req.url.path != '/api/generate'"
    actions:
      - type: deny
        config:
          status_code: 403
  - actions:
      - type: basic-auth
        config:
          credentials:
            - "quizez:SENHA_ALEATORIA_AQUI"
      - type: remove-headers
        config:
          headers: [authorization]
      - type: add-headers
        config:
          headers:
            host: "localhost:11434"
```

A política restringe o acesso à [geração de texto](https://docs.ollama.com/api/generate), exige [Basic Auth](https://ngrok.com/docs/gateway/traffic-policy/actions/basic-auth) e ajusta o cabeçalho `Host` para o Ollama local.

3. Com o Ollama em execução, inicie o ngrok com a política. Não inicie o túnel sem a política.

```powershell
ngrok http http://127.0.0.1:11434 --traffic-policy-file ngrok-ollama.local.yml --inspect=false
```

4. Antes de usar o túnel, confirme que um `POST /api/generate` sem credenciais retorna `401` e que `GET /api/tags` retorna `403`. Se o teste não bloquear o acesso, pare o túnel e confira a política.
5. No ambiente do FastAPI, configure as variáveis abaixo. Use seu endereço HTTPS, sem `/api/generate`, e a mesma senha da política. Para testar antes de publicar, use o `.env` local e reinicie o FastAPI. No deploy, configure essas variáveis no painel da Vercel. Nunca use o prefixo `VITE_` para as credenciais.

```dotenv
QUESTION_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
OLLAMA_BASE_URL=https://seu-endereco.ngrok-free.dev
OLLAMA_TUNNEL_USER=quizez
OLLAMA_TUNNEL_PASSWORD=SENHA_ALEATORIA_AQUI
```

Crie uma sala e escolha uma dificuldade para confirmar que a pergunta chega. O PC, o Ollama e o ngrok precisam ficar ligados durante a partida. Para voltar ao acesso direto no mesmo PC, remova as três variáveis `OLLAMA_BASE_URL`, `OLLAMA_TUNNEL_USER` e `OLLAMA_TUNNEL_PASSWORD`.

## Estrutura do projeto

| Arquivo | Responsabilidade |
| --- | --- |
| [`app/main.py`](app/main.py) | Rotas HTTP, arquivos estáticos, WebSocket e timers do servidor |
| [`app/game_functions.py`](app/game_functions.py) | Estado das salas, ordem dos turnos, regras e pontuação |
| [`app/room_store.py`](app/room_store.py) | Armazenamento em memória ou Redis, alterações atômicas e avisos de atualização |
| [`app/ai_questions.py`](app/ai_questions.py) | Geração, validação e embaralhamento de perguntas |
| [`frontend/src/`](frontend/src/) | Lobby Arcade, turnos, popup, placar e sessão React |
| [`frontend/vite.config.js`](frontend/vite.config.js) | Build do Arcade e proxy de desenvolvimento para o FastAPI |
| [`requirements.txt`](requirements.txt) | FastAPI, Uvicorn com suporte a WebSocket, python-dotenv e Requests |

O navegador envia ações por HTTP e recebe o estado da sala pelo WebSocket em `/ws/{room_code}`. O servidor emite um token ao criar a sala ou entrar nela. O navegador usa esse token nas ações de jogo e ao reconectar, sem precisar de uma conta. Sem Redis, reiniciar o servidor encerra as partidas abertas. Com Redis, o estado fica acessível a outros processos e os prazos são aplicados na próxima atualização ou consulta à sala.

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
- **Não foi possível gerar a pergunta.** Confira se o Ollama está rodando e se o modelo em `OLLAMA_MODEL` está disponível. O terminal do servidor mostra as falhas de geração. Depois de resolver o problema, clique em **Tentar novamente** no seu turno.
- **Uma mudança na interface não apareceu.** Recarregue com `Ctrl+F5` para buscar os arquivos estáticos atualizados.
