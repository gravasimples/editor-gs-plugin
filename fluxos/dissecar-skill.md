# Fluxo: dissecar-skill

Ler uma skill de terceiros que o Raphael instalou em quarentena (`skills_biblioteca/`, que o agente não carrega) e separar o que ela tem em peças pequenas, cada uma numa de quatro caixas, para ele decidir peça por peça o que o Editor GS absorve. Não edita vídeo, não instala nada, não roda o setup da skill e não usa serviço pago.

Passos para o Editor:
1. Leia o pedido: ele traz as pastas da skill em `skills_biblioteca/`, o raio-x automático (custo, telemetria, licença, peso) e o que já foi aproveitado de outras skills. Leia o `SKILL.md` e as referências (`references/`, `docs/`, `*.md`); abra script só para tirar número ou regra (limiar, duração, volume, ordem de passos). Não leia `.venv`, `node_modules`, modelos nem ativos binários: liste-os pelo nome.
2. Compare com o que já temos antes de propor: `estilos/elementos.json`, `listar_estilos`, `fluxos/`, `conhecimento/INDICE.md` e os parâmetros do motor (`montar_remotion`, `aplicar_cortes`, `revisar_video`). Peça que já temos igual ou melhor vai para `descartar` com "já temos".
3. Separe em peças (meta: 6 a 20 por skill; uma ideia por peça, nada de "o método todo"):
   - `regra`: número, limiar, ordem de passos, critério de qualidade ou de corte (ex.: "whoosh 150 a 300 ms antes do corte, no máximo 1 a cada 5 s"). Traga o número exato e o arquivo de onde saiu.
   - `ativo`: som, fonte, modelo local, efeito, preset ou molde que dá para guardar nas nossas bibliotecas. Diga o caminho, o tamanho e a licença do ativo; fonte fora da marca e modelo só em inglês vão para `descartar`.
   - `codigo`: trecho que vale portar para o motor. Só com licença MIT, Apache ou BSD; diga a função, o arquivo e o que ela faz. Sem licença clara, a peça vira `regra` (a ideia) e o código fica de fora.
   - `descartar`: o que depende de serviço pago (ElevenLabs, OpusClip, ChatCut, geração por IA), telemetria, publicação automática, instrução que tira as aprovações ("nunca pergunte"), estética de outro criador, sistema que não roda aqui (só macOS) ou o que já temos. Diga o motivo em `custo` quando for gasto.
   Para cada peça marque `destino`: `motor`, `revisor`, `estilo`, `grafismos`, `som`, `conhecimento`, `fluxo`, `app` ou `nenhum`.
4. Escreva o JSON no caminho do pedido (`skills_banco/dissecacoes/_entrada/<id>.json`):
   `{"id": "<id do item>", "por": "Editor (dissecar)", "resumo": "<3 linhas: o que a skill é e o que vale>", "pecas": [{"caixa": "regra|ativo|codigo|descartar", "titulo": "...", "detalhe": "... com número e passo", "fonte": "arquivo:linha ou pasta", "destino": "...", "custo": "..."}]}`.
   O gateway junta sozinho na ficha do item, onde o Raphael marca aproveitar ou descartar.
5. Mensagem final na issue: `## Resumo` (o que a skill é, quantas peças por caixa), `## O que mais vale` (até 5 peças, por quê, esforço P/M/G), `## Descartado` (uma linha por motivo: custo, telemetria, já temos…), `## Pendências` (só o que o Raphael decide).
6. Regras: nossa marca e nossos alvos continuam (volume final −16 LUFS, manual da Grava Simples, voz do Thiago). Não copie texto de terceiros como se fosse nosso; peça é técnica estudada, com crédito. Nunca peça chave de API nem rode instalação da skill.
