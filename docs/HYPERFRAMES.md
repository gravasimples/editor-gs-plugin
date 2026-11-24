# HyperFrames no Editor GS — teste integrado (10/11/2026)

Pedido do Raphael: testar o HyperFrames integrado ao Editor como motor **alternativo** de grafismos/overlays (outros editores com IA usam). Não vira padrão: o motor de grafismos continua o Remotion (`remotion/` + `acabamento.py`/`grafismos.py`). Pesquisa anterior: `docs/maquina/PESQUISA-GRAFISMOS-2026-11-10.md` e `PESQUISA-2026-11-10-NOITE.md`.

## O que é

HyperFrames (HeyGen, https://github.com/heygen-com/hyperframes, **Apache-2.0**): uma composição é um HTML com `data-*` de tempo (`data-composition-id`, `data-width`/`data-height`, `data-duration`, `data-fps`, `data-start` nos elementos) e uma timeline GSAP pausada registrada em `window.__timelines[<id>]`. O CLI abre a página num Chrome headless, dá seek quadro a quadro e entrega pelo FFmpeg. Mesma arquitetura do Remotion (Chromium → quadros → ffmpeg), com outro vocabulário (HTML/CSS/GSAP em vez de React/TSX). Pacote npm `hyperframes` 0.9.30 (10/11/2026), Node ≥ 22, FFmpeg no PATH.

Conferido na instalação local:
- **Alpha de verdade**: `--format webm` dá VP9 `yuva420p` (tag `ALPHA_MODE=1`); `--format mov` dá ProRes 4444; `--format png-sequence` dá PNGs RGBA. O fundo da página é forçado transparente (`html, body` sem fundo). Atenção: o `ffprobe` comum mostra `yuv420p`; só com `-c:v libvpx-vp9` aparece `yuva420p`.
- **Navegador**: não baixou Chromium. O `doctor`/`browser path` usa o Chrome do sistema (`C:\Program Files\Google\Chrome\Application\chrome.exe`, HeadlessChrome 152); `HYPERFRAMES_BROWSER_PATH` troca o executável (serve o `chrome-headless-shell` do Remotion em `remotion/node_modules/.remotion/`, não testado).
- **Windows nativo**: funcionou direto (Node portátil 24.22.2, ffmpeg 9.0.2 do `~/EditorGS/bin`). O `doctor` só reclama de opcionais (whisper-cpp, Kokoro, Docker).
- Duração/fps/tamanho entram do jeito oficial: atributos no elemento raiz + `--fps`. Não há `--width/--height/--duration` no CLI; `--resolution` só muda o DPR (mesma proporção).
- Dados dinâmicos oficiais: `data-composition-variables` + `--variables`. Aqui usamos marcadores no HTML (`{{DADOS}}` = JSON), mais simples para o agente.
- **Telemetria ligada por padrão** (`hyperframes telemetry status`); o módulo manda `HYPERFRAMES_NO_TELEMETRY=1` em todo render. Há `hyperframes auth` (conta HeyGen) e `usage`: não usados, nada exige conta para renderizar local.
- Render por seek: a timeline só pode usar `set/to/from/fromTo` com opacity, x, y, scale, rotation, width, height, visibility. **Tween de `color`, troca de classe ou callback não entram no quadro** (a primeira versão da legenda cinética saiu toda transparente por isso). Nunca tweenar `visibility`/`display` num `.clip`.
- Lint: qualquer coisa antes de `<!doctype html>` (até comentário) é tratada como fragmento; os comentários dos blocos ficam dentro de `<head>`.

## Como instalar (local, não entra no instalador padrão)

```
scripts\instalar-hyperframes.cmd        (Windows; usa ~\EditorGS\bin\node)
scripts/instalar-hyperframes.sh         (Linux/macOS; Node 22+ no PATH ou nvm)
```
`npm install` em `hyperframes/` (`package.json` próprio: `hyperframes@0.9.30` + `gsap@3.15.0` para render sem internet). Resultado: **101 MB** em `hyperframes/node_modules/` (74 pacotes + gsap), sem Chromium. `.gitignore` cobre `hyperframes/node_modules/` e `hyperframes/_render/`. Nada global. Sem a instalação, `grafismo_hyperframes` devolve `erro` com o comando.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `mcp/editor-de-video/editor_video/hyperframes.py` | `renderizar_overlay(html, saida_webm, largura, altura, fps, duracao_s)` (HTML → WebM alpha; reserva PNG→WebM pelo ffmpeg se vier sem alpha), `sobrepor(video, overlay_webm, saida, inicio_s)` (ffmpeg overlay com alpha, áudio copiado, overlay redimensionado ao vídeo), `html_do_bloco`, `listar_blocos`, `grafismo_no_video` |
| `hyperframes/blocos/manchete.html` | manchete com kicker (pílula laranja), Inter ExtraBold, caixa marinho, destaque laranja numa parte da frase; entra palavra por palavra e sai no fim |
| `hyperframes/blocos/legenda-cinetica.html` | legenda palavra por palavra nos tempos da transcrição (`{"palavra","inicio","fim"}`, mesmo formato do Editor), até 4 por linha, palavra atual em laranja (cópia laranja por cima com opacity), `posicao` baixo/centro |
| `servidor.py → grafismo_hyperframes(video, bloco, dados_json, saida, inicio_s, duracao_s)` | ferramenta MCP: render do bloco no tamanho/fps do vídeo + sobreposição; overlay fica em `_trabalho/` ao lado da saída; passa pelo `_final` (áudio −16 LUFS) |
| `scripts/instalar-hyperframes.cmd` / `.sh` | instalação local |
| `testes/teste_hyperframes.py` | 27 verificações; render real só se o CLI estiver instalado |
| `workspace/AGENTS.md` | parágrafo: a ferramenta existe e só entra quando o pedido citar HyperFrames |

## O que o teste mostrou (10/11/2026, i5-9300H, GTX 1650, Chrome 152)

| Render | Tempo | Saída |
|---|---|---|
| `manchete` 3 s, 1080×1920, 30 fps, workers auto | 36,3 s | WebM 0,1 MB, `yuva420p`, 3,000 s |
| idem, `--workers 1` | 34,7 s | igual |
| `legenda-cinetica` 3 s, 1080×1920 | 30,5 s | 3,000 s |
| `legenda-cinetica` 2,5 s, 540×960 | 15,6 s | |
| `manchete` 1 s, 320×568 (teste) | 15,8 s | |
| `sobrepor` em vídeo de 6 s 1080×1920 (libx264 crf 18) | 12,6 s | MP4 6,000 s, AAC copiado |

Leitura: quase tudo é custo fixo (compilar, abrir o Chrome, calibrar, ~12–15 s) mais ~0,1 s por quadro; o dedup de quadros estáticos ajuda em bloco parado. Validação visual: quadro em 2,0 s do MP4 final mostra o `testsrc` com a manchete e o kicker por cima, fonte Inter carregada do repo; quadros 0,5 s e 1,6 s da legenda mostram "OLHA SÓ" e "O OBS" com a palavra atual laranja. `python testes/teste_hyperframes.py`: 27 PASS (render real incluído).

## Como o agente usa

Só quando o pedido citar HyperFrames. Exemplo:
```
grafismo_hyperframes(video="saida/<slug>/final_9x16.mp4", bloco="manchete",
  dados_json='{"kicker": "Áudio", "manchete": "Microfone caro não resolve", "destaque": "não resolve"}',
  saida="saida/<slug>/final_9x16_hf.mp4", inicio_s=3.2, duracao_s=3)
```
Cada chamada reencoda o vídeo inteiro (um passe de ffmpeg por grafismo). Para vários grafismos no mesmo vídeo, o caminho certo seria **um** HTML com todos os blocos e `data-start` próprios, renderizado uma vez na duração total (`renderizar_overlay` já aceita qualquer HTML), e uma única `sobrepor` — não implementado como ferramenta.

## Comparação curta com o Remotion

| | Remotion (atual) | HyperFrames |
|---|---|---|
| Arquitetura | Chromium headless → quadros → ffmpeg | igual |
| Linguagem | React/TSX, props JSON | HTML/CSS/GSAP, `data-*` |
| Alpha | WebM VP8/VP9 e ProRes 4444 | WebM VP9, ProRes 4444, PNG |
| Integração aqui | montagem inteira (cortes, legenda, layouts, grafismos semânticos, transições, trilha) num render só | só overlay por cima de um MP4 pronto; mais um reencode |
| Velocidade | ~0,1–0,2 s/quadro em 1080p nos nossos renders | ~0,1 s/quadro + 12–15 s fixos; sem ganho |
| Dependências | Chromium próprio (já baixado) | Chrome do sistema; Node 22+ |
| Extras | — | catálogo de ~450 blocos (`hyperframes catalog`, exige rede/conta?), skills de captions/motion com regras numéricas boas, telemetria ligada por padrão, `auth` HeyGen |
| Licença | Remotion (própria; já aceita) | Apache-2.0 |

## Veredito

- **Não trocar de motor** nem rodar por padrão: no Editor GS o HyperFrames só consegue ser overlay sobre um MP4 pronto, com reencode extra e sem ganho de tempo; o Remotion já faz tudo num passe e conhece layouts, transições e grafismos semânticos.
- **Manter como opção instalável** (como está: pasta própria, ferramenta explícita, zero custo quando não instalado). Útil para: testar rápido um grafismo escrito em HTML/GSAP pelo agente sem mexer em `remotion/src`; e aproveitar skills de terceiros feitas em HyperFrames (claude-editing-skills, claude-edit) que já falam esse vocabulário.
- **Maior valor: catálogo e regras.** Ler os blocos (`hyperframes catalog`, `dist/skills/hyperframes/references/*.md`: captions, motion, overlays, look) e recriar em TSX os 8–10 que fazem falta (lower third, counter, comparação, tier list), como já estava no plano da pesquisa. Os números do `captions.md` (grupos de 2–6 palavras, kill com `set` no fim, posição 600–700 px do fundo no 9:16, mistura por brilho do fundo) cabem direto no nosso `legenda.py`/`CenaTexto`.
- Se for usar em entrega real: fazer o modo "um HTML com vários blocos" (uma sobreposição por vídeo) e avaliar `HYPERFRAMES_BROWSER_PATH` → `chrome-headless-shell` do Remotion para não depender do Chrome instalado.

## O que não foi verificado

- `hyperframes catalog` / blocos remotos (se exige rede ou conta HeyGen) e o `frame.md`.
- Render com `HYPERFRAMES_BROWSER_PATH` apontando o Chromium do Remotion.
- `--format mov` (ProRes 4444) e `png-sequence` só foram lidos na ajuda; a reserva PNG→WebM do módulo não foi exercitada porque o WebM já veio com alpha.
- Composição com `<video>` dentro (aqui só overlay sem mídia) e tempo em vídeos longos (> 60 s).
