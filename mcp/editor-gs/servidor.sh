#!/usr/bin/env bash
# MCP editor-gs: o Editor GS como ferramenta para outros agentes (Claude Code, plugin). Precisa do gateway no ar (porta 3200 ou EDITOR_GS_URL).
# Windows (Git Bash do Claude Code): python.exe do venv; não carrega o .env (barra invertida some no `source`; este servidor só precisa de EDITOR_GS_URL).
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*)
  VENV="${EDITOR_GS_VENV:-$USERPROFILE\\.venvs\\editor-gs}"; VENV="$(cygpath -u "$VENV")"
  export PYTHONUTF8=1
  exec "$VENV/Scripts/python.exe" -I -X utf8 "$(cygpath -w "$(dirname "$0")/servidor.py")" "$@";;
esac
set -e
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"; [ -d "$HOME_GS" ] && export EDITOR_GS_HOME="$HOME_GS"
[ -n "${EDITOR_GS_HOME:-}" ] && [ -f "$EDITOR_GS_HOME/.env" ] && { set -a; . "$EDITOR_GS_HOME/.env"; set +a; } || true
exec "${EDITOR_GS_VENV:-$HOME/.venvs/editor-gs}/bin/python" -I "$(cd "$(dirname "$0")" && pwd -P)/servidor.py" "$@"
