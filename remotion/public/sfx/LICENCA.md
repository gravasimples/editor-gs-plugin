# Efeitos sonoros — origem e licença (pacote de 10/11/2026)

Todos os arquivos desta pasta são **CC0 1.0 (domínio público)**: https://creativecommons.org/publicdomain/zero/1.0/ — uso comercial liberado, sem atribuição obrigatória. Nada aqui vem de fonte com outra licença. Catálogo por categoria em `catalogo.json`; o motor escolhe a variação pelo instante (`editor_video/nivel_pro.py → escolher_sfx`).

Processamento (ffmpeg, local): silêncio das pontas removido, duração limitada (fade de 0,18 s quando cortado), WAV 48 kHz mono 16 bits, ganho para −18 LUFS (loudnorm medido e corrigido) ou pico −4 dBFS nos sons curtos demais para medir LUFS, limitador em −2,5 dBFS. Os sons do Freesound foram baixados pela prévia pública em MP3 (`cdn.freesound.org/previews/…-hq.mp3`, 128 kbps), que é o mesmo conteúdo do original; a licença de cada um foi conferida na página pública do som.

## Kenney (www.kenney.nl) — CC0, conforme `License.txt` de cada pacote

Pacotes: **Interface Sounds** (https://kenney.nl/assets/interface-sounds, v1.0, 2020), **UI Audio** (https://kenney.nl/assets/ui-audio), **Impact Sounds** (https://kenney.nl/assets/impact-sounds, v1.0, 2019). Página de cada pacote declara "CC0 licensed".

| Arquivo | Categoria | Pacote | Arquivo original |
|---|---|---|---|
| pop-01.wav | pop | Interface Sounds | Audio/click_001.ogg |
| pop-02.wav | pop | Interface Sounds | Audio/drop_001.ogg |
| pop-03.wav | pop | UI Audio | Audio/click1.ogg |
| ding-01.wav | ding | Interface Sounds | Audio/confirmation_001.ogg |
| ding-02.wav | ding | Interface Sounds | Audio/confirmation_002.ogg |
| impacto-01.wav | impacto | Impact Sounds | Audio/impactSoft_medium_000.ogg |
| impacto-02.wav | impacto | Impact Sounds | Audio/impactGeneric_light_000.ogg |
| tick-01.wav | tick | Interface Sounds | Audio/switch_002.ogg |
| tick-02.wav | tick | UI Audio | Audio/switch2.ogg |
| tick-03.wav | tick | Interface Sounds | Audio/toggle_001.ogg |
| erro-01.wav | erro | Interface Sounds | Audio/error_001.ogg |
| erro-02.wav | erro | Interface Sounds | Audio/error_004.ogg |

## Freesound (freesound.org) — só sons marcados "Creative Commons 0" na página pública

| Arquivo | Categoria | Som (id) | Autor | URL |
|---|---|---|---|---|
| whoosh-01.wav | whoosh | swoosh_v2 (786514) | migoreng1 | https://freesound.org/people/migoreng1/sounds/786514/ |
| whoosh-02.wav | whoosh | whoosh low (830856) | MeanRaccoon | https://freesound.org/people/MeanRaccoon/sounds/830856/ |
| whoosh-03.wav | whoosh | Short Woosh 04.wav (582895) | ironcross32 | https://freesound.org/people/ironcross32/sounds/582895/ |
| whoosh-04.wav | whoosh | Woosh_Medium_Short_01.wav (425706), cortado em 1,4 s | moogy73 | https://freesound.org/people/moogy73/sounds/425706/ |
| riser-01.wav | riser | Cinematic Riser #3 subtle (859482), cortado em 3 s | BeaconStudio | https://freesound.org/people/BeaconStudio/sounds/859482/ |
| riser-02.wav | riser | Short Glitch Riser SFX (867126) | Diim_1 | https://freesound.org/people/Diim_1/sounds/867126/ |
| riser-03.wav | riser | Riser sound effect short.wav (685256), cortado em 3 s | syntheffects | https://freesound.org/people/syntheffects/sounds/685256/ |
| swipe-01.wav | swipe | Swipe Up (592443) | Baconation | https://freesound.org/people/Baconation/sounds/592443/ |
| swipe-02.wav | swipe | Swish Single 4 (393811) | deleted_user_6479820 | https://freesound.org/people/deleted_user_6479820/sounds/393811/ |
| swipe-03.wav | swipe | Movement.wav (391551) | 2create | https://freesound.org/people/2create/sounds/391551/ |

## O que saiu

Os sons sintéticos antigos (`whoosh.wav`, `pop.wav`, `ding.wav`, `swish.wav`, `riser.wav`, `impacto.wav`, `tick.wav`, gerados por ffmpeg/numpy em 02/11 e 08/11/2026) foram substituídos pelo catálogo. Para trocar um som: salve o WAV nesta pasta, acrescente o nome na categoria em `catalogo.json` e a linha aqui (só CC0 ou som próprio).
