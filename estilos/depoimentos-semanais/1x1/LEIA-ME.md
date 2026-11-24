# Molde 1:1 do carrossel de depoimentos (06/11/2026)

Derivado em 06/11/2026 comparando a entrega do Editor (4:5, 3 prints por tela) com o post publicado em 05/11
(`modelo-original/ref-2026-11-05-tela-0N.png`, feito pelo Raphael no Máquina de Criativos). Os dois posts de
referência (29/10 e 05/11) são **1080×1080**; o molde `fundo.png` da pasta de cima está em 1080×1350 e por isso
a ferramenta `gerar_carrossel_depoimentos` não bate com o padrão publicado.

## Arquivos
- `fundo.png`, `fundo-ultimo.png`: o fundo do designer recortado (95 px do topo, 95 px do meio em área escura, 80 px do pé).
  Título em y≈65–195, zona dos cartões 205–870, selo em ≈895, rodapé em ≈1015.
- `tela-cta.png`: a tela CTA exportada pelo Raphael em 05/11, reduzida a 1080.
- Montagem: `workspace/_trabalho-gra47/montar_1x1.py` (reusa `editor_video.depoimentos` com W/H/FAIXA em 1:1,
  vagas P4 = 4 cartões [principal à esquerda, dois à direita, tira larga embaixo], P3A = [principal largo à esquerda,
  pequeno acima à direita, grande abaixo à direita], P3B = [principal alto à esquerda, grande e tira à direita]).

## O que o padrão publicado faz (e o motor 4:5 não fazia)
1. 1:1, 3 a 4 cartões por tela, cartões grandes chegando perto das bordas; sobreposição só em área em branco de outro print.
2. Prints inteiros, com cabeçalho e nome do aluno; tira-se só barra de status, teclado e rodapé de dados (IP/localização).
   Sufixo do contato ("executa 2.0") apagado com a cor do cabeçalho, não cortado.
3. Tiras largas (comentário de uma linha) viram cartão de rodapé em 85–90% da largura, mesmo ampliando 1,3×.
4. Tela do vídeo: vídeo cortado ao rosto em 3:4 (414×552), moldura vermelha fina com sombra deslocada, sem desfoque lateral.
5. Rodapé longo ("…e veja mais comentários") nas telas do meio e curto na última de prints.
6. Seleção: o Raphael usou todos os prints da pasta, inclusive tira pequena, print com preço e menção a concorrente
   já censurada. O fluxo ainda diz para excluir preço/concorrente: confirmar com ele antes de mudar a regra.

Pedido para a ferramenta: aceitar molde 1:1 (W/H lidos do `fundo.png`) e 4 prints por tela, com estas vagas.
