---
name: editor-gs
description: Usa o Editor GS (app local de edição de vídeo da Grava Simples) a partir do Claude Code. Use quando a pessoa pedir para editar um vídeo, fazer Reel, cortes de live, carrossel, legenda ou qualquer peça no padrão Grava Simples, acompanhar um pedido ("como está o GRA-12?"), responder ao Editor ou ver a fila. Não edita no terminal: abre o pedido no app e o Editor (agente do próprio app) faz o trabalho.
---

# Editor GS pelo Claude Code

O Editor GS é um app local (http://localhost:3200) com um agente editor próprio. Você não edita o vídeo aqui: você **abre o pedido** no app, pelas ferramentas MCP `editor-gs`, e acompanha.

## Antes
- `bash "${CLAUDE_PLUGIN_ROOT}/scripts/editor-gs.sh" status`. Fora do ar → `/editor-gs:subir`. Não instalado → `/editor-gs:instalar`.
- Um pedido por vez entra em edição (GPU e cota): só abra pedido quando a pessoa pedir.

## Ferramentas (MCP `editor-gs`)
- `novo_pedido(texto, fluxo, estilo, arquivos, campanha)`: abre o pedido com o vídeo (caminho local). Fluxos em `fluxos()`; os mais usados: `reels-padrao`, `cortes-longos`, `carrossel`, `kit-derivacao`, `roteiro`. Estilos: `padrao`, `tutorial`, `opiniao`, `bastidor`, `profissional`.
- `kit_derivacao(video|link, n_reels, carrossel, stories)`: gravação longa → Reels + carrossel + Stories.
- `listar_pedidos(n, so_abertos)`, `ver_pedido(id, mensagens)`, `responder_pedido(id, texto, arquivos)`, `fila()`.
- `buscar_fala(q)`, `ganchos(tipo)`, `o_que_rende()`, `campanhas()`.

## Entregas
Arquivos em `<dados>/workspace/saida/<slug>/` (`final_9x16.mp4`, `final_16x9.mp4`, `capa.png`, `legenda.srt`, carrossel em PNG/PPTX). Textos (resumo, legenda do post, pendências) vêm na mensagem final do Editor, em seções `## `. Mostre à pessoa o link do pedido (`ver_pedido` devolve) e os caminhos dos arquivos; não copie os vídeos para outro lugar.

## Regras
- Quem aprova, publica e decide é a pessoa, no app. Você não aprova nem publica.
- Padrão da marca (laranja #F79615 único destaque, marinho #000921, Inter): o Editor já segue; só repasse pedidos fora da paleta quando a pessoa disser.
- Pedido de teste seu nunca passa na frente de pedido da pessoa.
