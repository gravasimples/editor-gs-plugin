#!/usr/bin/env bash
# Instalador único do Editor GS para macOS e Ubuntu (inclusive WSL). Uso: bash instalar-editor-gs.sh [GS1-...]
# Ordem: Homebrew (Mac) ou git/curl (Ubuntu) → Claude Code → login no Claude → plugin (repositório público) → motor (10 a 30 min) → chave → sobe o app.
# Pode rodar de novo: cada passo só faz o que falta.
set -uo pipefail
CHAVE="${1:-}"
MARKETPLACE="gravasimples/editor-gs-plugin"
passo() { printf '\n\033[36m== %s %s\033[0m\n' "$1" "$2"; }
tem() { command -v "$1" >/dev/null 2>&1; }
SO="$(uname -s)"

passo 1/5 "Ferramentas do sistema"
if [ "$SO" = "Darwin" ]; then
  if ! tem brew; then /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"; fi
  tem git || brew install git
else
  tem git && tem curl || { sudo apt-get update -qq && sudo apt-get install -y -qq git curl; }
fi
echo "  ok: $(git --version)"

passo 2/5 "Claude Code"
if ! tem claude; then curl -fsSL https://claude.ai/install.sh | bash; export PATH="$HOME/.local/bin:$PATH"; fi
tem claude || { echo "claude não está no PATH. Feche e abra o terminal e rode de novo."; exit 1; }
echo "  ok: $(claude --version)"

passo 3/5 "Login no Claude (conta Pro ou Max; o navegador abre)"
claude auth status 2>/dev/null | grep -q '"loggedIn": *true' || claude login
echo "  ok"

passo 4/5 "Plugin editor-gs"
claude plugin marketplace add "$MARKETPLACE" >/dev/null 2>&1 || true
claude plugin marketplace update editor-gs >/dev/null 2>&1 || true
claude plugin install editor-gs@editor-gs >/dev/null 2>&1 || true
RAIZ="$(claude plugin list 2>/dev/null | awk '/editor-gs@editor-gs/{f=1} f && /Path:/{print $2; exit}')"
[ -n "$RAIZ" ] && [ -f "$RAIZ/scripts/editor-gs.sh" ] || RAIZ="$(dirname "$(dirname "$(find "$HOME/.claude/plugins" -maxdepth 6 -name editor-gs.sh 2>/dev/null | head -1)")")"
[ -n "$RAIZ" ] && [ -f "$RAIZ/scripts/editor-gs.sh" ] || { echo "O plugin não foi instalado. Confira a internet e rode de novo; se persistir, mande o print para a Grava Simples."; exit 1; }
echo "  ok: $RAIZ"

passo 5/5 "Motor de edição (10 a 30 min; pode pedir a senha do sudo), chave e app"
CLAUDE_PLUGIN_ROOT="$RAIZ" bash "$RAIZ/scripts/editor-gs.sh" instalar || { echo "A instalação do motor falhou. Veja o log em ~/EditorGS/logs e rode de novo."; exit 1; }
if [ -n "$CHAVE" ]; then bash "$RAIZ/scripts/editor-gs.sh" chave "$CHAVE"; else echo "  sem chave informada: ative depois no Claude Code com /editor-gs:chave GS1-... (peça a chave à Grava Simples)"; fi
bash "$RAIZ/scripts/editor-gs.sh" subir && bash "$RAIZ/scripts/editor-gs.sh" abrir
printf '\n\033[32mPronto. O app abre em http://localhost:3200.\033[0m\nDepois de reiniciar: bash "%s/scripts/editor-gs.sh" subir (ou /editor-gs:subir no Claude Code).\nAtualizar quando a Grava Simples avisar: claude plugin update editor-gs@editor-gs\n' "$RAIZ"
