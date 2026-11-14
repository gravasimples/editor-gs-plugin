#!/usr/bin/env bash
# Instala o HyperFrames (teste integrado, 10/11/2026) só na pasta hyperframes/ do repo: nada global, não entra no instalador padrão.
# Precisa de Node 22+ (EDITOR_GS_NODE_BIN, nvm ou PATH), FFmpeg e um Chrome/Chromium (HYPERFRAMES_BROWSER_PATH aponta um, se preciso).
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
if [ -n "${EDITOR_GS_NODE_BIN:-}" ]; then export PATH="$EDITOR_GS_NODE_BIN:$PATH"; fi
if ! command -v npm >/dev/null 2>&1; then
  ULT="$(ls -d "$HOME"/.nvm/versions/node/v*/bin 2>/dev/null | sort -V | tail -n1 || true)"
  [ -n "$ULT" ] && export PATH="$ULT:$PATH"
fi
command -v npm >/dev/null 2>&1 || { echo "npm não encontrado (Node 22+)."; exit 1; }
cd "$RAIZ/hyperframes"
echo "== npm install em $PWD (hyperframes 0.9.30 + gsap, ~100 MB)"
npm install --no-audit --no-fund
./node_modules/.bin/hyperframes --version
echo "== pronto. Conferir: ./node_modules/.bin/hyperframes doctor"
