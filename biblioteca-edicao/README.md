# Biblioteca de edição

O repertório de edição do Editor GS, versionado com o código. Quem instala o plugin ou clona o projeto recebe tudo isto; o agente lê pelo MCP (`biblioteca_edicao`, `ver_estilo_edicao`) e o app mostra em **Estilos › Receitas**.

| Pasta | O que tem |
|---|---|
| `estilos/<id>.json` | Receita de estilo: quando usar, base do motor (estilo, legenda, energia), grafismos e cadência, pesos de transição, alvos de ritmo, estrutura com tempos, regras, o que evitar e o prompt pronto. |
| `padroes/formatos.json` | Medianas e padrões por formato (fala com tela, fala, anúncio, aula, animação, react, carrossel em vídeo) medidos nas referências estudadas. Sem título, link nem autor. |
| `padroes/efeitos.json` | Efeitos vistos nas referências: o que o motor já faz (e quantas vezes aparece) e as lacunas que ainda não temos. |
| `INDICE.md` | Lista das receitas (gerada). |

## Como cresce

1. Referência nova entra no repertório (Referências › garimpo, `adicionar_referencia`, `inventariar_efeitos`). A ficha é privada e fica no workspace da máquina.
2. `destilar_conhecimento` atualiza os padrões sem gastar modelo.
3. O fluxo `destilar-estilos` lê as fichas novas e propõe receitas (novas ou versão melhor de uma existente).
4. Decisão humana em Estilos › Receitas › Propostas: aprovar ou recusar.
5. Aprovada na máquina de desenvolvimento, a receita vai para `biblioteca-edicao/estilos/` e chega a todos no próximo commit e `scripts/publicar_plugin.ps1`. Numa instalação de usuário, fica na biblioteca local dele (`workspace/biblioteca-local/`), que vence a oficial quando o id é igual.

## Regras

- Referência é estudo. A receita descreve técnica, ritmo e estrutura com as nossas palavras; a validação recusa link, @perfil, nome de quem fez a referência e frase copiada entre aspas.
- Efeito só com motivo na fala; a receita dá teto (um gráfico a cada N s), nunca cota.
- O pedido do usuário e o painel Estilo do criativo vencem a receita quando discordam.
