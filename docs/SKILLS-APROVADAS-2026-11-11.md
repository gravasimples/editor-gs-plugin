# Skills aprovadas pelo Raphael em 11/11/2026: avaliação e incorporação

Textos de conhecimento (propostas, ainda não padrão) em `EditorGS/workspace/conhecimento/skill-*.md`. Nada foi instalado nem executado; só README/SKILL.md lidos no GitHub. Comparação feita com as ferramentas do MCP `editor-de-video` (já temos: detectar_silencios, propor_cortes, ajustar_edl, aplicar_cortes, recortar_rosto, reenquadrar, planejar/validar_grafismos, revisar_video, folha_contato, adicionar_trilha, comparar_versoes, repertório, etc.).

## Tabela

| Item | Licença | O que aproveitar | Como | Esforço |
|---|---|---|---|---|
| video-use | MIT | Limiares de corte (folga 30-200 ms; pausa >= 400 ms corta, 150-400 olhar, <150 não); fade 30 ms por emenda; legenda 2 palavras maiúsculas; durações de cartão; ducking 12-15 dB; autoavaliação de ±1,5 s por emenda, máx. 3 rodadas | Regra no conhecimento (feito) + ferramenta/parâmetro: fade em aplicar_cortes; checagem de emenda em revisar_video | Texto: feito. Código: pequeno/médio |
| AskEditor (41 skills) | MIT | Ordem cortes > cor > 1 grafismo > som; área segura; efeitos "palavra atrás da cabeça", spotlight, tier list, contador, antes/depois | Regra no conhecimento (feito) + tipos novos em planejar_grafismos ('atras', 'tier', 'spotlight') | Texto: feito. Código: médio/grande |
| 2BFT | MIT | Suavização do caminho de reenquadro, aviso de ampliação > 2,5x, pausa pelo ruído medido, tremor por energia, -14 LUFS + QC, denoise | Regra (feito) + ajustes em reenquadrar, detectar_silencios (limiar adaptativo), transicoes (energia), etapa de denoise e QC de loudness | Texto: feito. Código: médio |
| Claude Edit (ctskool) | README diz MIT; catálogo diz sem licença clara; tratar como só-ideia | Notas com tempo no quadro exato, mudar só o anotado, render parcial por batida, paradas de aprovação | Regra (feito) + UI de notas na página da conversa que vira ajustar_edl/grafismos + render parcial no montar_remotion | Texto: feito. Código: grande |
| Kev's Talking Head | MIT | Re-transcrever após cortar (acha recomeço escondido); logo automática do produto citado; contador numérico; layout faixa (já temos painel) | Regra (feito) + passo "retranscrever e validar" + tipo 'numero' + busca de logo em validar_grafismos | Texto: feito. Código: pequeno/médio |
| Shorts (MarioRodrigues10) | MIT | Corte onde a voz começa/termina; respiro quase mudo; revisão "de ouvido" com avisos; 8 estilos de legenda incl. pilha; editar apagando palavras | Regra (feito) + prévia de estilos na página Estilos; comparar detector de refação com 'recomeço' do propor_cortes | Texto: feito. Código: pequeno (prévia), grande (editar por texto) |

## Tarefas para o Codex (código)

1. Fade de áudio de 30 ms em toda emenda em `aplicar_cortes` (parâmetro `fade_ms`, padrão 30). Esforço: pequeno.
2. Checagem de fronteira em `revisar_video`: quadros ±1,5 s por emenda, avisar pulo visual/estalo/legenda escondida; limite de 3 rodadas. Esforço: médio.
3. Passo "retranscrever o resultado e apontar recomeço remanescente" depois de `aplicar_cortes`. Esforço: pequeno.
4. `detectar_silencios` com limiar adaptativo (nível de ruído medido) e classes por duração (>= 400 ms / 150-400 / < 150). Esforço: pequeno/médio.
5. `reenquadrar`: suavização em 5 passos (preencher, mediana, gaussiana, zona morta, gaussiana), segurar última posição e relatar taxa de acerto, aviso de ampliação > 2,5x. Esforço: médio.
6. `transicoes='auto'`: dosar punch-in/tremor pela energia RMS da fala (`energia='auto'`). Esforço: médio.
7. QC final de loudness (-14 LUFS, pico <= -1 dBTP) e etapa opcional de denoise antes de cortar. Esforço: médio.
8. Novos tipos em `planejar_grafismos`: 'numero' (contador animado), 'atras' (texto atrás do rosto via recortar_rosto), 'tier', 'spotlight'. Esforço: grande.
9. Logo automática: `validar_grafismos` buscar em marca/logos quando faltar. Esforço: pequeno.
10. Página Estilos: prévia visual dos estilos de legenda; adicionar estilo "pilha". Esforço: pequeno/médio.
11. Notas com tempo na página da conversa (player com tecla de nota) mapeadas para `ajustar_edl`/grafismos, e render parcial por batida no `montar_remotion`. Esforço: grande.
12. Editar por texto (apagar palavras no transcrito gera EDL). Esforço: grande; baixa prioridade.

## Descartar ou adiar

- Editar por texto (Shorts): duplica o fluxo atual de EDL; adiar.
- Pacote AskEditor inteiro (41 efeitos, em inglês, só macOS): pegar só as 4 ideias listadas; os 20 grafismos genéricos não são do nosso nicho.
- Busca de música/tendências e stems do 2BFT: fora do escopo e com risco de licença; não adotar.
- Transcrição ElevenLabs (video-use): temos Whisper local; não trocar.
