# Editor manual no app e CapCut fiel — estudo e proposta (12/11/2026)

## Por que o "Abrir no CapCut" sai genérico
`editor_video/capcut.py` exporta só duas coisas: uma faixa de vídeo com os cortes e uma faixa de texto com a legenda simples. Grafismos, layouts (tela dividida, PiP, fundo desfocado), zooms, b-roll, trilha com ducking, efeitos sonoros e transições ficam de fora. Por isso o CapCut abre com cara genérica: não é limitação de reconhecimento de material, é o que mandamos.

## CapCut fiel (proposta, em fases)
Escrever o rascunho nós mesmos (schema conferido no pyCapCut, que não declara licença: só referência), sempre a partir de modelo capturado da versão instalada (9.6), com a atualização automática do CapCut desligada (relatos de que a 10.x recusa rascunho feito por ferramenta).

| Elemento | Como vai | Editável no CapCut |
|---|---|---|
| Cortes | faixa principal (já existe) | sim |
| Zoom / punch-in / enquadramento alternado | keyframes de escala e posição no clipe | sim |
| Layouts (tela dividida, PiP) | segunda faixa com o mesmo arquivo + recorte/máscara; fundo desfocado como preenchimento de fundo | sim |
| B-roll | faixa de sobreposição | sim |
| Trilha e SFX | faixas de áudio; ducking vira keyframes de volume; fades nativos | sim |
| Transições | mapa curto para equivalentes gratuitos do CapCut (dissolver, zoom, deslizar); ids tirados de um rascunho real da 9.6 | sim (troca no CapCut) |
| Grafismos, legenda animada, barra, capítulos, terço inferior | camada pré-renderizada transparente por cima | mover/apagar; texto não |
| Legenda simples | texto nativo numa faixa oculta (plano B para corrigir palavra) | sim |

Teste pendente (decide a camada transparente): projeto "Editor GS - teste transparencia" na lista de rascunhos do CapCut, com fundo marinho + uma faixa ProRes 4444 (caixa laranja) + uma faixa WebM VP9 (caixa branca). Se as caixas aparecem sem fundo preto, o formato funciona. Se nenhuma funcionar, a reserva é fundo verde + chroma do CapCut (bordas um pouco piores).

## Editor manual dentro do app (mini CapCut nosso)
Recomendação: `@remotion/player` + timeline headless (dnd-timeline, MIT) editando o **mesmo JSON de props** que o agente usou para renderizar; re-render no servidor com o motor atual. Assim não existem dois modelos de dados, e tudo que o agente sabe fazer (grafismos, layouts, legendas, trilhas) aparece editável sem conversão.

Descartados: forks de editores com motor próprio (OpenCut, Omniclip, openvideodev) — teríamos de converter nosso projeto; código AGPL/GPL/SUL (OpenChatCut, Etro, Twick) só como estudo. Remotion Editor Starter (US$ 600) poupa ~2 semanas de interface, mas não tem transições nem keyframes e tem modelo de dados próprio.

MVP (5 faixas: cortes, legendas, textos/grafismos, trilha, SFX):
1. Player + carregar/salvar props versionadas (checkpoints já existem) — S
2. Trocar estilo de legenda e corrigir texto de palavra — S
3. Trocar transição em cada corte (catálogo de `@remotion/transitions` + as nossas) — S
4. Trilha: trocar, volume, nível do ducking; SFX num ponto do tempo — S
5. Aparar/mover cortes com legenda acompanhando (ripple) — M
6. Mover/editar textos e grafismos (timeline e na tela) — M
7. Desfazer, validação (zod) e "Renderizar de novo"; o diff vira aprendizado do agente — S/M
Esforço total: M (2–3 semanas de construção). Depois: keyframes, filtros/LUT, máscara, batida da música.

Atenção de licença: uso interno do Remotion é gratuito até 3 pessoas. Vender o Editor GS (plugin para clientes) com o Player embutido cai na categoria paga "Remotion for Automators"/licença de empresa. Confirmar com a Remotion antes de vender — isso já vale hoje, porque o plugin renderiza com Remotion.

## Demos de skills
Página `/demos` (menu Repertório): cada skill instalada edita os mesmos 3 brutos — Reels (`obvio02`, série "O óbvio"), ADS (`ADS-2026-08 - takes Escritório`, Drive › Sander › Agosto) e aula (`AULA-OBS-M03-A02` bruta). Brutos em `workspace/entrada/_demos-skills/`; estado em `workspace/skills_banco/demos.json`. Primeira rodada: GRA-97 a GRA-105 (12/11/2026, 2h).
