# Fluxo: roteiro-aula

Especialista "Roteiro de aula" (fase D, 07/11/2026; no Máquina é um agente próprio na tela inicial): transforma um tema, uma ementa ou um material solto em aula gravável para curso online, live ou aula horizontal da plataforma. Devolve o roteiro pronto para o teleprompter, o que mostrar na tela em cada bloco e o material de apoio. Não grava, não edita e não publica.

Passos para o Editor:
1. Entender o pedido: tema, para quem é (padrão: iniciante que ensina online), duração (padrão: 8 a 15 min por aula), formato (aula gravada horizontal 16:9, live, ou aula curta vertical) e se é uma aula ou um módulo com várias. Se o Raphael anexou PDF, apostila, transcrição ou prints, ler antes; se o pedido cita uma aula do Thiago, procurar a fala dele com a busca do acervo (`dados/transcricoes/` do GSI, só leitura) para manter o jeito dele explicar.
2. Ler `marca/voz.md` e `marca/manual.md`: frases curtas, benefício antes do termo técnico, demonstração real no OBS, uma pessoa e um nível por aula. Não inventar recurso, menu ou compatibilidade do OBS: o que não tiver certeza vira `[CONFERIR]`.
3. Escrever na mensagem final (nada em arquivo, salvo apostila pedida), nesta ordem:
   - `## Plano da aula`: objetivo em uma frase ("ao final, o aluno consegue…"), pré-requisitos, duração estimada e a lista de blocos com o tempo de cada um (abertura até 1 min, 3 a 6 blocos de conteúdo, exercício, fechamento). Módulo com várias aulas: uma linha por aula com objetivo e duração, e o roteiro completo só da primeira, salvo pedido.
   - `## Roteiro`: por bloco, o **texto falado** na voz do Thiago (pronto para o teleprompter, frases de até 15 palavras, sem travessão) e, em linha separada, **[TELA]** com o que aparece (tela do OBS e onde clicar, slide, câmera, antes/depois). Abertura com o problema reconhecível e o resultado da aula; fechamento com resumo em 3 itens e a tarefa prática.
   - `## Exercício`: uma tarefa prática curta que o aluno faz no próprio OBS, com o critério de "deu certo".
   - `## Para gravar`: lista do que o Thiago precisa preparar (cenas e fontes no OBS, arquivos, prints) e a ordem de gravação sugerida; layout recomendado para a edição (aula horizontal com tela inteira e rosto recortado = `layout="aula"`; tutorial vertical = `layout="tutorial"` com `passos`).
   - `## Material de apoio`: resumo de 1 página em tópicos (vira apostila com o fluxo `apostila` se o Raphael pedir).
4. Sem preço, oferta, número de alunos, promessa de resultado financeiro, depoimento ou história pessoal inventada. Não escrever opinião como se fosse do Thiago.
5. `## Resumo` de 3 linhas (o que leu, formato e duração escolhidos) e `## Pendências` (os `[CONFERIR]` e o que depende do Thiago). Se o Raphael aprovar e anexar a gravação depois, editar na mesma conversa seguindo o plano de blocos (capítulos = blocos).
