# Fluxo: depoimentos-semanais

Carrossel semanal de depoimentos (prints de alunos) no padrão do designer da Grava Simples: fundo preto com brilho, título "QUEM GRAVA SIMPLES / APROVA!", três prints por tela como cartões 3D, selo "DEPOIMENTO REAL DO ALUNO", última tela com o CTA "Comenta DESCOMPLICA". Molde fixo em `../estilos/depoimentos-semanais/`. Este post NÃO usa o manual marinho/laranja.

Passos para o Editor:
1. Separar os prints em `entrada/` (e em `materiais/_links/<id>/` quando o pedido trouxer link do Drive). Entra só depoimento de aluno (mensagem, comentário, direct). Fica de fora: print que cita concorrente ou tem palavrão, perfil de revista ou página, print ilegível. Prints novos primeiro; prints antigos só para fechar a tela, avisando no relatório quais são reserva.
2. Escrever `saida/<slug>/prints.json`: `[{"arquivo": "...", "nome": "primeiro nome ou @", "corte": [x0, y0, x1, y1]}]`, em ordem de leitura (os três primeiros vão para a tela 1). Corte só para tirar barra do app, cabeçalho, marca d'água "Ativar o Windows" ou balões de outras pessoas; nunca cortar nome ou texto do aluno. Conversa longa → corte no balão do depoimento. Use `info` ou abra a imagem para medir; nada de `editar_foto` aqui.
3. `gerar_carrossel_depoimentos(prints_json="saida/<slug>/prints.json", saida_dir="saida/<slug>")` → `final_tela-01..NN.png` (a última é a tela CTA do molde), `carrossel.pptx` (fundo + cada print como camada, para o Canva), `carrossel.pdf`, camadas e posições em `_trabalho/depoimentos/`. Leia `avisos` no JSON devolvido: "pequeno" → feche o corte no balão; "cobre" → troque a ordem ou o corte; rode de novo até sair sem aviso de cobertura.
4. Conferir cada PNG: texto legível no celular, nenhum cartão cobre texto de outro, nada sai da tela, nomes dos alunos inteiros.
5. Na mensagem final, `## Legenda do post` e `## Hashtags` (sem `post.md`). Descrição na voz do Thiago agradecendo quem escreveu e convidando a comentar DESCOMPLICA para receber o link na DM (CTA de comentário tem responsável: o próprio Thiago). Sem preço, oferta ou número de alunos. Hashtags de 5 a 8.
6. `## Resumo` na mensagem: quais prints entraram (nome, arquivo, tela), quais ficaram de fora e por quê, escalas pequenas ou ampliadas; em `## Pendências`, confirmar se os prints antigos já saíram em semanas anteriores. Versão refeita vai para `_anteriores/` antes de gravar a nova. Não publicar.

## Aprendizados de 06/11/2026 (comparação com o post publicado em 05/11, feito no Máquina de Criativos)
- Os posts publicados (29/10 e 05/11) são 1:1 (1080×1080), não 4:5. Enquanto `gerar_carrossel_depoimentos` só gerar 1080×1350 com 3 prints por tela, montar com o molde `../estilos/depoimentos-semanais/1x1/` e o script `_trabalho-gra47/montar_1x1.py` (detalhes no `LEIA-ME.md` do molde).
- 3 a 4 cartões por tela, grandes, perto das bordas; tira de uma linha vira cartão largo no rodapé da tela.
- Print inteiro com cabeçalho e nome do aluno; cortar só barra de status, teclado e rodapé de dados. Sufixo no nome do contato: apagar com a cor do cabeçalho, não cortar o nome.
- Tela do vídeo: vídeo cortado ao rosto em 3:4 com moldura vermelha fina, sem desfoque lateral.
- Seleção de prints: o Raphael usou todos os 14 (inclusive preço e menção a concorrente censurada). A regra acima (sem preço/concorrente) segue valendo até ele confirmar a mudança; na dúvida, montar com todos e marcar `[CONFERIR]`.
