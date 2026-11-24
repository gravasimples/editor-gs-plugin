# Fluxo: referencia-analise

Analisar um vídeo de referência (de outro criador ou nosso) e registrar o que faz ele funcionar, sem produzir nada.

Passos para o Editor:
1. Ler `referencias/<id>/referencia.json` (link, nota do Raphael, autor, duração). Se `status` não for `pronto` ou faltar o vídeo, esperar até 2 min e reler; se continuar faltando, escrever a análise só pelo link/nota e avisar.
2. `info` + `transcrever` o vídeo da referência (SRT em `referencias/<id>/transcricao.srt`).
3. `revisar_video` na referência com `prompt_extra` pedindo: gancho (primeiros 3 s), estrutura (blocos e tempos), ritmo de corte, texto na tela, legenda, enquadramento, CTA, trilha, o que prende e o que sobra.
4. Escrever `referencias/<id>/analise.md` (memória para o fluxo minha-versao) e repetir o mesmo conteúdo na mensagem final da issue (o app mostra na conversa e na página Textos), com exatamente estas seções: `## Resumo` (3 linhas), `## Gancho`, `## Estrutura` (tabela tempo × o que acontece), `## Por que funciona` (5 pontos com evidência do vídeo), `## O que não copiar` (o que não cabe para o público iniciante da Grava Simples ou é claim/opinião do outro criador), `## Como virar Grava Simples` (3 ângulos possíveis, cada um com gancho sugerido na voz do Thiago e o recurso do OBS/webcam/áudio que demonstra), `## Pendências`.
5. Não editar, não publicar, não escrever no Notion. Não atribuir opinião ao Thiago. Não copiar frases da referência como se fossem nossas.
