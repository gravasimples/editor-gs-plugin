"""Legenda cinética (10/11/2026): GSAP (SplitText + CustomWiggle) dentro do Remotion, dirigido pelo palavras_json.
Confere: modelos cinetica-* carregam, elementos.json válido, props montadas pelo acabamento.py com e sem as chaves (render falso),
legenda_ass mantém tudo como era, e um render curto de verdade quando EDITOR_GS_RENDER_TESTE=1.
Isolado: vídeo sintético e saídas em pasta temporária. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_legenda_cinetica.py"""
import inspect, json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import acabamento as A
from editor_video.util import FFMPEG, info_midia, ErroFerramenta

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

LEG = RAIZ / "estilos" / "legendas"
CIN = ["cinetica-tipografica", "cinetica-maquina", "cinetica-onda"]

# modelos carregam e têm o formato dos modelos existentes
ref = json.loads((LEG / "karaoke-pop.json").read_text(encoding="utf-8"))
for cid in CIN:
    d = json.loads((LEG / f"{cid}.json").read_text(encoding="utf-8"))
    check(d["id"] == cid and set(ref) <= set(d) and set(ref["legenda"]) <= set(d["legenda"]), f"{cid}: mesmas chaves do modelo de referência")
    leg = d["legenda"]
    check(leg["animacao"] == cid.split("-")[1] and leg["fonte"] == "Inter" and leg["cor_destaque"] == "#F79615" and leg["contorno"] == "#000921", f"{cid}: Inter, laranja e marinho da marca")
    check(leg["animacao"] in A.CINETICAS and isinstance(leg.get("tremor"), bool), f"{cid}: animação cinética conhecida e tremor booleano")
check(json.loads((LEG / "cinetica-onda.json").read_text(encoding="utf-8"))["legenda"]["tremor"] is True, "cinetica-onda já vem com tremor")

# elementos.json válido e com as animações de legenda
el = json.loads((RAIZ / "estilos" / "elementos.json").read_text(encoding="utf-8"))
ids = {i["id"]: i for i in el["itens"]}
check(len(ids) == len(el["itens"]), "elementos.json sem id repetido")
for eid in ("legenda-tipografica", "legenda-maquina", "legenda-onda", "legenda-tremor"):
    i = ids.get(eid)
    check(i and i["categoria"] == "animacao" and i.get("subcategoria") == "legenda" and i["parametro"] and i["previa"]["motor"] == "remotion", f"elemento {eid} registrado (animação de legenda, com parametro)")
sig = inspect.signature(A.montar_remotion).parameters
args_ok = all(set(i["previa"]["args"]) - {"cortes"} <= set(sig) for i in el["itens"] if i["previa"]["motor"] == "remotion")
check(args_ok, "todo args de prévia do motor remotion é parâmetro de montar_remotion")
check("legenda_modelo" in sig and "legenda_tremor" in sig and sig["legenda_tremor"].default is None, "montar_remotion aceita legenda_modelo e legenda_tremor (padrão None)")

# props montadas pelo acabamento (render falso: nada de Remotion)
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-cinetica-")); os.chdir(tmp)
vid = tmp / "v.mp4"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=360x640:d=3:r=30", "-f", "lavfi", "-i", "sine=f=300:d=3", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(vid)], check=True)
ws = [("agora", 0.2, 0.5), ("vai", 0.55, 0.75), ("depender", 0.8, 1.3), ("da", 1.35, 1.45), ("sua", 1.5, 1.7), ("webcam", 1.75, 2.4)]
pal = {"palavras": [{"palavra": w, "inicio": a, "fim": b} for w, a, b in ws], "segmentos": [{"inicio": 0.2, "fim": 2.4, "texto": "agora vai depender da sua webcam"}], "duracao_s": 3.0}
pj = tmp / "p.json"; pj.write_text(json.dumps(pal), encoding="utf-8")
padrao = json.loads((RAIZ / "estilos" / "padrao.json").read_text(encoding="utf-8"))
capt = {}
render_real = A.renderizar_remotion
def render_falso(comp, props, saida, timeout=0):
    capt["props"] = props
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(vid), "-c", "copy", str(saida)], check=True); return Path(saida)
A.renderizar_remotion = render_falso
base = dict(palavras_json=str(pj), formato="9x16", estilo=padrao, zoom=False, clarao=False, tela_final=False)

r0 = A.montar_remotion(str(vid), str(tmp / "o0.mp4"), **base)
check("legenda_cinetica" not in capt["props"] and r0["legenda_cinetica"] is None and r0["aviso_legenda"] is None, "sem as chaves: props e resultado como antes")

r1 = A.montar_remotion(str(vid), str(tmp / "o1.mp4"), legenda_modelo="cinetica-tipografica", **base)
c = capt["props"].get("legenda_cinetica")
check(c and c["animacao"] == "tipografica" and c["tremor"] is False and c["maiusculas"] is True, "legenda_modelo=cinetica-tipografica monta a prop legenda_cinetica")
check(c["linhas"] and sum(len(l["palavras"]) for l in c["linhas"]) == 6 and all(len(l["palavras"]) <= 3 for l in c["linhas"]), f"6 palavras em linhas de até 3 ({[len(l['palavras']) for l in c['linhas']]})")
check(all(a["fim"] <= b["inicio"] for a, b in zip(c["linhas"], c["linhas"][1:])), "linhas não se sobrepõem")
check(all(sum(1 for p in l["palavras"] if p.get("enfase")) == 1 for l in c["linhas"]), "uma palavra de ênfase por linha")
check(any(p["texto"] == "webcam" and p.get("enfase") for l in c["linhas"] for p in l["palavras"]), "a palavra-chave da fala (webcam) é a ênfase da linha dela")
check(abs(c["tamanho"] - 76) < 0.1 and c["peso"] == 800 and c["fonte"] == "InterGS" and c["posicao"] == "baixa", f"tamanho em px na resolução do render (1080p: {c['tamanho']}), peso 800")
check(r1["legenda_cinetica"] == {"animacao": "tipografica", "tremor": False, "n_linhas": len(c["linhas"])}, "resultado resume a legenda cinética")

A.montar_remotion(str(vid), str(tmp / "o2.mp4"), legenda_modelo="cinetica-onda", resolucao="720p", **base)
c2 = capt["props"]["legenda_cinetica"]
check(c2["animacao"] == "onda" and c2["tremor"] is True and c2["posicao"] == "centro" and abs(c2["tamanho"] - 48) < 0.1, f"cinetica-onda: tremor do modelo, centro, 720p escala o tamanho ({c2['tamanho']})")
A.montar_remotion(str(vid), str(tmp / "o3.mp4"), legenda_modelo="cinetica-onda", legenda_tremor=False, **base)
check(capt["props"]["legenda_cinetica"]["tremor"] is False, "legenda_tremor=False desliga o tremor do modelo")

est_inline = {**padrao, "legenda": {**padrao["legenda"], "animacao": "maquina", "tremor": True, "caixa": True}}
A.montar_remotion(str(vid), str(tmp / "o4.mp4"), **{**base, "estilo": est_inline})
c4 = capt["props"]["legenda_cinetica"]
check(c4["animacao"] == "maquina" and c4["tremor"] is True and c4["caixa"] is True and c4["contorno_px"] == 0, "estilo inline (legenda.animacao + legenda.tremor + caixa) também liga")

A.montar_remotion(str(vid), str(tmp / "o5.mp4"), formato="16x9", **{k: v for k, v in base.items() if k != "formato"}, legenda_modelo="cinetica-tipografica")
check(abs(capt["props"]["legenda_cinetica"]["tamanho"] - 56) < 0.1, "16x9 usa tamanho_16x9")

# legenda_ass externa: nada muda
ass = tmp / "l.ass"; ass.write_text("[Script Info]\nScriptType: v4.00+\nPlayResX: 360\nPlayResY: 640\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Legenda,Arial,24,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.20,0:00:02.40,Legenda,,0,0,0,,agora vai\n", encoding="utf-8")
r6 = A.montar_remotion(str(vid), str(tmp / "o6.mp4"), legenda_modelo="cinetica-tipografica", legenda_ass=str(ass), **base)
check("legenda_cinetica" not in capt["props"] and r6["legenda_cinetica"] is None and r6["legenda_queimada"] is True and r6["aviso_legenda"], "com legenda_ass a cinética não entra (ASS queimada como sempre) e o resultado avisa")
A.montar_remotion(str(vid), str(tmp / "o7.mp4"), **{**base, "palavras_json": None}, legenda_modelo="cinetica-tipografica")
check("legenda_cinetica" not in capt["props"], "sem palavras_json não há legenda cinética")

# função pura
check(A.legenda_cinetica_props({"animacao": "pop"}, pal, "9x16", 1080, 1920) is None, "animação do motor ASS (pop) não vira cinética")
check(A.legenda_cinetica_props({"animacao": "onda"}, {"palavras": []}, "9x16", 1080, 1920) is None, "sem palavras devolve None")

# Remotion: componente e props no lugar
tsx = (RAIZ / "remotion" / "src" / "LegendaCinetica.tsx").read_text(encoding="utf-8")
check("gsap/SplitText" in tsx and "gsap/CustomWiggle" in tsx and "paused: true" in tsx and ".seek(" in tsx, "LegendaCinetica.tsx usa SplitText, CustomWiggle e timeline pausada dirigida por seek")
check("LegendaCinetica" in (RAIZ / "remotion" / "src" / "Montagem.tsx").read_text(encoding="utf-8") and "legenda_cinetica" in (RAIZ / "remotion" / "src" / "tipos.ts").read_text(encoding="utf-8"), "Montagem.tsx desenha a legenda cinética e tipos.ts declara a prop")
pkg = json.loads((RAIZ / "remotion" / "package.json").read_text(encoding="utf-8"))
check(pkg["dependencies"].get("gsap", "").startswith("3."), f"gsap no package.json ({pkg['dependencies'].get('gsap')})")

# prévia da página Estilos (11/11/2026): modelo cinético vai pelo Remotion, modelo ASS continua queimando a ASS
sys.path.insert(0, str(RAIZ / "servico"))
import previa_estilo as PE
chamadas = []
PE.remotion = lambda td, saida, estilo, args, legenda_ass=None: (chamadas.append(("remotion", estilo, legenda_ass)), Path(saida).write_bytes(b"x"))
PE.prev_legenda = lambda td, saida, leg: (chamadas.append(("ass", leg)), Path(saida).write_bytes(b"x"))
PE.main("legenda", "cinetica-onda", str(tmp / "prev" / "cin.mp4"))
PE.main("legenda", "karaoke-pop", str(tmp / "prev" / "ass.mp4"))
check(chamadas[0][0] == "remotion" and chamadas[0][1]["legenda"]["animacao"] == "onda" and chamadas[0][2] is None, "prévia de cinetica-onda: montar_remotion com o bloco legenda do modelo, sem ASS")
check(chamadas[1][0] == "ass" and (tmp / "prev" / "ass.mp4").exists(), "prévia de karaoke-pop: segue pela ASS")

# render curto de verdade (só quando pedido)
A.renderizar_remotion = render_real
if os.environ.get("EDITOR_GS_RENDER_TESTE") == "1":
    try:
        r = A.montar_remotion(str(vid), str(tmp / "real.mp4"), legenda_modelo="cinetica-tipografica", legenda_tremor=True, resolucao="720p", **base)
        i = info_midia(r["video"])
        check(i["largura"] == 720 and i["altura"] == 1280 and abs(i["duracao_s"] - 3.0) < 0.3 and r["legenda_cinetica"]["tremor"] is True, f"render real 720p com legenda cinética: {i['largura']}x{i['altura']}, {i['duracao_s']} s")
    except ErroFerramenta as e:
        check(False, "render real falhou: " + str(e)[:200].replace("\n", " "))
else:
    print("SKIP render real (EDITOR_GS_RENDER_TESTE=1 liga)")

os.chdir(RAIZ)
import shutil; shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
