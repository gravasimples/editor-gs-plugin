#!/usr/bin/env bash
# Sobe o MCP editor-de-video com o venv e as libs CUDA do pip no caminho. Caminhos relativos ao projeto e ao $HOME (roda em qualquer máquina).
set -e
RAIZ="$(cd "$(cd "$(dirname "$0")" && pwd -P)/../.." && pwd)"
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"; [ -d "$HOME_GS" ] && export EDITOR_GS_HOME="$HOME_GS"
[ -n "${EDITOR_GS_HOME:-}" ] && [ -f "$EDITOR_GS_HOME/.env" ] && { set -a; . "$EDITOR_GS_HOME/.env"; set +a; } || true
VENV="${EDITOR_GS_VENV:-$HOME/.venvs/editor-gs}"
SP="$("$VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib:$HOME/.local/lib-chromium/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# EDITOR_GS_ENV: carrega chaves do .env do projeto (GEMINI_API_KEY etc.)
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"; [ -d "$HOME_GS" ] && export EDITOR_GS_HOME="$HOME_GS"
for ENVF in "$RAIZ/.env" "${EDITOR_GS_HOME:+$EDITOR_GS_HOME/.env}"; do [ -n "$ENVF" ] && [ -f "$ENVF" ] && { set -a; . "$ENVF"; set +a; } || true; done
[ -n "${EDITOR_GS_HOME:-}" ] && export EDITOR_GS_WORKSPACE="${EDITOR_GS_WORKSPACE:-$EDITOR_GS_HOME/workspace}"
export EDITOR_GS_ESTILOS="${EDITOR_GS_ESTILOS:-$RAIZ/estilos}"
exec "$VENV/bin/python" -I "$(cd "$(dirname "$0")" && pwd -P)/servidor.py" "$@"
