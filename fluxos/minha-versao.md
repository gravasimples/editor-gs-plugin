# Fluxo: minha-versao

Fazer a versão da Grava Simples de um vídeo de referência: primeiro o roteiro, depois (se houver vídeo bruto) a edição.

Passos para o Editor:
1. Se `referencias/<id>/analise.md` não existir, rodar o fluxo `referencia-analise` antes.
2. Escrever o roteiro na mensagem (seção `## Roteiro`; nada em arquivo): gancho até 3 s na voz do Thiago (frases curtas, conversa com um amigo, sem hype), estrutura em blocos com fala e texto na tela, demonstração real do recurso (OBS, webcam, áudio, Meet), CTA orgânico (seguir, comentar só com responsável definido), duração alvo. Público: iniciante que ensina online. Seguir o manual de marca (`../estilos/padrao.json` para o visual; sem preço, oferta ou número de alunos).
3. Criar uma interaction `request_confirmation` com o roteiro resumido e esperar a aprovação do Raphael.
4. Aprovado e com vídeo bruto em `entrada/`: seguir o `reels-padrao` até o fim (com Revisor), citando a referência no `## Resumo`. Sem vídeo bruto: a mensagem final traz `## Roteiro`, `## Legenda do post`, `## Hashtags`, `## Título (YouTube)`, `## Gancho` e `## Para gravar` (cena a cena); nenhum arquivo em `saida/`.
5. Nunca reutilizar imagem ou áudio da referência na entrega.
