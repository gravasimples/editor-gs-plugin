#!/usr/bin/env bash
# Sobe o gateway do Editor GS (3200) em segundo plano; no modo paperclip sobe também o Paperclip (3100). Rode de novo para reiniciar o gateway.
RAIZ="$(cd "$(cd "$(dirname "$0")" && pwd -P)/.." && pwd)"; cd "$RAIZ"
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
HOME_GS="${EDITOR_GS_HOME:-$HOME/EditorGS}"; [ -d "$HOME_GS" ] && export EDITOR_GS_HOME="$HOME_GS"
for ENVF in "$RAIZ/.env" "${EDITOR_GS_HOME:+$EDITOR_GS_HOME/.env}"; do [ -n "$ENVF" ] && [ -f "$ENVF" ] && { set -a; . "$ENVF"; set +a; } || true; done
SETSID="$(command -v setsid || true)"  # macOS não tem setsid
LOGS="${EDITOR_GS_LOGS:-${EDITOR_GS_HOME:+$EDITOR_GS_HOME/logs}}"; LOGS="${LOGS:-docs/logs}"; mkdir -p "$LOGS"
MODO="$(python3 -c "import sys;sys.path.insert(0,'.');from servico import caminhos;print((caminhos.config().get('executor') or {}).get('modo','paperclip'))" 2>/dev/null || echo paperclip)"
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
($SETSID nohup servico/rodar.sh >> "$LOGS/gateway-$(date +%F).log" 2>&1 &)
sleep 5
[ "$MODO" = "local" ] || curl -s -m 3 -o /dev/null -w "Paperclip: %{http_code}\n" http://127.0.0.1:3100/api/health
curl -s -m 3 -o /dev/null -w "Editor GS: %{http_code}  → abra http://localhost:3200\n" http://127.0.0.1:3200/api/gs/quem
