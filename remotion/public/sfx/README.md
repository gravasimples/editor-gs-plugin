# Efeitos sonoros do acabamento (nível profissional)

Pacote CC0 de 10/11/2026 (Kenney + Freesound; origem e licença de cada arquivo em `LICENCA.md`). `catalogo.json` lista as variações por categoria:

| Categoria | Quando entra (`montar_remotion(sfx=True)`) |
|---|---|
| `whoosh` | corte (modo antigo) e transição `zoom_blur` |
| `swipe` | cortina laranja entre blocos de layout; transições `deslize` e `giro` |
| `pop` | palavra-chave na tela e grafismos comuns (pílula, logos, checklist…) |
| `tick` | capítulo (pílula 1/3, 2/3…) e transição `punch` |
| `riser` | 0,6 s antes da `manchete`; transição `luz` |
| `impacto` | grafismo `numero`; transições `flash` e `tremor` |
| `erro` | grafismo `riscado` |
| `ding` | tela final e grafismo `cta` |

Quem decide é `editor_video/nivel_pro.py` (`sfx_auto`, `escolher_sfx`: a variação é sorteada pelo instante, então o mesmo vídeo dá sempre a mesma edição) e `transicoes.py` (`SFX`, por tipo de transição). Volume baixo (o app mistura a 0,18–0,35). Para acrescentar um som: WAV 48 kHz mono em volta de −18 LUFS, nome na categoria em `catalogo.json`, linha em `LICENCA.md` (só CC0 ou som próprio). Categoria sem arquivo = evento sem som.
