"""Pacote de SFX CC0 (10/11/2026): catálogo bate com os arquivos, LICENCA cobre todos, sorteio determinístico por categoria,
categorias novas ligadas aos eventos (cortina → swipe, capítulo → tick, riscado → erro, manchete → riser) e transições pelo catálogo.
Rodar: python -I testes/teste_sfx_catalogo.py"""
import inspect, json, re, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import nivel_pro as np_, transicoes as T, acabamento as A
from editor_video.util import FFPROBE

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

SFX = RAIZ / "remotion" / "public" / "sfx"
cat = json.loads((SFX / "catalogo.json").read_text(encoding="utf-8"))
arqs_cat = [a for v in cat.values() for a in v]
wavs = sorted(p.name for p in SFX.glob("*.wav"))
check(set(np_.CATEGORIAS_SFX) <= set(cat) and all(len(cat[c]) >= 2 for c in np_.CATEGORIAS_SFX), f"catálogo tem as 8 categorias com 2+ variações ({ {c: len(v) for c, v in cat.items()} })")
check(len(cat["whoosh"]) >= 3 and len(cat["pop"]) >= 3 and len(cat["swipe"]) >= 3, "whoosh, pop e swipe com 3 variações")
check(sorted(arqs_cat) == wavs and len(arqs_cat) == len(set(arqs_cat)), f"todo wav está no catálogo e todo item do catálogo existe ({len(wavs)} sons)")
check(all(re.fullmatch(r"[a-z]+-\d\d\.wav", a) for a in arqs_cat), "nomes em PT-BR com índice (categoria-NN.wav)")
check(20 <= len(wavs) <= 30, f"entre 20 e 30 sons ({len(wavs)})")
total = sum(p.stat().st_size for p in SFX.iterdir() if p.is_file())
check(total < 5 * 1024 * 1024, f"pasta com menos de 5 MB ({total / 1024:.0f} KB)")
lic = (SFX / "LICENCA.md").read_text(encoding="utf-8")
check(all(a in lic for a in arqs_cat), "LICENCA.md cita todo arquivo do catálogo")
check("CC0" in lic and "kenney.nl" in lic and "freesound.org" in lic and "http" in lic, "LICENCA.md traz licença CC0, origem e URL")
check(not any((SFX / n).exists() for n in ("whoosh.wav", "pop.wav", "ding.wav", "swish.wav", "riser.wav", "impacto.wav", "tick.wav")), "sons sintéticos antigos saíram")
gi = (RAIZ / ".gitignore").read_text(encoding="utf-8")
check("public/sfx" not in gi, ".gitignore não exclui remotion/public/sfx (os sons vão para o git)")
# formato dos arquivos
ok_fmt = True
for a in arqs_cat[:30]:
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels:format=duration", "-of", "json", str(SFX / a)], capture_output=True, text=True)
    d = json.loads(r.stdout); s = d["streams"][0]
    if s["sample_rate"] != "48000" or s["channels"] != 1 or float(d["format"]["duration"]) > 3.2:
        ok_fmt = False; print("   formato errado:", a, s, d["format"]["duration"])
check(ok_fmt, "todos em 48 kHz mono e até 3 s")

# sorteio determinístico
c = np_.catalogo_sfx()
check(c and all(len(v) >= 2 for v in c.values()), "catalogo_sfx lê o catálogo real")
e1 = np_.escolher_sfx("whoosh", 12.34); e2 = np_.escolher_sfx("whoosh", 12.34)
check(e1 == e2 and e1 in cat["whoosh"], f"mesmo instante → mesma variação ({e1})")
vars_ = {np_.escolher_sfx("whoosh", t) for t in (0.5, 1.7, 3.3, 5.1, 8.8, 12.0, 15.5, 21.2, 30.0, 44.4)}
check(len(vars_) >= 2, f"instantes diferentes espalham pelas variações ({sorted(vars_)})")
check(np_.escolher_sfx("inexistente", 1.0) is None and np_.escolher_sfx("whoosh", 1.0, {}) is None, "categoria sem som devolve None")
with tempfile.TemporaryDirectory() as td:
    check(np_.catalogo_sfx(td) == {} and np_.sfx_auto([1.0, 3.0], [{"inicio": 2.0}], 5.0, catalogo=np_.catalogo_sfx(td)) == [], "pasta sem catálogo: nenhum som, sem erro")
    (Path(td) / "catalogo.json").write_text(json.dumps({"pop": ["fantasma.wav"]}), encoding="utf-8")
    check(np_.catalogo_sfx(td) == {"pop": []}, "arquivo citado no catálogo mas ausente na pasta é ignorado (e o cache acompanha o arquivo)")

# eventos → categorias
fx = np_.sfx_auto([2.6, 2.9, 5.2], [{"texto": "erro", "inicio": 0.4, "fim": 1.5}], 8.0)
cats = [e["categoria"] for e in fx]
check(cats == ["pop", "whoosh", "whoosh", "ding"] and fx[1]["inicio"] == 2.55 and fx[-1]["inicio"] == 7.8, f"compatível com o antigo: pop na palavra-chave, whoosh por corte (colados viram um), ding antes da tela final ({[(e['categoria'], e['inicio']) for e in fx]})")
check(all(e["arquivo"] in cat[e["categoria"]] for e in fx), "cada entrada usa um arquivo da própria categoria")
check(np_.sfx_auto([], [], None) == [], "sem eventos: sem sfx")
fx2 = np_.sfx_auto([], [], None, cortinas_s=[6.0, 6.3, 14.0], capitulos=[{"inicio": 0.0}, {"inicio": 9.0}],
                   grafismos=[{"tipo": "manchete", "inicio": 3.0}, {"tipo": "riscado", "inicio": 11.0}, {"tipo": "numero", "inicio": 20.0}, {"tipo": "pilula", "inicio": 25.0}, {"tipo": "serie", "inicio": 0.0}, {"tipo": "cta", "inicio": 30.0}])
por = {(e["categoria"], e["inicio"]) for e in fx2}
check(("swipe", 5.9) in por and ("swipe", 13.9) in por and not any(c == "swipe" and 6.1 <= t <= 6.4 for c, t in por), f"cortinas viram swipe (0,1 s antes), coladas viram uma ({sorted(por)})")
check(("tick", 0.0) in por and ("tick", 9.0) in por, "capítulos viram tick")
check(("riser", 2.4) in por, "manchete tem riser 0,6 s antes")
check(("erro", 11.0) in por and ("impacto", 20.0) in por and ("pop", 25.0) in por and ("ding", 29.8) in por, "riscado → erro, numero → impacto, pilula → pop, cta → ding")
check(not any(t == 0.0 and c != "tick" for c, t in por), "item serie não tem som")
check([e["inicio"] for e in fx2] == sorted(e["inicio"] for e in fx2), "saída em ordem de tempo")

# transições pelo catálogo
check(all(v[0] in np_.CATEGORIAS_SFX for v in T.SFX.values()), "transicoes.SFX aponta para categorias do catálogo")
planos = [{"inicio": 0.0, "entrada": "seco"}, {"inicio": 2.0, "entrada": "zoom_blur"}, {"inicio": 5.0, "entrada": "deslize"}, {"inicio": 9.0, "entrada": "luz"}, {"inicio": 14.0, "entrada": "punch"}, {"inicio": 18.0, "entrada": "flash"}, {"inicio": 22.0, "entrada": "seco"}]
sf = T.sfx_dos_planos(planos)
check([e["categoria"] for e in sf] == ["whoosh", "swipe", "riser", "tick", "impacto"] and all(e["arquivo"] in cat[e["categoria"]] for e in sf), f"cada transição pega um som da sua categoria; seco sem som ({[(e['categoria'], e['arquivo']) for e in sf]})")
check(T.sfx_dos_planos(planos) == sf, "sfx das transições é determinístico")

# acabamento liga os eventos
fonte = inspect.getsource(A.montar_remotion)
check("cortinas_s=" in fonte and "capitulos=caps" in fonte and "grafismos=graf_sfx" in fonte and "sfx_auto(cortes, chaves" in fonte, "montar_remotion passa cortinas, capítulos e grafismos ao sfx_auto")
sig = inspect.signature(np_.sfx_auto).parameters
check(all(k in sig for k in ("cortinas_s", "capitulos", "grafismos", "catalogo")), "sfx_auto aceita as categorias novas")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
