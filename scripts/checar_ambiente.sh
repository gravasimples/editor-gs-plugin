#!/usr/bin/env bash
# Hook de início de sessão do plugin editor-gs: uma linha dizendo se o Editor GS está instalado e no ar. Nunca instala nem sobe nada.
# Windows (Git Bash do Claude Code): o lançador é o editor_gs.py, pelo .cmd
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) exec cmd.exe //c "$(cygpath -w "$(dirname "$0")/editor-gs.cmd")" checar;; esac
RAIZ="$(cd "$(cd "$(dirname "$0")" && pwd -P)/.." && pwd)"
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"
[ -f "$HOME_GS/.env" ] && { set -a; . "$HOME_GS/.env"; set +a; } || true
VENV="${EDITOR_GS_VENV:-$HOME/.venvs/editor-gs}"; PORTA="${EDITOR_GS_PORTA:-3200}"
if [ ! -x "$VENV/bin/python" ] || [ ! -d "$RAIZ/app/dist" ]; then
  echo "Editor GS: ainda não instalado nesta máquina. Para instalar, peça /editor-gs:instalar (uma vez; baixa Python, Node, ffmpeg e o motor de edição)."
  exit 0
fi
LIC=""; if [ -d "$HOME_GS" ] && [ ! -f "$HOME_GS/estado/licenca.json" ]; then LIC=" Falta a chave do produto: /editor-gs:chave GS1-..."; fi
if curl -s -m 2 "http://127.0.0.1:$PORTA/api/health" >/dev/null 2>&1; then
  echo "Editor GS: instalado e no ar em http://localhost:$PORTA (dados em ${EDITOR_GS_HOME:-$RAIZ}). Ferramentas MCP editor-gs disponíveis (novo_pedido, listar_pedidos, ver_pedido, fila).$LIC"
else
  echo "Editor GS: instalado, mas o app não está no ar. Para subir, peça /editor-gs:subir (abre em http://localhost:$PORTA).$LIC"
fi
