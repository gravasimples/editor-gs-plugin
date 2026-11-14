"""Testes das regras do nível profissional (sem render): palavras-chave automáticas, efeitos sonoros, capítulos e b-roll.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_nivel_pro.py"""
import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import nivel_pro as np_

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

segs = [{"inicio": 0.2, "fim": 2.6, "texto": "Primeiro erro: a webcam travando no OBS."}, {"inicio": 2.8, "fim": 5.2, "texto": "Segundo erro: três cenas sem preset."}, {"inicio": 5.4, "fim": 7.8, "texto": "Terceiro: microfone com ruído."}, {"inicio": 8.0, "fim": 9.0, "texto": "Pronto, tá gravando."}]
pal = []
for s in segs:
    ws = s["texto"].split(); dur = (s["fim"] - s["inicio"]) / len(ws)
    for i, w in enumerate(ws): pal.append({"palavra": w, "inicio": round(s["inicio"] + i * dur, 2), "fim": round(s["inicio"] + (i + 1) * dur, 2)})
d = {"duracao_s": 9.0, "segmentos": segs, "palavras": pal}
k = np_.palavras_chave_auto(d)
check([x["texto"] for x in k] == ["erro", "erro", "microfone"], f"uma palavra-chave por frase, a primeira da lista que aparece, intervalo mínimo de 2,5 s (Pronto fica de fora) ({[x['texto'] for x in k]})")
check(all(k[i]["fim"] <= k[i + 1]["inicio"] - 0.15 + 1e-6 for i in range(len(k) - 1)) and all(x["fim"] > x["inicio"] for x in k), "fim de cada palavra-chave não atropela a seguinte")
k2 = np_.palavras_chave_auto(d, lista=["webcam", "obs"])
check([x["texto"] for x in k2] == ["webcam"] , f"lista própria: só o que está nela ({[x['texto'] for x in k2]})")
k3 = np_.palavras_chave_auto({"segmentos": [{"inicio": 0, "fim": 2, "texto": "Uso o OBS Studio todo dia", "palavras": [{"palavra": "Uso", "inicio": 0, "fim": 0.3}, {"palavra": "o", "inicio": 0.3, "fim": 0.4}, {"palavra": "OBS", "inicio": 0.4, "fim": 0.7}, {"palavra": "Studio", "inicio": 0.7, "fim": 1.1}, {"palavra": "todo", "inicio": 1.1, "fim": 1.4}]}]})
check(k3 and k3[0]["texto"] == "OBS Studio" and k3[0]["fim"] == 2.0, f"termo composto da lista vira uma palavra-chave só, com os dois tempos ({k3})")
longo = {"duracao_s": 60.0, "palavras": [{"palavra": "erro", "inicio": i * 3.0, "fim": i * 3.0 + 0.3} for i in range(20)]}
check(len(np_.palavras_chave_auto(longo)) == 10, "teto de 10 palavras-chave por minuto, espalhadas")
check(np_.palavras_chave_auto({}) == [] and np_.palavras_chave_auto({"palavras": [{"palavra": "e", "inicio": 0, "fim": 0.2}]}) == [], "sem palavras ou sem termo da lista: vazio")
n = np_.palavras_chave_auto({"palavras": [{"palavra": "15", "inicio": 1, "fim": 1.3}, {"palavra": "minutos", "inicio": 1.3, "fim": 1.8}]})
check(n and n[0]["texto"] == "15", "número vira palavra-chave")
check(np_.palavras_chave_auto({"palavras": [{"palavra": "um", "inicio": 0, "fim": 0.2}, {"palavra": "slide", "inicio": 0.2, "fim": 0.6}, {"palavra": "e", "inicio": 0.7, "fim": 0.8}, {"palavra": "três", "inicio": 3.5, "fim": 3.8}]}) == [{"texto": "três", "inicio": 3.5, "fim": 4.7}], "\"um\" (artigo) não vira palavra-chave; \"três\" vira")
fx = np_.sfx_auto([2.6, 2.9, 5.2], [{"texto": "erro", "inicio": 0.4, "fim": 1.5}], 8.0)
check([e["categoria"] for e in fx] == ["pop", "whoosh", "whoosh", "ding"] and fx[1]["inicio"] == 2.55 and fx[-1]["inicio"] == 7.8 and all(e["arquivo"].startswith(e["categoria"] + "-") for e in fx),
      f"sfx: pop na palavra-chave, whoosh por corte (cortes colados viram um), ding antes da tela final; arquivo vem do catálogo CC0 ({[(e['arquivo'], e['inicio']) for e in fx]})")
check(np_.sfx_auto([], [], None) == [], "sem cortes, palavras ou tela final: sem sfx")
c = np_.capitulos_de("Áudio@0; Luz@12,5; Câmera@30")
check(len(c) == 3 and c[1] == {"texto": "Luz", "inicio": 12.5, "numero": 2, "total": 3}, f"capítulos na forma curta com vírgula decimal ({c[1]})")
c2 = np_.capitulos_de('[{"texto": "Um", "inicio": 1}, {"texto": "Dois", "inicio": 9, "numero": 2}]')
check(c2[0]["numero"] == 1 and c2[0]["total"] == 2 and c2[1]["inicio"] == 9.0 and np_.capitulos_de("") == [], "capítulos em JSON; vazio é lista vazia")
b = np_.broll_de("materiais/print.png@8@3; takes/obs.mp4@20@4@cheio; x@1")
check(len(b) == 3 and b[0] == {"arquivo": "materiais/print.png", "inicio": 8.0, "duracao_s": 3.0, "modo": "janela"} and b[1]["modo"] == "cheio" and b[2]["duracao_s"] == 3.0, f"b-roll na forma curta: padrão janela e 3 s ({b[0]})")
b2 = np_.broll_de('[{"arquivo": "a.png", "inicio": 2, "duracao_s": 0.2, "modo": "errado"}]')
check(b2[0]["duracao_s"] == 0.8 and b2[0]["modo"] == "janela" and np_.broll_de("") == [], "b-roll em JSON: duração mínima 0,8 s e modo inválido vira janela")
try:
    from servidor import _estilo
    e = _estilo('{"base": "profissional", "legenda": {"cor_destaque": "#F4C2D7"}, "montagem": {"sfx": false}}')
    check(e["legenda"]["cor_destaque"] == "#F4C2D7" and e["legenda"]["animacao"] == "pop" and e["montagem"]["sfx"] is False and e["montagem"]["palavras_chave"] == "auto" and e["nome"] == "profissional+ajustes", "estilo inline: ajustes por cima da base, resto preservado")
    check(_estilo("lista")["montagem"].get("capitulos_obrigatorios") and _estilo("padrao")["montagem"]["nivel"] == 1, "estilos por nome continuam; lista exige capítulos; padrao é nível 1")
except Exception as ex:  # noqa
    print("SKIP estilo inline:", str(ex)[:100])
# Fase 2 (03/11/2026): b-roll automático e trilha automática
import tempfile
am = [(i * 1.5, not (8 <= i <= 10 or 24 <= i <= 25)) for i in range(40)]  # 60 s: tela em 12–15 s e 36–37,5 s
b = np_.broll_auto(am, [{"inicio": 6.0}, {"inicio": 22.0}, {"inicio": 45.0}], 60.0)
check(len(b) == 2 and {x["fonte_t"] for x in b} <= {12.0, 13.5, 15.0, 36.0, 37.5}, f"um cutaway por trecho de tela, quadro tirado do trecho ({b})")
check(all(x["inicio"] >= 3.0 and x["inicio"] + x["duracao_s"] <= 60 - 3.5 for x in b), "longe do gancho e da tela final")
check(all(not (r0 - 1.5 - 2.5 <= x["inicio"] <= r1 + 1.5) for x in b for r0, r1 in ((12, 15), (36, 37.5))), "não cai em cima nem colado no trecho de tela")
check(all(dict(am).get(round(x["inicio"] / 1.5) * 1.5, True) for x in b) and len({x["inicio"] for x in b}) == 2 and abs(b[0]["inicio"] - b[1]["inicio"]) >= 8, "com rosto e espaçados 8 s")
check(any(x["inicio"] in (6.0, 22.0, 45.0) for x in b), "prefere o instante de uma palavra-chave")
check(np_.broll_auto([(i * 1.5, i != 10) for i in range(40)], None, 60.0) == [], "uma amostra isolada sem rosto é falha do detector, não tela")
check(np_.broll_auto([(i * 1.5, True) for i in range(20)]) == [] and np_.broll_auto([(i * 1.5, False) for i in range(20)]) == [], "vídeo todo de rosto ou todo de tela: sem b-roll")
with tempfile.TemporaryDirectory() as td:
    check(np_.escolher_trilha(td) is None and np_.escolher_trilha(Path(td) / "nao-existe") is None, "trilhas/ vazia: sem trilha")
    (Path(td) / "leia.md").write_text("x"); (Path(td) / "b-lofi.mp3").write_bytes(b"0"); (Path(td) / "a-piano.wav").write_bytes(b"0")
    check(np_.escolher_trilha(td).name == "a-piano.wav", "pega a primeira trilha de áudio em ordem alfabética, ignora outros arquivos")
try:
    m = _estilo("profissional")["montagem"]
    check(m.get("broll") == "auto" and m.get("gancho_animacao") == "palavra" and m.get("trilha") == "auto", "estilo profissional liga b-roll auto, gancho palavra a palavra e trilha auto")
except Exception as ex:  # noqa
    print("SKIP estilo fase 2:", str(ex)[:100])
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
