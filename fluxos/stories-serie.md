# Fluxo: stories-serie

Série recorrente de Stories "Dúvida da semana" (Automação 1, 01/11/2026). O pedido traz uma dúvida real da audiência (comentário público do YouTube ou Instagram, sem autor) escolhida pelo app. O Editor responde em 3 telas verticais no manual da marca e entrega também um vídeo 9:16 com as três telas, porque a Publora publica Story como vídeo (`videoType: "STORIES"`). O app agenda **só rascunho**; publicar é clique do Raphael.

Passos para o Editor (ferramentas do MCP editor-de-video):
1. Ler `marca/manual.md`, `marca/voz.md` e `referencias/_perfil-thiago/perfil.md` (se existirem). Público iniciante que ensina online; benefício antes do termo técnico; sem preço, oferta, número de alunos, promessa ou link.
2. Escrever as 3 telas (texto curto, legível no celular, até 6 linhas por tela):
   - Tela 1 · a dúvida: reescreva a pergunta em 1 ou 2 frases, nas palavras de quem pergunta, sem nome nem @; selo "DÚVIDA DA SEMANA".
   - Tela 2 · a resposta: 2 a 4 linhas na voz do Thiago (frases curtas, "ó", "olha só", "na prática"); o passo concreto no OBS ou no setup; se a resposta pedir mais de um passo, destaque só o primeiro e diga onde está o resto (vídeo do canal, aula) sem link.
   - Tela 3 · a chamada: convite para mandar a próxima dúvida por comentário ou direct (CTA de comentário tem responsável: o próprio Thiago) ou para salvar; nunca "link na bio" com preço.
   Não invente recurso ou compatibilidade: na dúvida sobre algo que você não tem certeza, responda o que é seguro e registre a lacuna em `## Pendências`.
3. Gerar as telas com `gerar_post_imagem(saida="saida/<slug>/final_story-01.png", titulo=..., destaque=..., apoio=..., formato="story", modelo="tipografico", selo="Dúvida da semana")` (telas 02 e 03 idem; alterne fundo marinho e papel como no carrossel; um destaque laranja por título). Foto real do Thiago só se houver em `materiais/` (`buscar_material`); sem foto, tipográfico. O formato story é nativo desde 03/11 (desenhado na área segura, 250 px livres em cima e embaixo); use `fundo="papel"` ou `fundo="marinho"` para alternar as telas.
4. `animar_carrossel(slides=["saida/<slug>/final_story-01.png", ".../final_story-02.png", ".../final_story-03.png"], saida_video="saida/<slug>/final_stories_9x16.mp4", duracao_slide_s=5, transicao_s=0.5, formato="9x16")`. Conferir no JSON `duracao_s` entre 12 e 20 s (a Publora exige pelo menos 3 s).
5. `revisar_video("saida/<slug>/final_stories_9x16.mp4")` uma vez; corrigir texto errado ou tela ilegível; o resto vai para `## Pendências`.
6. Mensagem final com `## Resumo` (dúvida escolhida, fonte sem autor, telas), `## Roteiro` (texto de cada tela), `## Legenda do post` (1 a 2 linhas para a Publora: a dúvida e o convite, sem hashtag em excesso), `## Hashtags` (3 a 5), `## Pendências` e `## Arquivos`. Não publicar, não escrever no Notion.
