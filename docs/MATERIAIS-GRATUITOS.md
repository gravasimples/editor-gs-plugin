# Materiais gratuitos para edição (bancos, música, GIF, ícones) e como o Editor usa

Atualizado: 30/10/2026. Regra que vale acima de tudo (manual da marca): **material real primeiro** (Drive: takes, fotos do Thiago e do setup, prints do OBS). Banco de imagem é só **apoio** (b-roll de contexto, fundo, trilha, efeito sonoro, ícone), nunca no lugar do Thiago, do setup ou da tela do OBS, nem apresentado como se fosse. O Editor cita a origem no `## Resumo`.

## O que já está ligado no app

`buscar_material(tema)` (ferramenta do Editor): procura no espelho do Drive (`materiais/`) por palavras do tema e sinônimos e, com chave, nos bancos abaixo; baixa em `workspace/banco/<fonte>/<id>` com um `<id>.licenca.json` ao lado (origem, autor, URL, licença, texto de atribuição). `listar_banco` mostra o que já foi baixado. Sem chave, o Drive continua funcionando e o banco vira pendência.

| Fonte | O que tem | Como o app acessa | Licença (conferir na página) | O que o Raphael precisa fazer |
|---|---|---|---|---|
| **Drive da empresa** (`Materiais do Editor`) | takes, fotos, prints, trilhas compradas | rclone → `materiais/` + índice | material próprio | organizar as pastas (takes/, fotos/, prints/, trilhas/, logo/) e clicar Sincronizar na Biblioteca |
| **Pexels** (pexels.com) | vídeos e fotos | API, chave gratuita, 200 pedidos/h e 20 mil/mês | Pexels License: uso comercial, sem atribuição obrigatória; crédito ao autor e link "Photos provided by Pexels" recomendados; não usar pessoas/marcas reconhecíveis como endosso | criar conta → pexels.com/api → colar `PEXELS_API_KEY=` no `.env` do Editor GS |
| **Pixabay** (pixabay.com) | vídeos e fotos (música e efeitos só pelo site, sem API) | API, chave gratuita, 100 pedidos/min, cache de 24 h, sem hotlink | Content License: uso comercial sem atribuição; mostrar a origem; pessoas/marcas podem ter direitos próprios | conta → pixabay.com/api/docs → `PIXABAY_API_KEY=` no `.env` |

## Candidatos para a próxima etapa (ainda não ligados)

| Fonte | Tipo | Acesso | Licença | Observação |
|---|---|---|---|---|
| Mixkit (mixkit.co) | vídeos, música, efeitos sonoros, templates | sem API; download pelo site | Mixkit Free License (comercial, sem atribuição); alguns vídeos têm "Stock Video Restricted" (só pessoal): ler o rótulo de cada item | melhor fonte gratuita de trilha + efeito; baixar à mão para `trilhas/` e `materiais/` |
| Pixabay Music / Sound Effects | música e efeitos | só pelo site | mesma Content License | baixar à mão para `trilhas/` |
| YouTube Audio Library (studio.youtube.com) | música e efeitos | só pelo YouTube Studio (sem API) | gratuita; algumas faixas exigem crédito na descrição | boa para vídeos do YouTube; anotar a atribuição no `trilhas/README.md` |
| Free Music Archive (freemusicarchive.org) | música CC | site (sem API pública confirmada) | CC por faixa (BY, BY-NC...): BY-NC não serve para conteúdo com anúncio/oferta | checar a licença faixa a faixa |
| Incompetech (incompetech.com) | música (Kevin MacLeod) | site | CC BY 4.0: exige crédito | crédito na descrição do vídeo |
| Freesound (freesound.org) | efeitos sonoros e samples | API com token; o uso da API é gratuito só para fins não comerciais (licença comercial à parte) | por arquivo: CC0, CC BY, CC BY-NC | usar só itens CC0 e baixar pelo site, não pela API, até decidir a licença da API |
| Openverse (openverse.org) | imagens e áudio CC de várias fontes (Wikimedia, Flickr, Jamendo…) | API pública sem chave | filtra por licença (`license=cc0,by`) | a API não respondeu deste notebook em 30/10 (tempo esgotado); testar de novo antes de ligar |
| Wikimedia Commons | fotos, logos de software (ex.: OBS), diagramas | API pública sem chave (respondeu 200 em 30/10) | por arquivo (CC BY-SA, CC0, domínio público); BY-SA pede crédito e mesma licença | útil para o logo oficial do OBS e capturas antigas; ler a licença de cada arquivo |
| Tenor (tenor.googleapis.com) | GIF | API com chave gratuita do Google | gratuita "por enquanto"; app não pode monetizar a integração | GIF de reação em Reels é raro na marca; baixa prioridade. Giphy passou a cobrar e exige aprovação |
| Klipy (klipy.com) | GIF | API parecida com a do Tenor, plano gratuito | conferir termos comerciais | alternativa se o Tenor acabar |
| LottieFiles (lottiefiles.com) | animações Lottie (ícones animados, transições) | site; `@remotion/lottie` no projeto Remotion | "Lottie Simple License" nas gratuitas, mas a página de cada animação pode ter termos do criador | ler a licença na página; ótimo para ícones animados nas cenas de slide |
| Lucide (lucide.dev), Tabler Icons, Phosphor | ícones SVG | pacote npm ou SVG direto | ISC/MIT (comercial, sem atribuição) | caminho mais seguro para ícones nas cenas e carrosséis |
| unDraw (undraw.co) | ilustrações SVG com cor configurável | site | licença própria: uso comercial livre, sem atribuição, não redistribuir como pacote | só se a marca aceitar ilustração (o manual prefere foto real) |
| Google Fonts | fontes | fonts.google.com | OFL | já usamos Inter; Unbounded também é Google Font |
| Coverr (coverr.co), Videvo (videvo.net) | vídeos | site (Videvo tem clipes com atribuição obrigatória) | conferir por clipe | reserva |

Repositórios úteis (código aberto, já conhecidos no projeto): `yt-dlp` (referências), `remotion` + `@remotion/lottie` (animações), `edge-tts` (voz), `ffmpeg`. Para os bancos acima o app fala direto com a API REST (sem SDK), como já faz com Gemini, Publora e YouTube.

## Como o pulso do GSI aproveita isso

Quando o pulso manda uma ideia do Notion para o Editor GS, o fluxo do pedido já diz ao Editor para rodar `buscar_material(tema)` antes de recorrer a slide tipográfico: primeiro o que existe no Drive, depois banco gratuito como apoio. Quanto melhor organizado o Drive (nomes de arquivo com o assunto: `take-obs-cena-webcam.mp4`, `print-obs-fontes.png`, `foto-thiago-mesa.jpg`), melhor a busca, porque ela lê pasta e nome do arquivo.

## Pendências do Raphael

1. Criar as chaves gratuitas do Pexels e do Pixabay e colar no `.env` do Editor GS (`~/EditorGS/.env` quando instalado como plugin).
2. Organizar o Drive `Materiais do Editor` em pastas por tipo e nomes com o assunto; depois Biblioteca → Sincronizar.
3. Abastecer `trilhas/` com música gratuita (Mixkit, Pixabay Music ou YouTube Audio Library), anotando origem e licença no `trilhas/README.md`.
