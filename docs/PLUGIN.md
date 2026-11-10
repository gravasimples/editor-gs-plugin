# Editor GS como plugin do Claude Code — 10/11/2026

Direção fechada com o Raphael em 09/11: o Editor GS deixa de depender do Paperclip e passa a ser distribuído como plugin do Claude Code, com repositório no GitHub, acesso liberado por pessoa e a interface do app instalável no computador de quem usa. O motor é o Claude Code da própria pessoa (assinatura dela); não há servidor nem chave de API nossa.

## O que já está pronto (10/11)
- **Executor local** no lugar do Paperclip (`docs/EXECUTOR-LOCAL.md`).
- **Este repositório é o plugin e o marketplace**: `.claude-plugin/plugin.json` (plugin `editor-gs` 1.0.0), `.claude-plugin/marketplace.json` (marketplace `editor-gs`, fonte `./`), `.mcp.json` (servidor MCP `editor-gs` para abrir e acompanhar pedidos de dentro do Claude Code), `hooks/hooks.json` (início de sessão: uma linha dizendo se está instalado e no ar), comandos `/editor-gs:instalar`, `/editor-gs:subir`, `/editor-gs:status`, skill `editor-gs` (como usar o app pelo Claude). `claude plugin validate .` passa.
- **Dados fora do código** (`servico/caminhos.py`): quando existe `~/EditorGS` (ou `EDITOR_GS_HOME`), workspace, estado (índices, tokens, `config.local.json`), logs, trilhas e `.env` ficam lá; o código do plugin pode ser atualizado sem perder nada. Sem a pasta, tudo continua dentro do projeto como sempre (esta máquina).
- `scripts/editor-gs.sh` (instalar | subir | parar | status | abrir | caminhos) é a porta única; `scripts/instalar.sh` não instala mais o Paperclip e, chamado pelo plugin, cria `~/EditorGS`.

## Como alguém instala (depois do repositório no GitHub)
Caminho curto: o instalador único (`scripts/instalar-editor-gs.ps1` no Windows, `.sh` no Mac/Ubuntu) faz os passos abaixo numa linha; ver `docs/INSTALAR-OUTRO-PC.md`. À mão:
1. Claude Code instalado e logado (Pro ou Max). Windows: nativo desde 10/11 (Git for Windows + `CLAUDE_CODE_GIT_BASH_PATH`), sem WSL.
2. Acesso ao repositório privado (convite por usuário GitHub) e `gh auth login` na máquina (no WSL, apontar o git para o gh: `git config --global credential.helper '!gh auth git-credential'`).
3. No terminal:
   ```
   claude plugin marketplace add gravasimples/editor-gs
   claude plugin install editor-gs@editor-gs
   ```
4. Abrir o Claude Code e pedir `/editor-gs:instalar` (uma vez, 10 a 30 min). Depois `/editor-gs:subir` → http://localhost:3200 (no navegador: "instalar como aplicativo").
5. Atualizações: ao subir a versão no `plugin.json` e dar push, o Claude Code da pessoa atualiza o plugin; os dados em `~/EditorGS` ficam.

Sem GitHub (teste imediato nesta máquina ou em outra com o código copiado): `claude --plugin-dir ~/projetos/editor-gs`.

## Na prática, para quem recebe o Editor GS (perguntas do Raphael, 10/11)

**Como a pessoa recebe o acesso.** Três coisas: (1) convite ao repositório privado `gravasimples/editor-gs` pelo usuário GitHub dela (Settings → Collaborators → Add people; ela aceita o convite por e-mail); (2) uma chave do produto emitida aqui (`servico/licenca.py emitir --nome "Nome" --dias 365`), mandada por mensagem; (3) o guia de instalação (`docs/INSTALAR-OUTRO-PC.md`). O Claude (Pro ou Max) e o Claude Code são dela; o GitHub é só o canal de entrega e atualização.

**O que ela faz na máquina (hoje, 10/11).** Windows: instalar o WSL2 com Ubuntu uma vez (até a versão nativa existir); Mac: nada extra. Depois, no terminal: Claude Code (`claude login`), `gh auth login` (abre o navegador), `git config --global credential.helper '!gh auth git-credential'`, `claude plugin marketplace add gravasimples/editor-gs`, `claude plugin install editor-gs@editor-gs`. Abre o Claude Code: `/editor-gs:instalar` (10 a 30 min, uma vez), `/editor-gs:chave GS1-...`, `/editor-gs:subir` → http://localhost:3200. O app pode virar ícone ("instalar como aplicativo" no navegador).

**Dá para encurtar?** Sim, em duas frentes: um script único `instalar-editor-gs.sh` que faz WSL/Homebrew → Claude Code → gh → marketplace → plugin → instalar numa sequência só (o que sobra para a pessoa é entrar nas contas quando o navegador abrir), e a versão Windows nativa (sem WSL), que é o que mais pesa hoje. O login do GitHub é o passo que não dá para tirar enquanto a entrega for por repositório privado; a alternativa é o zip assinado (`docs/DISTRIBUICAO.md` do Edita Simples), que exige servidor nosso.

**O que eu vejo de quem usa.** Nada do conteúdo: vídeos, pedidos, conversas e chaves de API ficam na máquina da pessoa (`~/EditorGS`); o app não manda nada para fora. O GitHub mostra apenas quem aceitou o convite e, em Insights → Traffic, contagens agregadas de clone (14 dias, sem nome). Se quisermos saber uso (quantos pedidos, quais fluxos, erros), tem de ser um envio opcional e declarado (um "relatório de uso" que a pessoa liga), construído à parte. Hoje não existe.

**Atualizações.** Toda mudança que eu commitar e der push no `master` fica disponível na hora. Correção de 10/11 (noite), pela doc do Claude Code: a atualização automática é **desligada por padrão** para marketplaces de terceiros. A pessoa roda `claude plugin update editor-gs@editor-gs` ou liga "Enable auto-update" em `/plugin` → Marketplaces; a cópia nova só vem quando `plugin.json → version` muda. Repositório privado: `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` + credencial do `gh`. Regra para nós: subir a versão no `plugin.json` a cada release; mudança sem versão nova não chega. Os dados dela (`~/EditorGS`) não são tocados pela atualização; se uma versão mudar o banco do executor ou o `config.local.json`, o código precisa migrar sozinho na subida.

**Codex e Gemini depois do Paperclip.** As ferramentas não se perderam: o Revisor de vídeo (Gemini assiste ao vídeo) e a tradução de legenda pelo Gemini são ferramentas do MCP `editor-de-video`, chamadas por qualquer agente com `GEMINI_API_KEY` no `.env`. O que o Paperclip dava eram agentes alternativos (Codex, Gemini/Antigravity) para rodar o pedido inteiro. O Codex voltou em 10/11 (adaptador `codex` no executor: `codex exec --json`, mesmo AGENTS.md e MCP; chip "Codex (ChatGPT)" e roteamento por fluxo como antes). O Gemini como agente ficou de fora: a ponte do Antigravity era frágil e dependia de permissões manuais; volta só se fizer falta. Para quem compra o produto, nada disso importa: o motor é o Claude dela.

## Estado em 10/11/2026 (noite)
1. **Publicado**: `https://github.com/gravasimples/editor-gs` (privado, conta `gravasimples`; `master` = código Windows nativo + Linux/macOS). Convite por pessoa: `gh api -X PUT repos/gravasimples/editor-gs/collaborators/<usuario> -f permission=pull`.
2. **Windows nativo feito** (10/11, madrugada e manhã): `servico/plataforma.py` concentra as diferenças de SO; lançador `scripts/editor_gs.py` + `editor-gs.cmd` (instalar | subir | parar | status | abrir | caminhos | checar | chave); os `.sh` do plugin delegam ao `.cmd` quando rodam no Git Bash; o MCP `editor-gs` do plugin é lançado por `${CLAUDE_CODE_GIT_BASH_PATH:-bash}` (o Claude Code no Windows já exige o Git Bash; o instalador define a variável). Produção desta máquina roda nativa.
3. **Chave do produto**: `servico/licenca.py` (Ed25519; privada só em `~/.config/editor-gs/licenca-privada.pem` do Raphael). Exigida só no modo plugin (dados em `~/EditorGS`): sem chave a API responde 402; ativar com `/editor-gs:chave GS1-...`. Revogar: id em `config.json → licenca.revogadas`. Desligar a exigência numa instalação: `licenca.exigir=false` no `config.local.json`.
4. **Instalador único** (10/11, noite): `scripts/instalar-editor-gs.ps1` (Windows) e `scripts/instalar-editor-gs.sh` (Mac/Ubuntu/WSL) fazem Git → gh → Claude Code → logins → marketplace → plugin → motor → chave → app numa sequência só. `/editor-gs:instalar` roda em segundo plano e acompanha o log (`~/EditorGS/logs/instalacao-*.log`), porque a instalação passa do limite de tempo de um comando. `.env.exemplo` agora vai no repositório (modelo das chaves opcionais).
5. **Teste no computador do Thiago**: roteiro em `docs/INSTALAR-OUTRO-PC.md`. Ainda não houve instalação em máquina limpa de ponta a ponta.
6. **Depois**: casca de desktop (Tauri/Electron) com ícone e instalador `.exe`/`.dmg`; relatório de uso opcional; Gemini como agente só se fizer falta.

## O que fica fora do produto
Voz clonada do Thiago, métricas e acervo do GSI (`gs.db`), vidIQ, Notion e as automações que leem o GSI são desta máquina. O produto é a edição.
