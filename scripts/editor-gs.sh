#!/usr/bin/env bash
# Porta única do Editor GS. Uso: bash scripts/editor-gs.sh instalar | subir | parar | status | abrir | caminhos
# Windows (Git Bash do Claude Code): o lançador é o editor_gs.py, pelo .cmd
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) exec cmd.exe //c "$(cygpath -w "$(dirname "$0")/editor-gs.cmd")" "$@";; esac
set -uo pipefail
RAIZ="$(cd "$(cd "$(dirname "$0")" && pwd -P)/.." && pwd)"; cd "$RAIZ"
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"; [ -d "$HOME_GS" ] && export EDITOR_GS_HOME="$HOME_GS"
[ -n "${EDITOR_GS_HOME:-}" ] && [ -f "$EDITOR_GS_HOME/.env" ] && { set -a; . "$EDITOR_GS_HOME/.env"; set +a; } || true
[ -z "${EDITOR_GS_HOME:-}" ] && [ -f "$RAIZ/.env" ] && { set -a; . "$RAIZ/.env"; set +a; } || true
VENV="${EDITOR_GS_VENV:-$HOME/.venvs/editor-gs}"; PORTA="${EDITOR_GS_PORTA:-3200}"; URL="http://localhost:$PORTA"
case "${1:-status}" in
  instalar) if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then bash scripts/instalar.sh --plugin; else bash scripts/instalar.sh "${2:-}"; fi ;;
  subir) bash scripts/subir.sh ;;
  parar) pkill -f "[u]vicorn servico.api" && echo "Editor GS parado." || echo "Editor GS já estava parado." ;;
  status)
    if [ ! -x "$VENV/bin/python" ]; then echo "não instalado (venv $VENV ausente). Rode: bash scripts/editor-gs.sh instalar"; exit 1; fi
    if curl -s -m 2 "$URL/api/health" >/dev/null; then echo "no ar em $URL"; "$VENV/bin/python" -m servico.executor_local status 2>/dev/null | head -30; else echo "instalado, fora do ar. Rode: bash scripts/editor-gs.sh subir"; fi ;;
  abrir)
    if command -v xdg-open >/dev/null 2>&1 && [ -z "${WSL_DISTRO_NAME:-}" ]; then xdg-open "$URL"; elif command -v open >/dev/null 2>&1; then open "$URL"; elif command -v cmd.exe >/dev/null 2>&1; then cmd.exe /c start "$URL" >/dev/null 2>&1; fi
    echo "$URL" ;;
  caminhos) "$VENV/bin/python" servico/caminhos.py 2>/dev/null || python3 servico/caminhos.py ;;
  chave) [ -n "${2:-}" ] || { echo "uso: $0 chave GS1-..."; exit 2; }; "$VENV/bin/python" servico/licenca.py ativar "$2" && echo "Chave ativada. Se o app estiver no ar, recarregue a página." ;;
  garantir) curl -s -m 2 "$URL/api/health" >/dev/null || { echo "$(date '+%F %T') gateway fora do ar; subindo" >> "${EDITOR_GS_HOME:-$RAIZ/docs}/logs/vigia.log" 2>/dev/null; bash scripts/subir.sh; } ;;
  *) echo "uso: $0 instalar | subir | parar | status | abrir | caminhos | chave GS1-... | garantir"; exit 2 ;;
esac
