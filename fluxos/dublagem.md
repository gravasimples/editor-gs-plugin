# Fluxo: dublagem

Vídeo dublado: a fala original sai (ou fica bem baixa) e entra uma narração sintética no idioma de destino, com legenda karaokê nesse idioma. Reaproveita o fluxo `traduzir-legenda`. A voz é sintética e nunca é apresentada como a do Thiago.

Passos para o Editor:
1. Idioma de destino (padrão inglês; código `en`, `es`...). Vídeo-base: o vídeo SEM legenda queimada (`cortado.mp4` de uma entrega anterior, ou o bruto). Nunca cortar neste fluxo.
2. SRT traduzido: se já existir `legenda-<idioma>.srt` da entrega anterior, reaproveitar; senão `traduzir_srt(srt, saida/<slug>/legenda-<idioma>.srt, idioma, curto=True, destaque=False)` (Gemini, barato; frases mais curtas para caber no tempo) e leia o resultado antes de dublar; transcreva antes se não houver SRT. Para dublagem as frases precisam caber no tempo falado: traduza mais curto que o original (em inglês costuma caber; em espanhol encurte), uma frase por bloco, sem `*destaque*` obrigatório.
3. `dublar(video, srt, saida/<slug>/final_9x16_<idioma>_dub.mp4, idioma, voz_nome (en-andrew, en-ava, es-alvaro… ver listar_vozes), original_db=-22 (voz original baixa, como referência de ritmo) ou -99 para tirar de vez, estilo="padrao", formato="9x16")`.
4. Ler o JSON: a ferramenta já renarra com a voz até 20 % mais rápida quando metade ou mais dos blocos não cabe (`velocidade_automatica: true`, `velocidade` usada). Se mesmo assim `acelerados` ficar acima de um terço dos blocos ou `atraso_max_s` > 1 → encurtar os blocos longos do SRT (traduzir mais enxuto) e rodar de novo. No `## Resumo`, diga a velocidade usada e quais blocos passaram pelo atempo. Ouvir pelo `revisar_video` (ele avalia sincronismo e legibilidade); corrigir uma vez o que for grave.
5. Também `16x9` se pedido. Entregar `final_9x16_<idioma>_dub.mp4`, `final_9x16_<idioma>_dub.srt`, `legenda-<idioma>.srt`.
6. Mensagem final no idioma de destino: `## Legenda do post`, `## Hashtags`, `## Título (YouTube)`, `## Gancho`; e em português `## Resumo` (voz, blocos, acelerados, atraso máximo, se a voz original ficou ao fundo), `## Pendências` (termos `[CONFERIR]`, trechos em que a dublagem atrasou) e `## Arquivos`. Não publicar.
