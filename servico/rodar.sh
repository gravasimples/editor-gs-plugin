#!/usr/bin/env bash
# Sobe o gateway do Editor GS (API + app) em http://127.0.0.1:3200
cd "$(cd "$(dirname "$0")" && pwd -P)/.." || exit 1
mkdir -p docs/logs
RAIZ="$(pwd)"
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"; [ -d "$HOME_GS" ] && export EDITOR_GS_HOME="$HOME_GS"
for ENVF in "$RAIZ/.env" "${EDITOR_GS_HOME:+$EDITOR_GS_HOME/.env}"; do [ -n "$ENVF" ] && [ -f "$ENVF" ] && { set -a; . "$ENVF"; set +a; } || true; done
VENV="${EDITOR_GS_VENV:-$HOME/.venvs/editor-gs}"
exec "$VENV/bin/python" -m uvicorn servico.api:app --host "${EDITOR_GS_HOST:-127.0.0.1}" --port "${EDITOR_GS_PORTA:-3200}" --log-level info
