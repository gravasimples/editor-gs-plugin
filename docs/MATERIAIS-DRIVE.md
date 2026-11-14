# Materiais da empresa no Drive (logo, fotos, takes) para o Editor

Atualizado: 29/10/2026. O Editor passa a enxergar uma cópia só leitura de uma pasta do Drive em `workspace/materiais/`, com um índice (`materiais/INDICE.md`) que ele consulta antes de montar carrossel, capa ou edição. Nada é apagado no Drive.

## Como montar a pasta
1. No Drive da Grava Simples, criar a pasta **Materiais do Editor** (sugestão: dentro de `10. Mídias`), com subpastas: `logo/` (arquivo oficial `logo-grava-simples.png`, fundo transparente), `fotos/` (Thiago, setup, bastidor), `takes/` (vídeos curtos reutilizáveis), `prints/` (OBS, webcam, Meet), `trilhas/` (música com licença).
2. Quem edita só precisa jogar os arquivos lá. Nome de arquivo descritivo ajuda o Editor a escolher (ex.: `thiago-sorrindo-setup-2026-10.jpg`).

## Ligar no app (uma vez)
1. `rclone config` com o remote `gs` (passo em `docs/PUBLICAR.md`).
2. No `.env`: `DRIVE_MATERIAIS=gs:Grava Simples - Central/10. Mídias/Materiais do Editor` (o caminho exato da pasta no Drive).
3. Reiniciar o gateway. No app → **Biblioteca → Materiais do Drive → Sincronizar**. Repetir sempre que subir material novo (ou pedir na conversa: "sincroniza os materiais").
4. O primeiro `logo*.png` encontrado vira `estilos/logo.png` e entra nos carrosséis automaticamente.

## Cartões do Notion com link do Drive
O Editor pode baixar um arquivo ou pasta pelo link do campo URL do cartão: o gateway usa `rclone backend copyid` para `materiais/_links/<id>/`. No app, Biblioteca → "Buscar pelo link do Drive".

## Regras
- Só leitura: o espelho é refeito a cada sincronização; mudar o arquivo no Drive é a fonte de verdade.
- Fotos e takes de alunos ou clientes só entram em conteúdo público com autorização registrada.
- Arquivos acima de 2 GB não são espelhados.
