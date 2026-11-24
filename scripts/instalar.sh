#!/usr/bin/env bash
# Instala o Editor GS em um Ubuntu (WSL2 ou nativo). Rode de dentro da pasta do projeto: bash scripts/instalar.sh
# O que faz: pacotes do sistema (ffmpeg, libs do Chromium do Remotion, fontes), uv + Python 3.14 no venv ~/.venvs/editor-gs,
# Node 24 (nvm), dependências do app e do Remotion, build do app. Não faz login em nada e não grava chave.
# Com EDITOR_GS_HOME (ou instalado como plugin do Claude Code), os dados ficam em ~/EditorGS (workspace, estado, logs, .env), fora do código.
set -euo pipefail
RAIZ="$(cd "$(cd "$(dirname "$0")" && pwd -P)/.." && pwd)"
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || [ "${1:-}" = "--plugin" ]; then export EDITOR_GS_HOME="${EDITOR_GS_HOME:-$HOME/EditorGS}"; fi
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"; [ -d "$HOME_GS" ] && export EDITOR_GS_HOME="$HOME_GS"
DADOS="${EDITOR_GS_HOME:-$RAIZ}"; mkdir -p "$DADOS"
[ -f "$DADOS/.env" ] && { set -a; . "$DADOS/.env"; set +a; } || true
VENV="${EDITOR_GS_VENV:-$HOME/.venvs/editor-gs}"
LOGDIR="${EDITOR_GS_HOME:+$EDITOR_GS_HOME/logs}"; LOGDIR="${LOGDIR:-$RAIZ/docs/logs}"; LOG="$LOGDIR/instalacao-$(date +%F).log"; mkdir -p "$LOGDIR"
exec > >(tee -a "$LOG") 2>&1
echo "== Editor GS: instalação em $(hostname) ($(date)) — código em $RAIZ, dados em $DADOS"

SO="$(uname -s)"
if [ "$SO" = "Darwin" ]; then
  # 24/11/2026: sem Homebrew (era o que mais demorava e pedia senha). ffmpeg pronto da nossa release e, mais abaixo, Node portátil,
  # os dois em ~/EditorGS/bin, onde o gateway e o MCP já procuram (servico/plataforma.py → pastas_bin).
  echo "== 1/6 ffmpeg (macOS, sem Homebrew)"
  BIN_MAC="${EDITOR_GS_HOME:-$HOME/EditorGS}/bin"; mkdir -p "$BIN_MAC"
  if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]; then
    echo "Este Mac tem processador Intel. O Editor GS precisa de um Mac com Apple Silicon (M1 ou mais novo)."; exit 1
  fi
  if [ ! -x "$BIN_MAC/ffmpeg/bin/ffmpeg" ] || [ ! -x "$BIN_MAC/ffmpeg/bin/ffprobe" ]; then
    URL_FF="${EDITOR_GS_FFMPEG_URL:-https://github.com/gravasimples/editor-gs-plugin/releases/download/ferramentas-mac/ffmpeg-macos-arm64.tar.gz}"
    TMPF="$(mktemp -d)"
    if curl -fL --retry 3 -o "$TMPF/ffmpeg.tar.gz" "$URL_FF" && mkdir -p "$BIN_MAC/ffmpeg/bin" && tar -xzf "$TMPF/ffmpeg.tar.gz" -C "$BIN_MAC/ffmpeg/bin"; then
      chmod +x "$BIN_MAC/ffmpeg/bin/ffmpeg" "$BIN_MAC/ffmpeg/bin/ffprobe"; xattr -dr com.apple.quarantine "$BIN_MAC/ffmpeg" 2>/dev/null || true
    else
      rm -rf "$BIN_MAC/ffmpeg"
      echo "   não consegui baixar o ffmpeg pronto; tentando pelo Homebrew"
      command -v brew >/dev/null 2>&1 || export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
      command -v brew >/dev/null 2>&1 && brew install ffmpeg >/dev/null || true
    fi
    rm -rf "$TMPF"
  fi
  [ -d "$BIN_MAC/ffmpeg/bin" ] && export PATH="$BIN_MAC/ffmpeg/bin:$PATH"
else
  if command -v ffmpeg >/dev/null 2>&1 && ! sudo -n true 2>/dev/null && [ -n "${EDITOR_GS_SEM_APT:-}" ]; then
    echo "== 1/6 pacotes do sistema: pulado (ffmpeg já existe e EDITOR_GS_SEM_APT está definido)"
  else
  echo "== 1/6 pacotes do sistema (Ubuntu/WSL, pede a senha do sudo)"
  sudo apt-get update -qq
  sudo apt-get install -y -qq ffmpeg git curl build-essential fonts-dejavu-core fonts-ubuntu \
    libgl1 libegl1 libgles2 libglvnd0 libglx0 libopengl0 libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2t64 libpango-1.0-0 libcairo2 libglib2.0-0t64 libportaudio2 2>/dev/null \
    || sudo apt-get install -y -qq ffmpeg git curl build-essential fonts-dejavu-core libgl1 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 libportaudio2
  fi
fi
command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg não foi instalado. Confira a internet e rode de novo."; exit 1; }
ffmpeg -version | head -1

echo "== 2/6 Python 3.14 (uv) e venv em $VENV"
if ! command -v uv >/dev/null 2>&1; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.14 >/dev/null
[ -d "$VENV" ] || uv venv --python 3.14 "$VENV"
uv pip install --python "$VENV/bin/python" -r "$RAIZ/requirements.txt"
if [ "$SO" != "Darwin" ] && command -v nvidia-smi >/dev/null 2>&1; then uv pip install --python "$VENV/bin/python" -r "$RAIZ/requirements-cuda.txt" || echo "(CUDA opcional não instalou; a transcrição usa CPU)"; fi
"$VENV/bin/python" -c "import faster_whisper, fastapi, mediapipe; print('python ok')"

if [ "$SO" = "Darwin" ]; then
  echo "== 3/6 Node 24 (portátil, em $BIN_MAC/node)"
  if [ ! -x "$BIN_MAC/node/bin/node" ]; then
    BASE_NODE="https://nodejs.org/dist/latest-v24.x"
    ARQ_NODE="$(curl -fsSL "$BASE_NODE/SHASUMS256.txt" | awk '/darwin-arm64\.tar\.gz$/{print $2; exit}')"
    [ -n "$ARQ_NODE" ] || { echo "Não consegui consultar o Node em nodejs.org. Confira a internet e rode de novo."; exit 1; }
    rm -rf "$BIN_MAC/node"; mkdir -p "$BIN_MAC/node"
    curl -fL --retry 3 "$BASE_NODE/$ARQ_NODE" | tar -xz -C "$BIN_MAC/node" --strip-components 1
  fi
  export PATH="$BIN_MAC/node/bin:$PATH"
  if [ ! -f "$DADOS/.env" ]; then if [ -f "$RAIZ/.env.exemplo" ]; then cp "$RAIZ/.env.exemplo" "$DADOS/.env"; else touch "$DADOS/.env"; fi; fi
  grep -q "^EDITOR_GS_NODE_BIN=" "$DADOS/.env" || echo "EDITOR_GS_NODE_BIN=$BIN_MAC/node/bin" >> "$DADOS/.env"
else
  echo "== 3/6 Node 24 (nvm)"
  export NVM_DIR="$HOME/.nvm"
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash; fi
  . "$NVM_DIR/nvm.sh"
  nvm install 24 >/dev/null && nvm use 24 >/dev/null && nvm alias default 24 >/dev/null
fi
node --version

echo "== 4/6 dependências do app e do Remotion"
# 24/11/2026: o Remotion vem ANTES do app (o pacote /editor/ do app compila com remotion/node_modules; no 1º Mac a ordem inversa quebrou),
# e o app só é compilado se o plugin não trouxe app/dist pronto. Versão nova do plugin aproveita o node_modules da pasta anterior.
if case "$RAIZ" in */plugins/cache/*) true;; *) false;; esac && [ ! -d "$RAIZ/remotion/node_modules" ]; then
  for ANT in "$RAIZ"/../*/remotion/node_modules; do
    if [ -d "$ANT" ]; then mv "$ANT" "$RAIZ/remotion/node_modules" && echo "   remotion/node_modules ← versão anterior" && break; fi
  done
fi
(cd "$RAIZ/remotion" && npm install --no-audit --no-fund && npx remotion browser ensure)
if [ -f "$RAIZ/app/dist/index.html" ] && [ -f "$RAIZ/app/dist/editor/index.html" ]; then
  echo "   app/dist já veio pronto (mantido)"
else
  (cd "$RAIZ/app" && npm install --no-audit --no-fund && npm run build)
fi

echo "== 5/6 pastas de trabalho e .env"
WS="$DADOS/workspace"
mkdir -p "$WS/entrada" "$WS/saida" "$WS/_trabalho" "$WS/referencias" "$WS/materiais" "$WS/clipes" "$WS/banco" "$DADOS/trilhas"
if [ -n "${EDITOR_GS_HOME:-}" ]; then mkdir -p "$EDITOR_GS_HOME/estado" "$EDITOR_GS_HOME/logs"; [ -f "$WS/AGENTS.md" ] || cp "$RAIZ/workspace/AGENTS.md" "$WS/AGENTS.md"; fi
if [ ! -f "$DADOS/.env" ]; then if [ -f "$RAIZ/.env.exemplo" ]; then cp "$RAIZ/.env.exemplo" "$DADOS/.env"; else touch "$DADOS/.env"; fi; fi
grep -q "^EDITOR_GS_VENV=" "$DADOS/.env" || echo "EDITOR_GS_VENV=$VENV" >> "$DADOS/.env"
cat > "$WS/.mcp.json" <<JSON
{
    "mcpServers": {
        "editor-de-video": {
            "command": "bash",
            "args": ["$RAIZ/mcp/editor-de-video/servidor.sh"]
        }
    }
}
JSON
cksum < "$RAIZ/requirements.txt" > "$DADOS/requirements.sum" 2>/dev/null || true
chmod +x "$RAIZ"/servico/rodar.sh "$RAIZ"/mcp/editor-de-video/servidor.sh "$RAIZ"/mcp/editor-gs/servidor.sh "$RAIZ"/scripts/*.sh

# 24/11/2026 (macOS, modo plugin): atalho estável ~/EditorGS/bin/editor-gs (acha a versão mais nova do plugin) e início automático no login,
# para a pessoa não depender de abrir o Terminal depois de reiniciar.
if [ "$SO" = "Darwin" ] && case "$RAIZ" in */plugins/cache/*) true;; *) false;; esac; then
  cat > "$BIN_MAC/editor-gs" <<'ATALHO'
#!/bin/bash
# Atalho do Editor GS: roda o comando na versão mais nova do plugin. Uso: ~/EditorGS/bin/editor-gs [subir|parar|status|abrir|garantir]
R="$(ls -d "$HOME"/.claude/plugins/cache/editor-gs/editor-gs/*/scripts/editor-gs.sh 2>/dev/null | sort -V | tail -1)"
[ -n "$R" ] || { echo "Editor GS não encontrado. Rode o instalador de novo."; exit 1; }
exec /bin/bash "$R" "${1:-subir}" "${@:2}"
ATALHO
  chmod +x "$BIN_MAC/editor-gs"
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$HOME/Library/LaunchAgents/br.com.gravasimples.editor-gs.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>br.com.gravasimples.editor-gs</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$BIN_MAC/editor-gs</string><string>garantir</string></array>
  <key>RunAtLoad</key><true/>
  <key>AbandonProcessGroup</key><true/>
  <key>StandardOutPath</key><string>$DADOS/logs/inicio-automatico.log</string>
  <key>StandardErrorPath</key><string>$DADOS/logs/inicio-automatico.log</string>
</dict></plist>
PLIST
  echo "   início automático no login: ligado (~/Library/LaunchAgents/br.com.gravasimples.editor-gs.plist)"
fi

echo "== 6/6 conferência"
command -v claude >/dev/null 2>&1 && claude --version || echo "AVISO: Claude Code não está no PATH. Instale: curl -fsSL https://claude.ai/install.sh | bash  e depois  claude login"
"$VENV/bin/python" -I "$RAIZ/testes/teste_gateway_acesso.py" | tail -1
"$VENV/bin/python" -c "import sys; sys.path.insert(0, '$RAIZ'); from servico import caminhos; print(caminhos.garantir())"
[ -n "${EDITOR_GS_HOME:-}" ] && [ ! -f "$EDITOR_GS_HOME/estado/config.local.json" ] && printf '{\n  "executor": {"modo": "local"}\n}\n' > "$EDITOR_GS_HOME/estado/config.local.json"
echo "== pronto. Próximo passo: bash scripts/subir.sh (sobe o app em http://localhost:3200; o Claude Code logado nesta máquina é o motor). Log: $LOG"
