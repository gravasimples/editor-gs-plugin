# Fluxo: cortes-longos (Clipador)

Transformar live, aula, vídeo do YouTube, call ou reunião de mentoria em cortes curtos. Duas fases: PROPOR (este fluxo) e EDITAR (uma conversa por corte aprovado, com o reels-padrao).

Fase PROPOR, passos para o Editor:
1. `info` do vídeo. Se o pedido vier com link (YouTube/live), o vídeo já está em `clipes/<id>/origem.mp4`; se vier arquivo, em `entrada/`.
2. `transcrever` com SRT (modelo `small`; vídeo acima de 40 min pode usar `vad=true` e seguir).
2b. `detectar_cenas` no vídeo: saber onde a câmera corta ou troca para a tela (não terminar um corte no meio de um plano; se alterna rosto e tela, anotar `enquadramento` = tela ou rosto por corte).
3. `propor_cortes_longos` com n = 12 (min 20 s, max 75 s). Cada candidato traz `pontuacao_detalhe` (densidade de fala, gancho na abertura, número, pergunta, emoção, duração ideal, completude = termina em fim de frase, tópico novo) e limites já puxados para fronteiras de frase. Use como ponto de partida, não como veredito. Depois leia a transcrição inteira por cima e acrescente candidatos que a regra não pegou (resposta completa a uma pergunta, história com começo-meio-fim, demonstração de um recurso, erro comum + correção, bastidor). Remova candidatos que começam ou terminam no meio de uma frase: ajuste início e fim para fronteiras de frase.
4. Nota de 1 a 5 com a rubrica (estilo OpusClip, explicada no `motivo`): gancho nos 3 primeiros segundos (frase que faz parar), fluxo (o trecho se entende sozinho, começa e termina em frase completa), valor (ensina, prova ou emociona), relevância para quem ensina online e grava sozinho, e ritmo (sem pausa longa). Corte com um só desses fortes vale no máximo 3.
4b. Para cada corte escolhido (entre 6 e 12), escreva: `titulo` (até 8 palavras), `gancho` (frase de impacto até 8 palavras, uma em destaque), `motivo` (por que vira conteúdo: pergunta recorrente, dor, prova, bastidor), `tema`, `nota` de 1 a 5 e `tipo` (tutorial | resposta | historia | opiniao | bastidor).
5. Gravar `saida/<slug>/cortes.json` com exatamente: `{"origem": "<caminho do vídeo>", "duracao_s": <n>, "tipo_origem": "live|youtube|call|aula", "cortes": [{"id": "c01", "inicio": <s>, "fim": <s>, "duracao": <s>, "titulo", "gancho", "destaque", "motivo", "tema", "tipo", "nota", "pessoas": "<quem aparece ou fala além do Thiago, ou vazio>"}]}`, ordenado por nota. Na mensagem final: `## Resumo` com a lista resumida (tabela) e `## Pendências` (o que ficou de fora e por quê). Sem `relatorio.md`.
6. Não extrair nem editar nada nesta fase. O Raphael escolhe os cortes no app; cada escolhido vira um pedido com o reels-padrao.

Regras para call, mentoria e consultoria (`tipo_origem` = call):
- Outras pessoas aparecem ou falam: anotar em `pessoas`. Corte com aluno ou cliente falando só vira conteúdo público com autorização registrada (regra da Grava Simples: depoimento só com direitos aprovados). Preferir trechos em que só o Thiago fala e explica.
- Não incluir dados pessoais, telas com e-mail, nome completo, documento ou valores de cliente. Se a tela mostrar isso, marcar no `motivo` que precisa de blur e deixar nota ≤ 2.

Enquadramento na fase EDITAR: vídeo horizontal com uma pessoa → `reenquadrar` modo `rosto`; com duas ou mais pessoas (call, podcast) → modo `falante` (segue quem fala pelo movimento da boca) ou `dividido` (dois rostos empilhados no 9:16); trecho de tela (slides, OBS) → `montar` com fundo desfocado ou enquadramento auto. Se o modo pedido falhar, cair para `rosto` e avisar.

Fase EDITAR (pedido criado pelo app para cada corte): `extrair_trecho` do vídeo de origem com `palavras_json` da transcrição completa (tempos rebaseados) e seguir o `reels-padrao` do passo 3 em diante, usando `gancho` e `destaque` do corte como frase de impacto. Se o corte vier de call, aplicar as regras acima e registrar no relatório quem aparece.
