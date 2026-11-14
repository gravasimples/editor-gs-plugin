# Fluxo: reels-padrao

Vídeo de fala do Thiago → Reels 9:16 (e 16:9) pronto para postar: fala que faz sentido do começo ao fim, sem erro nem pausa sobrando, legenda karaokê e só os efeitos que a fala pede. Legenda também em arquivo separado.

A ordem é fixa: **entender → decidir a história → cortar → conferir → acabamento com motivo → revisar → entregar.** Não pule etapa para chegar mais rápido ao render: refazer render custa mais que ler a transcrição.

## 1. Entender (antes de qualquer corte)
1. `info` do vídeo. Sem áudio e com `.m4a` do microfone na entrada: `sincronizar_audio` primeiro.
2. `transcrever` com SRT.
3. **Leia a transcrição inteira.** Escreva para você, em 3 a 5 linhas (vai no comentário de plano, regra 1b do AGENTS): a ideia central em uma frase; a ordem da história (gancho → explicação/demonstração → fecho); quais trechos são refação ou take abandonado e qual take fica (o mais completo e fluente, não necessariamente o último); o que é desvio que não serve à ideia.
4. `consultar_repertorio(formato)` (fala_tela com tela do OBS; fala só câmera; anuncio para ADS): os `alvos` são referência de ritmo, não meta. O pedido, o estilo e o sentido da fala vencem o repertório.

## 2. Decidir a história e propor os cortes
5. `propor_cortes` com o modo da energia pedida (painel "Estilo do criativo" ou pedido): calmo/normal → `normal`; dinâmico → `dinamico`; bem dinâmico → `bem_dinamico`. Sem indicação: `dinamico`. Se `precisa_aprovacao`, mostre o resumo e espere (regra 4 do AGENTS).
6. **Revise a EDL contra o que você escreveu no passo 3, ANTES de cortar:**
   - leia `removidos`: cada refação traz `fica_a_versao`; se o take bom é o tirado, troque com `ajustar_edl(manter_extra=[[ini, fim]], remover_extra=[[ini, fim]])`. `conferir_takes` lista os casos suspeitos;
   - refação, frase pela metade ou desvio que a regra não pegou → `remover_extra`;
   - trecho útil que a regra tirou (ligação entre ideias, exemplo, número) → `manter_extra`;
   - conectivo sobrando ("e", "então", "aí" que não liga nada) você tira à mão; a regra não tira mais conectivo sozinha.
7. `conferir_emendas(edl_json, palavras_json)`: leia o `texto_final` de ponta a ponta como espectador e cada emenda com alerta. Corrija com `ajustar_edl` e confira de novo até não sobrar alerta que você não saiba justificar. Critério: toda frase termina, a seguinte começa num ponto que faz sentido, nenhuma palavra repetida na emenda, nenhuma palavra cortada pela metade. Se sílabas somem no fim das frases (fala que termina fraca), rode `propor_cortes` de novo com `pausa_max_audio_s=0`.

## 3. Cortar e legendar
8. `cortar_e_legendar(video, palavras_json, edl_json, saida_video, saida_palavras, formatos="9x16,16x9", estilo)`: corta, remapeia as palavras pelas durações reais e gera a legenda ASS. Confira `drift_quadros` (até 1), `palavras_recortadas_na_borda` (deve ser 0 ou justificado) e `avisos` (palavras que caíram em trecho cortado: confirme que era para sair). Sem script próprio, sem retranscrever o cortado.

## 4. Acabamento: cada efeito com um motivo
9. Frase de impacto (gancho, até 8 palavras, uma em destaque) e CTA da tela final, tirados da fala e do objetivo.
10. Escolha o nível pelo estilo (o pedido pode subir ou descer) e respeite o que o estilo desliga: em `montar_remotion`, parâmetro em branco segue o bloco `montagem` do estilo; diga True/False só quando o pedido mandar. Para desligar o que o estilo liga em "auto": `"nenhum"` (grafismos, broll, trilha, palavras_chave, capitulos, gancho_animacao) ou `sfx=False`.
    - **Nível 1 · limpo** (`padrao`, `bastidor`, `pov`): cortes, legenda, frase de impacto, capa. Sem zoom, clarão, tela final ou gráficos, salvo pedido.
    - **Nível 2 · dinâmico** (`tutorial`, `opiniao`): + o que o estilo ligar (zoom por frase, clarão, tela final, terço/vinheta).
    - **Nível 3 · profissional** (`profissional`, `lista`): + plano de grafismos, `transicoes="auto"` com a `energia`, barra de progresso, sfx; em `lista`, capítulos.
11. Regras de motivo (valem em todos os níveis):
    - **Transição forte** (deslize, zoom com desfoque, luz, giro, flash) só em troca de assunto, capítulo ou bloco novo. Dentro do mesmo assunto: corte seco com troca de enquadramento ou punch-in na palavra de ênfase. O motor já faz assim; para mandar numa emenda: `transicoes='{"35.1": "giro"}'` ou `'{"12.4": "seco"}'`.
    - **Gráfico** só quando a frase tem motivo visual: ferramenta citada (logos reais), enumeração (pílulas/checklist), número (numero), comparação (cartões), negação com troca (riscado), mudança de assunto (kicker), fim (cta). Teto: 1 no peito a cada 4 s. Gráfico decorativo ou que repete a legenda sai. Em `planejar_grafismos`, o rascunho automático é ponto de partida: apague o que não tiver motivo e confira em `validar_grafismos` que cada `palavra` é dita naquela frase (aviso de palavra não achada = corrigir antes de montar).
    - **Zoom/punch**: ênfase ou troca de enquadramento para esconder o corte; nunca dois colados (≥ 1,2 s entre efeitos). **Tremor**: só em palavra de impacto, no máximo um a cada 6 s, nunca em texto que está sendo lido.
    - **Som**: whoosh só onde há transição forte, pop no gráfico que entra; nada de som em corte seco. Música sempre abaixo da voz (o motor faz ducking).
    - **Gesto** (`detectar_gestos`, nível 3): só vira gráfico quando o gesto acompanha o sentido (polegar com lista ou aprovação, dedo com "olha isso"). Polegar solto não vira checklist.
12. `montar_remotion` 9x16 e 16x9 (parâmetros em `fluxos/_acabamento-referencia.md`). Pedido automático (Clipador, pulso, "pode aplicar sem aprovação"): render final direto e confira com `folha_contato(final_9x16.mp4, "_trabalho/folha.png")`. Prévia (`previa=True`) só quando alguém vai olhar antes.
13. `gerar_capa` com o gancho, num instante com o rosto visível.

## 5. Revisar
14. `comparar_com_repertorio(...)`: aponta só excesso e ritmo arrastado. Ter menos gráfico ou mais corte seco que a referência não é defeito.
15. `revisar_video(final_9x16, saida_json, palavras_json=<palavras do cortado>, grafismos_json=<plano usado>, pedido=<estilo e objetivo numa frase>)`. No máximo 2 rodadas (a segunda só no trecho corrigido, com `inicio_s`/`fim_s`). Refaça o que bater nestes critérios: **fala desconexa ou take repetido** (continuidade, take_repetido); palavra ou frase cortada; legenda fora de sincronia acima de 0,3 s; **efeito sem motivo ou em excesso**; grafismo tampando o rosto; áudio abaixo de −20 LUFS. O resto, e o que sobrar depois da segunda rodada, vai para `## Pendências` com o instante. Versão refeita: `comparar_versoes` antes do render final; o `resumo` vira o tópico **Mudou:**; a anterior vai para `_anteriores/`.

## 6. Entregar
16. `exportar_capcut_fiel` com o `final_*.mp4` entregue (nome `GS <data> <tema>`).
17. Mensagem final (regra 5 do AGENTS): `## Resumo` (Duração X → Y; **Corte:** o que saiu, qual take ficou e por quê; **Na tela:** cada efeito e o motivo; **Estilo:**; **Som:**), `## Legenda do post`, `## Hashtags`, `## Título (YouTube)`, `## Gancho`, `## Pendências`, `## Arquivos`.

## Variações de formato
- Bruto 16:9 que vira 9:16: `reenquadrar` (segue o rosto) antes do acabamento; não recorte à mão.
- Tutorial com rosto e tela em arquivos separados: `montar_dividido`, `montar_pip` (demonstração) ou `layout="tutorial@…"` com `tela=`.
- 16:9 de bruto vertical composto (tela em cima, rosto embaixo): o `montar_remotion` monta tela à esquerda e rosto à direita sozinho; confira `layout.composto`.
- B-roll: `buscar_material(tema do trecho)`; Drive primeiro, banco gratuito só como contexto, com `atribuicao` no `## Resumo`; nunca no lugar do Thiago, do setup ou da tela do OBS.
- Legenda cinética (`legenda_modelo="cinetica-…"`) só quando o pedido falar em legenda animada, cinética ou "estilo Máquina"; nesse caso não passe `legenda_ass`.
