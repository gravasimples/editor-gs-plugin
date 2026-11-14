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
  echo "== 1/6 pacotes do sistema (macOS, Homebrew)"
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew não encontrado. Instale primeiro (cola no Terminal e segue as instruções da tela):"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'; exit 1
  fi
  eval "$(brew shellenv)"
  brew install ffmpeg portaudio git curl >/dev/null || true
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
ffmpeg -version | head -1

echo "== 2/6 Python 3.14 (uv) e venv em $VENV"
if ! command -v uv >/dev/null 2>&1; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi
export PATH="$HOME/.local/bin:$PATH"
[ "$SO" = "Darwin" ] && export PATH="/opt/homebrew/bin:$PATH"
uv python install 3.14 >/dev/null
[ -d "$VENV" ] || uv venv --python 3.14 "$VENV"
uv pip install --python "$VENV/bin/python" -r "$RAIZ/requirements.txt"
if [ "$SO" != "Darwin" ] && command -v nvidia-smi >/dev/null 2>&1; then uv pip install --python "$VENV/bin/python" -r "$RAIZ/requirements-cuda.txt" || echo "(CUDA opcional não instalou; a transcrição usa CPU)"; fi
"$VENV/bin/python" -c "import faster_whisper, fastapi, mediapipe; print('python ok')"

echo "== 3/6 Node 24 (nvm)"
export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash; fi
. "$NVM_DIR/nvm.sh"
nvm install 24 >/dev/null && nvm use 24 >/dev/null && nvm alias default 24 >/dev/null
node --version

echo "== 4/6 dependências do app e do Remotion"
(cd "$RAIZ/app" && npm install --no-audit --no-fund && npm run build)
(cd "$RAIZ/remotion" && npm install --no-audit --no-fund && npx remotion browser ensure)

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
            "command": "$RAIZ/mcp/editor-de-video/servidor.sh",
            "args": []
        }
    }
}
JSON
chmod +x "$RAIZ"/servico/rodar.sh "$RAIZ"/mcp/editor-de-video/servidor.sh "$RAIZ"/mcp/editor-gs/servidor.sh "$RAIZ"/scripts/*.sh

echo "== 6/6 conferência"
command -v claude >/dev/null 2>&1 && claude --version || echo "AVISO: Claude Code não está no PATH. Instale: curl -fsSL https://claude.ai/install.sh | bash  e depois  claude login"
"$VENV/bin/python" -I "$RAIZ/testes/teste_gateway_acesso.py" | tail -1
"$VENV/bin/python" -c "import sys; sys.path.insert(0, '$RAIZ'); from servico import caminhos; print(caminhos.garantir())"
[ -n "${EDITOR_GS_HOME:-}" ] && [ ! -f "$EDITOR_GS_HOME/estado/config.local.json" ] && printf '{\n  "executor": {"modo": "local"}\n}\n' > "$EDITOR_GS_HOME/estado/config.local.json"
echo "== pronto. Próximo passo: bash scripts/subir.sh (sobe o app em http://localhost:3200; o Claude Code logado nesta máquina é o motor). Log: $LOG"
