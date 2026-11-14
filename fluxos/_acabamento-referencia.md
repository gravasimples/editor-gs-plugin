# Referência de acabamento (montar_remotion e companhia)

Consulta do agente, não é fluxo de pedido. As REGRAS de quando usar cada coisa estão no AGENTS.md ("Como editar") e no fluxo do pedido; aqui ficam os parâmetros. Em dúvida sobre um parâmetro, a descrição da ferramenta no MCP vale mais que este arquivo.

## Ligar e desligar
- Em `montar_remotion`, `zoom`, `clarao`, `tela_final`, `sfx` e `barra_progresso` em branco seguem o bloco `montagem` do estilo (o `padrao` sai limpo). True/False explícito vence: use só quando o pedido mandar.
- `palavras_chave`, `broll`, `grafismos`, `trilha`, `capitulos` e `gancho_animacao`: vazio = o que o estilo disser; `"nenhum"` desliga mesmo com o estilo em "auto".
- Estilo com a chave `montado` foi montado pelo Raphael na página Estilos: o bloco `montagem` dele manda (zoom, clarão, tela final, vinheta, `transicao` na locução). `formato_preferido` (pip, antes-depois, dividido) vale quando houver os dois vídeos; `terco_inferior` true = terço com o nome de quem fala.
- Fora da paleta (vídeo de cliente, teste de outro visual): estilo inline em `gerar_legenda`, `montar_remotion` e `gerar_capa`: `{"base": "profissional", "legenda": {"cor_destaque": "#F4C2D7", "cor_texto": "#FFF8F0", "contorno": "#3A2A33"}}`. Diga no `## Resumo` que saiu da paleta e por quê.

## Marca e abertura
- `frase_impacto`, `frase_destaque` (a palavra laranja), `tela_cta`, `tela_titulo`, `tela_destaque`.
- `vinheta=True` (abertura de 1 s "Grava Simples"; o vídeo atrasa 1 s: gere a legenda depois, com `legenda_de_srt` sobre o SRT deslocado, ou queime com `montar` em cima).
- `terco_texto="Thiago Gomes"`, `terco_sub="Grava Simples · OBS"` (terço inferior nos primeiros segundos).
- `gancho_animacao="palavra"`: frase de impacto entra palavra por palavra.
- Série recorrente ("O óbvio precisa ser dito", "parte N"): `listar_series`; se não existir, `salvar_serie(nome, titulo, destaque, handle, kicker, trilha)` uma vez; cada episódio `montar_remotion(serie=<nome>, parte=N)` (abertura com o título + selo "Parte N", cartela da série no fim, iguais em todos).

## Legenda
- Modelos em `estilos/legendas/<id>.json`: karaoke-pop, karaoke-classico, palavra-unica, caixa-marinho, digitar, subir, serifada-historia, display-unbounded, minuscula-discreta, alta-tutorial, papel-tweet, youtube-compacta, amarelo-creator (fora da marca). Pedido que cita um modelo: estilo inline `{"base": "<estilo>", "legenda_modelo": "<id>"}` em `gerar_legenda` e `montar_remotion`.
- Legenda cinética (GSAP no Remotion, sem ASS): `legenda_modelo="cinetica-tipografica"` (palavra entra na hora da fala com giro e escala), `"cinetica-maquina"` (letras digitadas com cursor laranja), `"cinetica-onda"` (palavras sobem; a de ênfase faz onda, já com tremor). `legenda_tremor=True` põe tremor na palavra de ênfase de cada linha. Nunca passe `legenda_ass` junto (o resultado avisa em `aviso_legenda`). O `legenda.srt` da entrega continua saindo do `gerar_legenda`. Cite `legenda_cinetica` em **Estilo:**. Só quando o pedido falar em legenda animada, cinética, "estilo Máquina" ou máquina de escrever.
- Legenda traduzida (fluxo `traduzir-legenda`): você traduz o SRT (mesmos tempos, `*palavra*` = destaque) e `legenda_de_srt(srt, saida_ass, estilo, formato)` gera o ASS; `blocos_longos` > 0 pede dividir o bloco.

## Grafismos (plano semântico)
- `planejar_grafismos(palavras_cortado, saida_json="saida/<slug>/grafismos.json"[, gestos_json])` devolve a fala por frase, os tipos e um rascunho. Reescreva o arquivo só com os gráficos que têm motivo (regras no fluxo). Cada item com `palavra` (ou `gesto`) para entrar quando é dita.
- Tipos por motivo: ferramenta citada → `logos` (logos reais; nunca ícone genérico no lugar da marca); enumeração → `pilulas`/`checklist` acumulando; "não precisa X" → `riscado` com `troca`; número → `numero` (no momento-chave `tela_cheia: true`, 2–4 s, a legenda some e a voz segue); comparação → `cartoes` no topo; assunto áudio → `ondas`/`manchete` com `ondas`; contexto do bloco → `kicker` no topo; fim → `cta`.
- `validar_grafismos`: aviso de palavra não achada, sobreposição ou densidade = corrigir antes de montar. Passe `grafismos="saida/<slug>/grafismos.json"` no `montar_remotion` (substitui `palavras_chave`).
- Entrada e saída variam sozinhas; para uma específica: `"entrada"`: mola, mascara, desfoque, deslize, elastico, cair, subir; `"saida"`: some, sobe, mascara, encolhe, desfoque, deslize.
- Em tela dividida o peito cai no rosto: `posicao: "centro"` ou `"topo"`.
- Logo de ferramenta que não existe (aviso do validador): o Raphael põe em `workspace/marca/logos/<nome>.png`; diga em `## Pendências`.
- Gestos: `detectar_gestos(cortado.mp4, "saida/<slug>/_trabalho/gestos.json")` depois dos cortes; tipos `polegar_cima`, `apontar_cima`, `vitoria`, `mao_aberta`, `punho`, `virada_esquerda`, `virada_direita`. Zero eventos é normal. `cutaways` (ele olhando a tela) são candidatos a `broll=` ou bloco `tutorial`; nada entra sozinho.
- Nada de número de alunos, preço ou oferta não aprovada nos gráficos. Cite em **Na tela:** os tipos que entraram e os avisos que ficaram.

## Transições e câmera
- `transicoes="auto"` (os estilos `profissional` e `lista` já ligam): corte seco com troca de enquadramento (aberto/médio/fechado) nas emendas comuns, punch-in (às vezes tremor) quando a palavra de ênfase vem logo depois do corte, transição forte (zoom_blur, deslize, luz, giro; flash no máximo 2) só nas trocas de assunto, e a câmera andando devagar em cada plano.
- `energia`: calmo, normal, dinamico, bem_dinamico (siga o painel Estilo do criativo).
- Mandar numa emenda: `transicoes='{"35.1": "giro"}'`; seco: `'{"12.4": "seco"}'`. `transicoes="nenhuma"` volta ao modo antigo (zoom alternado + clarão).
- `receita_transicoes=<formato>` decide qual forte entra numa troca de assunto, pela proporção do repertório (fala_tela, fala, anuncio, aula, animacao).

## Ritmo e nível 3
- `ritmo_zoom_s=4` (enquadramento muda a cada 4 s), `barra_progresso=True`, `sfx=True`, `capitulos="Item 1@0; Item 2@12"` ou `"auto"` (sai da fala "primeiro… segundo…"; se vier 0, passe à mão).
- `broll="arquivo@inicio@duração@janela"` com material real; `"auto"` usa quadros do próprio vídeo onde a câmera mostra a tela (com travas; `nivel_pro.broll_auto.n` = 0 é normal). Lista manual substitui o automático.
- `trilha="auto"` usa a primeira de `trilhas/` com ducking; `nivel_pro.aviso_trilha` preenchido = pasta vazia, vai em `## Pendências`.
- SFX (`sfx=True`): catálogo CC0 por categoria (whoosh na transição forte, swipe na cortina, pop no gráfico, tick no capítulo, riser antes da manchete, impacto no número, erro no riscado, ding na tela final e no cta). Origem em `remotion/public/sfx/LICENCA.md`.
- O resultado traz `nivel_pro` com o que entrou: cite no `## Resumo`.

## Layouts e formatos
- `layout="painel@0; tutorial@6.5; cheio@20"` (modo@segundo no vídeo cortado), com cortina laranja entre blocos. `painel` = terço de cima marinho com kicker, manchete e logos (abertura, listas); `moldura` = rosto em moldura arredondada com borda laranja (CTA final, fala de personagem); `tutorial` = tela em cima com câmera virtual e rosto embaixo (legenda com `posicao` "centro"); `tela` = só a tela com a voz; `aula` = tela inteira com o rosto recortado no canto. Tutorial, tela e aula pedem `tela=<gravação do OBS>` (passe o `edl_json`: a tela recebe os mesmos cortes quando é da mesma sessão).
- Câmera virtual: `focos="auto"` (prévia com `focos_da_tela`); para mandar: `focos=[{"palavra": "propriedades", "x": 0.72, "y": 0.3, "zoom": 2, "caixa": [0.65, 0.25, 0.14, 0.06]}]` (x, y e caixa de 0 a 1; ache com `extrair_quadros`). Tutorial de 2 a 5 passos: `passos='[{"texto": "Exposição", "palavra": "exposição"}, ...]'`.
- 16:9 de bruto vertical composto (tela em cima, rosto embaixo): detectado sozinho, tela à esquerda e rosto à direita, painel marinho com os grafismos no trecho só de rosto; `layout="composto"` força, `layout="cheio"` mantém o fundo desfocado. Confira `layout.composto`.
- `montar_pip(video_tela, video_rosto, …)` (demonstração: tela cheia, rosto na bolha); `montar_antes_depois(video_antes, video_depois, …)` (comparação de luz, áudio, cenário); `montar_dividido(video_rosto, video_tela, saida, formato)` (rosto e tela com o mesmo peso).
- `montar_react(video_reacao, video_referencia, saida, credito, direitos)` só com `direitos` = proprio, autorizado ou licenca, e o crédito "@perfil" na tela.
- `animar_carrossel(slides, saida, formato="9x16", transicao, audio)`: carrossel vira Reel.
- Estilo `pov` (bastidor gravado na hora): legenda pequena, terço, sem zoom, clarão nem tela final.
- Vídeo com mais de uma pessoa: `reenquadrar` com modo `falante` ou `dividido`; `detectar_cenas` para não cortar no meio de um plano.

## Repertório de referências
- `consultar_repertorio(formato)`: alvos medidos (Máquina e Reels que engajam) e receita nestes parâmetros. `ver_ficha_repertorio(id)` traduz "edita como a referência X" em `layout=`, gráficos e `transicoes=`.
- `comparar_com_repertorio` depois do acabamento: só excesso e ritmo arrastado contam.
- Referência é estudo: nunca copiar texto, imagem ou áudio dela. `adicionar_referencia` só quando o Raphael pedir.
- Garimpo (só quando o Raphael pedir referências novas): `buscar_referencias_youtube(termos)`; `listar_candidatos_referencia`; `decidir_candidato_referencia(id, aprovar|rejeitar, por="Raphael", formato)` só com a decisão dele na conversa.

## Prévia, versões e conferência visual
- `previa=True` em `montar`/`montar_remotion` grava `<saida>_previa.mp4` em 720p; custa quase o mesmo que o final, então só quando alguém vai olhar antes.
- `folha_contato(video, saida_png, max_quadros=16, por_cena=True, inicio_s, fim_s)`: grade de quadros com o instante, para olhar o vídeo pela imagem (use também para conferir uma emenda suspeita).
- `comparar_versoes(edl_a, edl_b, grafismos_a, grafismos_b, estilo_a, estilo_b)`: o `resumo` vira o tópico **Mudou:**.

## Outros
- `exportar_capcut_fiel(final_entregue)`: rascunho no CapCut igual à entrega. `exportar_capcut(video_ORIGINAL, nome, edl_json, palavras_json)` só para vídeo que não passou pelo `montar_remotion`.
- `grafismo_hyperframes(...)`: teste; só quando o pedido citar HyperFrames.
