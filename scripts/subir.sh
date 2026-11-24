#!/usr/bin/env bash
# Sobe o gateway do Editor GS (3200) em segundo plano; no modo paperclip sobe também o Paperclip (3100). Rode de novo para reiniciar o gateway.
RAIZ="$(cd "$(cd "$(dirname "$0")" && pwd -P)/.." && pwd)"; cd "$RAIZ"
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"; [ -d "$HOME_GS" ] && export EDITOR_GS_HOME="$HOME_GS"
for ENVF in "$RAIZ/.env" "${EDITOR_GS_HOME:+$EDITOR_GS_HOME/.env}"; do [ -n "$ENVF" ] && [ -f "$ENVF" ] && { set -a; . "$ENVF"; set +a; } || true; done
SETSID="$(command -v setsid || true)"  # macOS não tem setsid
# 24/11/2026 — pós-atualização no Linux/macOS (no Windows quem faz é o editor_gs.py): a pasta de uma versão nova do plugin chega sem bit de
# execução, sem remotion/node_modules e com o .mcp.json do workspace apontando para a pasta antiga. Sem isto o gateway morria na atualização automática.
VENV="${EDITOR_GS_VENV:-$HOME/.venvs/editor-gs}"; DADOS="${EDITOR_GS_HOME:-$RAIZ}"
chmod +x servico/rodar.sh mcp/*/servidor.sh scripts/*.sh 2>/dev/null || true
if case "$RAIZ" in */plugins/cache/*) true;; *) false;; esac && [ ! -d remotion/node_modules ]; then
  for ANT in "$RAIZ"/../*/remotion/node_modules; do
    if [ -d "$ANT" ]; then mv "$ANT" remotion/node_modules && echo "remotion/node_modules ← versão anterior" && break; fi
  done
  [ -d remotion/node_modules ] || echo "AVISO: remotion/node_modules ausente; rode: bash scripts/editor-gs.sh instalar"
fi
if [ -x "$VENV/bin/python" ] && [ "$(cksum < requirements.txt)" != "$(cat "$DADOS/requirements.sum" 2>/dev/null)" ]; then
  if command -v uv >/dev/null 2>&1 && uv pip install --python "$VENV/bin/python" -r requirements.txt >> "${EDITOR_GS_HOME:-$RAIZ/docs}/logs/atualizacao-libs.log" 2>&1; then cksum < requirements.txt > "$DADOS/requirements.sum"; fi
fi
MCPJ="$DADOS/workspace/.mcp.json"
if [ -f "$MCPJ" ] && ! grep -q "\"$RAIZ/mcp/editor-de-video/servidor.sh\"\]" "$MCPJ"; then
  printf '{\n    "mcpServers": {\n        "editor-de-video": {\n            "command": "bash",\n            "args": ["%s/mcp/editor-de-video/servidor.sh"]\n        }\n    }\n}\n' "$RAIZ" > "$MCPJ"
fi
LOGS="${EDITOR_GS_LOGS:-${EDITOR_GS_HOME:+$EDITOR_GS_HOME/logs}}"; LOGS="${LOGS:-docs/logs}"; mkdir -p "$LOGS"
PYM="$VENV/bin/python"; [ -x "$PYM" ] || PYM=python3
MODO="$("$PYM" -c "import sys;sys.path.insert(0,'.');from servico import caminhos;print((caminhos.config().get('executor') or {}).get('modo','paperclip'))" 2>/dev/null || echo paperclip)"
if [ "$MODO" = "local" ]; then
  echo "Executor local (config.json → executor.modo=local): o Paperclip não é necessário."
elif ! curl -s -m 3 http://127.0.0.1:3100/api/health >/dev/null; then
  if [ ! -f "$HOME/.paperclip/instances/default/config.json" ]; then
    echo "Primeira vez: configurando o Paperclip (local, sem login, porta 3100)."; npx paperclipai onboard -y --no-install-service
  fi
  ($SETSID nohup npx paperclipai run >> "$LOGS/paperclip-$(date +%F).log" 2>&1 &)
  for i in $(seq 1 60); do sleep 2; curl -s -m 2 http://127.0.0.1:3100/api/health >/dev/null && break; done
fi
pkill -f "[u]vicorn servico.api" 2>/dev/null; sleep 1
($SETSID nohup bash servico/rodar.sh >> "$LOGS/gateway-$(date +%F).log" 2>&1 &)
sleep 5
[ "$MODO" = "local" ] || curl -s -m 3 -o /dev/null -w "Paperclip: %{http_code}\n" http://127.0.0.1:3100/api/health
curl -s -m 3 -o /dev/null -w "Editor GS: %{http_code}  → abra http://localhost:3200\n" http://127.0.0.1:3200/api/gs/quem
