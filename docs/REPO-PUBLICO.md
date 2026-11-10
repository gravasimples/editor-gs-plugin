# Repositório público do plugin — 10/11/2026

Decisão do Raphael (10/11/2026, noite): o Thiago quer testar o caminho de instalação como será na venda, então o plugin passa a ser entregue por um repositório **público**, sem convite nem login no GitHub. Quem compra recebe só a chave `GS1-...` e o instalador.

## Dois repositórios

| | `gravasimples/editor-gs` (privado) | `gravasimples/editor-gs-plugin` (público) |
|---|---|---|
| Papel | desenvolvimento, histórico, docs internos | distribuição |
| Conteúdo | tudo | cópia filtrada do HEAD: código, estilos, fluxos, fontes, sons, modelos, instaladores, docs de uso |
| Histórico | completo | um commit por versão (`git push --force` em `main`) |
| Quem escreve | o Raphael e o Claude Code daqui | só `scripts/publicar_plugin.ps1` |

Fica de fora do público: `docs/HANDOFF*.md`, `docs/maquina/` (análises de concorrente, pesquisas), `docs/evidencias/`, registros de etapa, relatórios, `VOZ-CLONADA.md`, `AGENTES.md`, `ACESSO-EXTERNO.md` (URL do Tailscale), `INSTAGRAM-COOKIES.md`, scripts de voz e do Paperclip, prévias de estilo. A lista está em `$excluir` no script.

## O que a publicação exige

1. Commit no privado com a versão nova em `.claude-plugin/plugin.json` e `marketplace.json` (a atualização de quem instalou só chega quando a versão muda).
2. `powershell -ExecutionPolicy Bypass -File scripts\publicar_plugin.ps1` na raiz do privado. O script copia, roda uma varredura de segredos (tokens, chaves privadas, chaves `GS1-`) e aborta se achar algo, e só então publica.
3. Avisar quem usa: `claude plugin update editor-gs@editor-gs`.

## Segurança: o que está e o que não está protegido

- **Segredos:** nunca vão para nenhum dos dois repositórios (`.env` é ignorado; `.env.exemplo` só tem nomes). A chave privada do produto fica em `~/.config/editor-gs/` do Raphael, fora do git; no código vai só a chave pública, que serve para verificar, não para emitir.
- **Chave do produto:** continua exigida no modo plugin (402 sem chave). Com o código aberto, uma pessoa técnica consegue desligar a exigência (`licenca.exigir=false`). A proteção real do produto é a chave como condição de suporte e atualização, não o sigilo do código. Se isso passar a importar comercialmente, as opções são servidor de ativação (exige infraestrutura nossa) ou distribuição em binário (casca desktop).
- **O que fica visível:** prompts do agente (`workspace/AGENTS.md`, `fluxos/`), estilos da marca, regras de edição, os testes. Nada de vídeos, dados de clientes, métricas ou conversas: isso nunca esteve no git.
- **Telemetria:** nenhuma. O app não manda nada para fora; o GitHub só mostra contagens agregadas de clone.

## O que muda para quem instala

De 8 passos para 4: Git for Windows e Claude Code (o instalador faz), login no Claude (navegador), o resto é automático. Sem conta GitHub, sem convite, sem `gh`, sem `CLAUDE_CODE_PLUGIN_PREFER_HTTPS`.
