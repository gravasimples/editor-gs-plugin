# App próprio da Meta para publicar no Instagram (caminho definitivo, sem Publora)

Atualizado: 10/11/2026 (cliente construído; seção "Facebook Login com Página" para concorrentes). Precisa do login do Raphael (ou do Thiago) em https://developers.facebook.com. O mesmo app serve para publicar Reels, ler comentários, ler métricas da conta própria e alimentar o radar de concorrentes do GSI (`integracoes/instagram_fonte.py` já espera `META_IG_TOKEN` e `META_IG_USER_ID`).

## Por que dá para usar sem App Review
A "Instagram API with Instagram Login" com Acesso Padrão publica na conta própria sem revisão, desde que a conta tenha papel no app (admin, desenvolvedor ou testador) e seja profissional (Business ou Creator). O App Review só é exigido para atender contas de terceiros. Fonte: [App Review da Instagram Platform](https://developers.facebook.com/documentation/instagram-platform/app-review).

## Passo a passo (uma vez)
1. developers.facebook.com → Meus apps → Criar app → caso de uso "Outro" → tipo Empresa (Business) → nome "Grava Simples Editor".
2. No painel do app: Adicionar produto → Instagram → "API setup with Instagram login".
3. Em "Generate access tokens": Adicionar conta → entrar com @thiago.obsstudio (conta profissional). Se pedir, aceitar o convite de testador no app do Instagram (Configurações → Site e apps → Convites de testador).
4. Gerar o token da conta. Ele já vem de longa duração (60 dias). Anotar também o ID de usuário do Instagram que aparece ao lado.
5. No `.env` do Editor GS (`~/EditorGS/.env` quando instalado como plugin), acrescentar:
   ```
   META_IG_TOKEN=<token>
   META_IG_USER_ID=<id>
   ```
   Reiniciar o gateway. Nunca colar o token no chat ou em Markdown.
6. Renovação: `GET /refresh_access_token?grant_type=ig_refresh_token` antes de 60 dias; o gateway vai avisar no cartão "Publicar" quando faltar menos de 7 dias.

## Como o Reels sobe pela API
`POST /{ig-user-id}/media` com `media_type=REELS` e `video_url` → `POST /{ig-user-id}/media_publish`. O Instagram **baixa o vídeo de uma URL pública**: o gateway roda só no tailnet, então o arquivo precisa ficar público por alguns minutos. Opção sem custo: `tailscale funnel` expondo só `/arquivos/<slug>/final_9x16.mp4` durante a publicação (Tailscale já instalado). Alternativa: enviar antes para o Drive com link público ou para um bucket.
Limites: Reels de 3 s a 15 min, MP4 H.264/AAC, até 1 GB; legenda até 2.200 caracteres; 100 publicações por 24 h por conta (`content_publishing_limit`). Capa: `cover_url` ou `thumb_offset`.

## Comentários e métricas (mesmo token)
- Comentários: `GET /{media-id}/comments`, responder com `POST /{comment-id}/replies` (o Editor só escreve rascunhos; enviar é clique humano).
- Métricas: `GET /{media-id}/insights` (`views`, `reach`, `saved`, `shares`, `likes`, `comments`, `total_interactions`; `plays` foi descontinuado em 2025) e `GET /{ig-user-id}/insights`.
- Concorrentes: `GET /{ig-user-id}?fields=business_discovery.username(<perfil>){media{...}}` lê posts públicos de outras contas profissionais. **Correção (10/11/2026):** isso não existe no Instagram Login; exige a credencial do Facebook Login com Página (seção abaixo).

## Cliente no Editor GS (10/11/2026)
`servico/meta.py` (cliente, duas credenciais, cache de 60 s, `ErroMeta` sem token) e `servico/meta_api.py` (rotas `GET /api/gs/meta/situacao|conta|midias|midias/{id}/insights|midias/{id}/comentarios|insights|limite|concorrente/{username}` e `POST /api/gs/meta/renovar`). Publicar (`meta.publicar_reel`, `meta.publicar_imagem`) não tem rota: entra no cartão da entrega, por clique. Sem credenciais, `situacao` responde `{"configurada": false, "pendente": "META_PENDENTE", "como": "docs/META-APP.md"}` e as outras rotas 409. Testes: `~/.venvs/editor-gs/bin/python -B testes/teste_meta.py`.

## Facebook Login com Página (concorrentes e referências)

Adicionado em 10/11/2026, conferido na documentação oficial nesta data (links no fim da seção). O caminho acima (Instagram Login) resolve a conta própria. **Perfis públicos de terceiros (`business_discovery`) só existem na "Instagram API with Facebook Login"**: a referência do endpoint diz "Available for the Instagram API with Facebook Login", e o quadro comparativo da plataforma não lista Business Discovery nem Hashtag Search para o Instagram Login. Por isso o Editor GS aceita as duas credenciais ao mesmo tempo (`servico/meta.py`): a (a) para publicar/ler a conta própria, a (b) para concorrentes e referências. Se só a (b) existir, ela também serve para a conta própria.

### O que muda

| | (a) Instagram Login | (b) Facebook Login com Página |
|---|---|---|
| Host | `https://graph.instagram.com/v26.0` | `https://graph.facebook.com/v26.0` |
| Precisa de Página do Facebook | não | **sim**, com a conta IG profissional ligada a ela |
| Permissões | família `instagram_business_*` | família `instagram_*` + `pages_*` |
| Token | de usuário do Instagram, 60 dias, renova por `ig_refresh_token` | de usuário (60 dias) → **de Página (não expira)** |
| `business_discovery` | não | sim |
| Hashtag Search | não | sim (feature "Instagram Public Content Access"; não usamos) |

### Passo a passo (uma vez)

1. **Página do Facebook.** Se o Thiago não tiver uma, criar em facebook.com → Páginas → Criar (nome "Grava Simples"). Não precisa publicar nada nela.
2. **Ligar a conta IG à Página.** No app do Instagram: Configurações → Central de Contas → Contas → adicionar a conta do Facebook da mesma pessoa; depois, na Página: Configurações → Contas vinculadas → Instagram → Conectar conta (@thiago.obsstudio, que já é profissional). A doc exige "A Facebook Page connected to that Instagram account".
3. **App.** Pode ser o mesmo app "Grava Simples Editor" do caminho (a). No painel: Adicionar produto → **Facebook Login for Business** (configurações padrão servem).
4. **Token de usuário.** Painel → Ferramentas → Explorador da Graph API → escolher o app → "Permissões do usuário": marcar `instagram_basic`, `instagram_manage_insights`, `instagram_content_publish`, `instagram_manage_comments`, `pages_show_list`, `pages_read_engagement` (e `business_management` só se a Página pertencer a um Portfólio empresarial / Business Manager; nesse caso a doc também pede `ads_management` ou `ads_read` para insights, mídia e publicação) → "Generate Access Token" → entrar com o Facebook do Thiago e autorizar a Página. Esse token dura ~1 hora.
5. **Token de longa duração (60 dias).** No mesmo Explorador, chamar
   `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=<APP_ID>&client_secret=<APP_SECRET>&fb_exchange_token=<token de 1 h>`
   (ou pelo botão "Estender token" na Ferramenta de depuração de token).
6. **Token de Página (não expira) e ID da conta IG.** Com o token de longa duração, chamar
   `GET /me/accounts?fields=id,name,access_token,instagram_business_account`
   Anotar, da Página certa: `access_token` (é o **token de Página**: gerado a partir de um token de usuário de longa duração ele não tem data de expiração) e `instagram_business_account.id` (é o **ID da conta IG** para a Graph do Facebook; é diferente do `user_id` do Instagram Login). Se `instagram_business_account` não aparecer, o passo 2 não ficou completo.
7. **.env** do Editor GS (`~/EditorGS/.env` quando instalado como plugin), sem colar no chat:
   ```
   META_FB_TOKEN=<token de Página>
   META_FB_IG_USER_ID=<instagram_business_account.id>
   META_APP_ID=<id do app>          # opcional: liga a checagem de validade (debug_token) e o appsecret_proof
   META_APP_SECRET=<segredo do app>  # opcional, junto com META_APP_ID
   ```
   Reiniciar o gateway e conferir em `GET /api/gs/meta/situacao` (ou `python3 -m servico.meta`): deve mostrar `credenciais.fb = true` e `business_discovery = true`. Testar: `GET /api/gs/meta/concorrente/agapemultimidia`.

### O que o Acesso Padrão permite sem App Review

Para app usado só por quem tem papel nele (admin, desenvolvedor, testador) e por contas IG que essas pessoas administram, o **Standard Access** basta e não há App Review; a Meta só exige Advanced Access (App Review + verificação de empresa) para atender contas de terceiros ou usuários sem papel no app. `business_discovery` lê perfis públicos de contas profissionais **através da conta própria**, então entra nesse mesmo regime. A doc avisa que "alguns recursos podem não funcionar totalmente" no Acesso Padrão: se alguma permissão aparecer em cinza no Explorador, é sinal de que o app precisa estar em modo "Ao vivo" ou que a permissão exige revisão (a confirmar na prática, na primeira chamada).

### Limites

- **Publicação:** 100 posts por 24 h (janela móvel) por conta, contado em `POST /media_publish`; carrossel conta um. Consultar com `GET /{ig-user-id}/content_publishing_limit?fields=quota_usage,config` (`quota_total`, `quota_duration`). *Observação:* a página de referência do endpoint ainda diz "currently 50", e a seção de carrossel do guia também cita 50; o guia principal diz 100. Confiar no `quota_total` devolvido pela API (`GET /api/gs/meta/limite`).
- **Chamadas em geral (Instagram Platform):** `4800 × impressões` por 24 h, por par app + usuário (impressões = vezes que o conteúdo da conta apareceu na tela nas últimas 24 h). Cabeçalho `X-Business-Use-Case-Usage` traz o uso; erro de limite é code `80002` (Instagram) ou `4`/`17`/`32`.
- **`business_discovery` e Hashtag Search** não entram na conta de impressões: ficam nos **Platform Rate Limits** (nível de app: 200 chamadas × número de usuários por hora, segundo o guia de rate limiting). **Correção ao que se dizia:** o aumento "de 240 para 1.000 consultas por usuário por hora" (changelog de 30/03/2026) é da **Discovery API do Creator Marketplace**, não do `business_discovery`. Limite por hora específico do `business_discovery`: a confirmar nos cabeçalhos da primeira rodada real.
- **Comentários:** `GET /{media-id}/comments` devolve só comentários de nível 1, no máximo 50 por chamada, mais recentes primeiro; respostas vêm pelo campo `replies`.
- **Mídias de terceiros:** `media_url` é omitido em vídeos com áudio licenciado/com direitos e em Reels cujo dono desligou download; `view_count` soma orgânico e pago; contas restritas por idade não retornam nada; chamar `GET /{media-id}` direto numa mídia de terceiro falha (só via consulta aninhada).

### Métricas que o cliente pede (nomes atuais)

`plays` e `impressions` foram descontinuados em 2025 (changelog de 21/01/2025; `impressions` só segue em mídia anterior a 02/07/2024). Reels: `views, reach, saved, shares, likes, comments, total_interactions, ig_reels_avg_watch_time, ig_reels_video_view_total_time`. Feed: os sete primeiros. Conta (`period=day`, `metric_type=total_value`): `reach, views, total_interactions, accounts_engaged, profile_views, follower_count` — **a confirmar** (a página de referência de insights da conta não abriu na conferência; o cliente tolera erro por métrica e devolve `erros` ao lado de `metricas`).

### Variáveis do `.env` (lista completa)

| Variável | Credencial | Obrigatória | Para quê |
|---|---|---|---|
| `META_IG_TOKEN` | (a) | sim, para (a) | token de usuário do Instagram Login (60 dias; mesmo nome que o GSI usa) |
| `META_IG_USER_ID` | (a) | sim, para (a) | ID da conta IG no Instagram Login (`user_id` de `/me`) |
| `META_FB_TOKEN` | (b) | sim, para (b) | token de Página (não expira) ou de usuário de longa duração |
| `META_FB_IG_USER_ID` | (b) | sim, para (b) | `instagram_business_account.id` da Página |
| `META_APP_ID` | (b) | não | com o segredo: `debug_token` (validade e escopos em `situacao`) e `appsecret_proof` |
| `META_APP_SECRET` | (b) | não | idem; nunca sai do `.env` |
| `META_GRAPH_VERSION` | ambas | não | padrão `v26.0` |

Token renovado por `POST /api/gs/meta/renovar` (só (a)) fica em `estado/meta_token.json` (chmod 600, fora do git) e passa a valer sobre o `.env`; o `.env` não é reescrito.

### Fontes (developers.facebook.com, lidas em 10/11/2026)

- Visão geral e comparação dos dois logins, Standard/Advanced Access: https://developers.facebook.com/docs/instagram-platform/overview
- Primeiros passos com Facebook Login (Página, `instagram_basic`, `pages_show_list`, `/me/accounts`, `{page-id}?fields=instagram_business_account`): https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/get-started
- Business Discovery (guia): https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery · referência (permissões `instagram_basic`, `instagram_manage_insights`, `pages_read_engagement`; "Available for the Instagram API with Facebook Login"): https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/business_discovery
- Token de longa duração e de Página: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived
- Renovação no Instagram Login (`ig_exchange_token`, `ig_refresh_token`, 60 dias, token com mais de 24 h): https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login
- Publicação de conteúdo (container, `status_code`, 100/24 h, `trial_params`): https://developers.facebook.com/docs/instagram-platform/content-publishing · parâmetros do container (`cover_url`, `thumb_offset`, `share_to_feed`, `alt_text`): https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media · `content_publishing_limit`: https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/content_publishing_limit
- Métricas de mídia: https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights
- Comentários: https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-media/comments
- Rate limits (`4800 × impressões`, BUC, Platform Rate Limits): https://developers.facebook.com/docs/graph-api/overview/rate-limiting
- Changelog (deprecação de `plays`/`impressions`; 240 → 1.000 da Discovery API do Creator Marketplace, 30/03/2026): https://developers.facebook.com/docs/instagram-platform/changelog
- `debug_token`: https://developers.facebook.com/docs/graph-api/reference/debug_token/

## YouTube e TikTok (depois)
- YouTube: projeto próprio no Google Cloud, YouTube Data API v3, OAuth com `youtube.upload`; upload direto (sem URL pública); cota grátis de 10.000 unidades/dia (upload = 1.600). Tela de consentimento em produção, senão o refresh token vence em 7 dias.
- TikTok: Content Posting API com upload direto; sem auditoria do app o post sai privado (só a própria conta vê).
