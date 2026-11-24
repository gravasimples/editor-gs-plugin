# Fluxo: destilar-estilos

Transformar as referências novas do repertório em receitas da biblioteca de edição (`biblioteca-edicao/`). Não edita vídeo. Cada receita é uma proposta: só entra na biblioteca quando o Raphael aprova em Estilos › Receitas. Aprovada na máquina de desenvolvimento, ela vai para o GitHub e para o plugin de todo mundo; por isso a receita é técnica com as nossas palavras, sem nada da referência.

Passos para o Editor:
1. `destilar_conhecimento()` atualiza os padrões medidos e devolve `pendentes` (fichas decupadas que ainda não sustentaram receita), por formato.
2. Para cada formato com pendentes: `consultar_repertorio(formato, n=6)` e `ver_ficha_repertorio(id)` das pendentes. Leia `abertura`, `receita`, `por_que_funciona`, a decupagem trecho a trecho e as medidas. `catalogo_efeitos()` mostra os efeitos que essas peças usam e o nosso equivalente.
3. `biblioteca_edicao(formato=…)` antes de propor. Se uma receita existente já cobre o padrão, proponha a versão melhorada com o MESMO `id` (ajuste alvos, cadência, regras) em vez de criar outra. Receita nova só quando o padrão é diferente: estrutura, energia ou grafismo que nenhuma tem.
4. Monte cada receita no vocabulário do motor (`propor_estilo_edicao` recusa o que o motor não entende): `base_estilo` de `estilos/`, `legenda` de `estilos/legendas/`, `grafismos.tipos` e `visual` de `planejar_grafismos`, pesos de transição (`seco`, `punch`, `deslize`, `zoom_blur`, `flash`, `tremor`, `luz`, `giro`), chaves de `montagem` que os estilos já usam, alvos medidos (`pausa_max_s`, `palavras_por_s`, `duracao_s`). `estrutura` com tempos (0–3 s: …), `regras` com número, `evitar` com o erro concreto e `prompt` como o Raphael escreveria o pedido (até 1400 caracteres).
5. Proibido na receita: nome de criador, perfil, link, título da referência, frase dela entre aspas, preço, número de aluno. Diga o que fazer, não de onde veio. As fichas que sustentam a receita vão em `referencias` (ficam só nesta máquina).
6. Meta: até 3 propostas por rodada, cada uma com pelo menos 2 fichas de apoio. Padrão visto numa ficha só fica para a próxima rodada.
7. Mensagem final: `## Resumo` (quantas fichas lidas, quantas propostas, quais melhoram receita existente), `## Propostas` (uma linha por receita: nome, para que serve, o que muda), `## Pendências` (o que o Raphael decide).
