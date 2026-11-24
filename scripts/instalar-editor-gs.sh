#!/usr/bin/env bash
# Instalador único do Editor GS para macOS e Ubuntu (inclusive WSL). Uso: bash instalar-editor-gs.sh [GS1-...]
# Uma linha: curl -fsSL https://raw.githubusercontent.com/gravasimples/editor-gs-plugin/main/scripts/instalar-editor-gs.sh | bash -s -- GS1-…
# Ordem: git da Apple (Mac, sem Homebrew) ou git/curl (Ubuntu) → Claude Code → login no Claude → plugin (repositório público) → motor (2 a 10 min) → chave → sobe o app.
# Pode rodar de novo: cada passo só faz o que falta.
set -uo pipefail
# Tudo dentro de main(): com "curl … | bash" o bash precisa ler o script inteiro antes de rodar, senão um comando que lê a entrada engole o resto.
main() {
CHAVE="${1:-}"
MARKETPLACE="gravasimples/editor-gs-plugin"
passo() { printf '\n\033[36m== %s %s\033[0m\n' "$1" "$2"; }
tem() { command -v "$1" >/dev/null 2>&1; }
SO="$(uname -s)"

passo 1/5 "Ferramentas do sistema"
if [ "$SO" = "Darwin" ]; then
  # 24/11/2026: sem Homebrew. Só o git é do sistema (o Claude Code baixa o plugin com ele); vem nas Ferramentas de Linha de Comando da Apple.
  if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]; then echo "Este Mac tem processador Intel. O Editor GS precisa de um Mac com Apple Silicon (M1 ou mais novo)."; exit 1; fi
  if ! xcode-select -p >/dev/null 2>&1; then
    echo "  Falta o git da Apple. Vai abrir uma janela: clique em INSTALAR e aguarde (5 a 10 min). Eu continuo sozinho quando terminar."
    xcode-select --install >/dev/null 2>&1 || true
    n=0; until xcode-select -p >/dev/null 2>&1 && git --version >/dev/null 2>&1; do sleep 10; n=$((n+1)); [ $n -lt 180 ] || { echo "As ferramentas da Apple não terminaram de instalar. Conclua a janela de instalação e rode de novo."; exit 1; }; done
  fi
else
  tem git && tem curl || { sudo apt-get update -qq && sudo apt-get install -y -qq git curl; }
fi
echo "  ok: $(git --version)"

passo 2/5 "Claude Code"
if ! tem claude; then curl -fsSL https://claude.ai/install.sh | bash; export PATH="$HOME/.local/bin:$PATH"; fi
# Mac novo: ~/.local/bin (onde o claude fica) não está no PATH do Terminal; sem isto "claude" não é achado numa janela nova.
if [ "$SO" = "Darwin" ] && ! grep -qs '\.local/bin' "$HOME/.zprofile" "$HOME/.zshrc"; then echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zprofile"; fi
export PATH="$HOME/.local/bin:$PATH"
tem claude || { echo "claude não está no PATH. Feche e abra o terminal e rode de novo."; exit 1; }
echo "  ok: $(claude --version)"

passo 3/5 "Login no Claude (conta Pro ou Max; o navegador abre)"
logado() { claude auth status 2>/dev/null | grep -q '"loggedIn": *true' || claude auth status >/dev/null 2>&1; }
# "claude login" não existe no Claude Code atual: o comando é "claude auth login" (13/11/2026).
if ! logado; then
  if [ -t 0 ]; then claude auth login; else claude auth login </dev/tty; fi  # com "curl … | bash" a entrada é o próprio script
  logado || { echo "O login no Claude não foi concluído. Rode o instalador de novo e entre na sua conta quando o navegador abrir."; exit 1; }
fi
echo "  ok"

passo 4/5 "Plugin editor-gs"
claude plugin marketplace add "$MARKETPLACE" >/dev/null 2>&1 || true
claude plugin marketplace update editor-gs >/dev/null 2>&1 || true
claude plugin install editor-gs@editor-gs >/dev/null 2>&1 || true
claude plugin update editor-gs@editor-gs >/dev/null 2>&1 || true  # rodar o instalador de novo traz a versão mais nova
RAIZ="$(claude plugin list 2>/dev/null | awk '/editor-gs@editor-gs/{f=1} f && /Path:/{print $2; exit}')"
[ -n "$RAIZ" ] && [ -f "$RAIZ/scripts/editor-gs.sh" ] || RAIZ="$(dirname "$(dirname "$(ls -t "$HOME"/.claude/plugins/cache/editor-gs/editor-gs/*/scripts/editor-gs.sh 2>/dev/null | head -1)")")"
# Instalação antiga que o "plugin update" não trocou (visto no 1º Mac, que ficou na versão com defeito): reinstala para pegar a publicada.
versao_de() { sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$1" 2>/dev/null | head -1; }
V_PUB="$(versao_de "$HOME/.claude/plugins/marketplaces/editor-gs/.claude-plugin/plugin.json")"; V_INST="$(versao_de "$RAIZ/.claude-plugin/plugin.json")"
if [ -n "$V_PUB" ] && [ -n "$V_INST" ] && [ "$V_PUB" != "$V_INST" ]; then
  echo "  versão instalada $V_INST, publicada $V_PUB: reinstalando o plugin"
  claude plugin uninstall editor-gs@editor-gs >/dev/null 2>&1 || true
  claude plugin install editor-gs@editor-gs >/dev/null 2>&1 || true
  NOVA="$(ls -d "$HOME"/.claude/plugins/cache/editor-gs/editor-gs/"$V_PUB" 2>/dev/null | head -1)"
  [ -n "$NOVA" ] && [ -f "$NOVA/scripts/editor-gs.sh" ] && RAIZ="$NOVA"
fi
[ -n "$RAIZ" ] && [ -f "$RAIZ/scripts/editor-gs.sh" ] || { echo "O plugin não foi instalado. Confira a internet e rode de novo; se persistir, mande o print para a Grava Simples."; exit 1; }
echo "  ok: $RAIZ"

passo 5/5 "Motor de edição (2 a 10 min, conforme a internet), chave e app"
CLAUDE_PLUGIN_ROOT="$RAIZ" bash "$RAIZ/scripts/editor-gs.sh" instalar || { echo "A instalação do motor falhou. Veja o log em ~/EditorGS/logs e rode de novo."; exit 1; }
if [ -n "$CHAVE" ]; then bash "$RAIZ/scripts/editor-gs.sh" chave "$CHAVE"; else echo "  sem chave informada: ative depois no Claude Code com /editor-gs:chave GS1-... (peça a chave à Grava Simples)"; fi
bash "$RAIZ/scripts/editor-gs.sh" subir && bash "$RAIZ/scripts/editor-gs.sh" abrir
printf '\n\033[32mPronto. O app abre em http://localhost:3200.\033[0m\nDepois de reiniciar o computador ele sobe sozinho no Mac; se não abrir: bash "%s/scripts/editor-gs.sh" subir (ou /editor-gs:subir no Claude Code).\nAtualizar quando a Grava Simples avisar: claude plugin update editor-gs@editor-gs\n' "$RAIZ"
}
main "$@"
