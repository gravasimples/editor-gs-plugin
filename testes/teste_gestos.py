"""Gestos e olhar (10/11/2026): agrupamento e filtragem com eventos fabricados, yaw da cabeça, gatilho `gesto` no plano de grafismos,
sugestões no rascunho, ferramenta MCP registrada e detecção real num vídeo sintético (sem rosto nem mão → zero eventos; SKIP se os modelos
.task não estiverem disponíveis sem baixar). Tudo em pasta temporária. Rodar: python -I testes/teste_gestos.py"""
import inspect, json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-gestos-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import gestos as G, grafismos as GR
from editor_video.util import FFMPEG, ErroFerramenta
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

# --- yaw e rótulo da cabeça
check(abs(G.yaw_de_pontos(50, 0, 100)) < 1e-6 and G.rotulo_cabeca(0.0) == "olhando_camera", "nariz no meio das bochechas = de frente")
check(G.yaw_de_pontos(30, 0, 100) < -18 and G.rotulo_cabeca(G.yaw_de_pontos(30, 0, 100)) == "virada_esquerda", "nariz para a esquerda da imagem = virada_esquerda")
check(G.rotulo_cabeca(G.yaw_de_pontos(72, 0, 100)) == "virada_direita" and G.rotulo_cabeca(G.yaw_de_pontos(58, 0, 100)) == "olhando_camera", "nariz à direita = virada_direita; leve desvio ainda é câmera")
check(G.yaw_de_pontos(10, 5, 5) == 0.0, "largura zero não divide por zero")

# --- agrupamento e filtragem
passo = 0.2
am = [(round(i * passo, 3), []) for i in range(40)]  # 8 s
for i in range(5, 10):   # 1,0–2,0 s: polegar (5 amostras = 1,0 s)
    am[i][1].append(("polegar_cima", 0.9))
am[12][1].append(("vitoria", 0.8))  # 2,4 s: uma amostra só (0,2 s) → fora
for i in range(20, 24):  # 4,0–4,8 s: apontar, com um buraco de 1 amostra no meio
    if i != 22:
        am[i][1].append(("apontar_cima", 0.7))
for i in range(30, 38):  # 6,0–7,6 s: virada
    am[i][1].append(("virada_direita", 1.0))
ev = G.agrupar(am, passo, min_dur_s=0.4)
tipos = [(e["tipo"], e["inicio"], e["fim"]) for e in ev]
check(("polegar_cima", 1.0, 2.0) in tipos, f"amostras seguidas viram um evento com início e fim ({tipos})")
check(not any(t == "vitoria" for t, _, _ in tipos), "evento de 0,2 s é descartado (< 0,4 s)")
check(("apontar_cima", 4.0, 4.8) in tipos, "buraco de uma amostra não quebra o evento")
check(("virada_direita", 6.0, 7.6) in tipos and len(ev) == 3, "virada vira evento; três eventos no total")
pol = next(e for e in ev if e["tipo"] == "polegar_cima")
check(abs(pol["confianca"] - 0.9) < 1e-6 and pol["amostras"] == 5, "confiança média e contagem de amostras")
check(G.agrupar([], passo) == [] and G.agrupar([(0.0, []), (0.2, [])], passo) == [], "sem rótulos: sem eventos")
am2 = [(0.0, [("punho", 0.6)]), (0.2, [("punho", 0.6)]), (1.0, [("punho", 0.6)]), (1.2, [("punho", 0.6)]), (1.4, [("punho", 0.6)])]
ev2 = G.agrupar(am2, passo, min_dur_s=0.4)
check([(e["inicio"], e["fim"]) for e in ev2] == [(0.0, 0.4), (1.0, 1.6)], f"buraco maior que a tolerância separa em dois eventos ({[(e['inicio'], e['fim']) for e in ev2]})")
r = G.resumo_de(ev, 40, 40, 30)
check("polegar_cima ×1" in r and "virada" in r and "75%" in r, f"resumo em uma frase ({r})")
check("nenhum gesto" in G.resumo_de([], 10, 0, 0) and "nenhum rosto" in G.resumo_de([], 10, 0, 0), "resumo sem nada")

# --- eventos_de / ancorar_gesto
gj = tmp / "gestos.json"; gj.write_text(json.dumps({"eventos": ev}), encoding="utf-8")
check(len(G.eventos_de(str(gj))) == 3 and len(G.eventos_de(json.dumps({"eventos": ev}))) == 3 and len(G.eventos_de(ev)) == 3 and G.eventos_de("") == [], "eventos_de aceita caminho, JSON inline, lista e vazio")
check(G.ancorar_gesto("polegar_cima", ev) == 1.0 and G.ancorar_gesto("apontar_cima", ev, perto=4.5) == 4.0 and G.ancorar_gesto("polegar_cima", ev, perto=30.0) is None and G.ancorar_gesto("amo_voce", ev) is None, "ancorar_gesto: primeiro, mais perto, fora da janela e inexistente")

# --- gatilho `gesto` no plano de grafismos
def fala(texto, inicio=0.0, passo=0.4):
    ws = [{"palavra": w, "inicio": round(inicio + i * passo, 2), "fim": round(inicio + i * passo + 0.3, 2)} for i, w in enumerate(texto.split())]
    return {"palavras": ws, "segmentos": [{"inicio": ws[0]["inicio"], "fim": ws[-1]["fim"], "texto": texto}], "duracao_s": ws[-1]["fim"] + 0.5}
pal = fala("ó galera isso aqui funciona de verdade sem configurar nada e pronto tá gravando mesmo e é simples")
plano = {"itens": [
    {"tipo": "checklist", "gesto": "polegar_cima", "itens": [{"texto": "Funciona", "gesto": "polegar_cima"}]},
    {"tipo": "kicker", "gesto": "apontar_cima", "inicio": 4.5, "texto": "Detalhe"},
    {"tipo": "pilula", "gesto": "amo_voce", "inicio": 6.0, "texto": "SIMPLES"},
    {"tipo": "manchete", "gesto": "polegar_cima", "texto": "Sem gesto"},
]}
itens, avisos = GR.normalizar(plano, pal, gestos=str(gj))
por_tipo = {i["tipo"]: i for i in itens}
check(por_tipo["checklist"]["inicio"] == 1.0 and por_tipo["checklist"]["itens"][0]["em"] == 1.0, f"checklist entra no polegar (1,0 s), subitem também ({por_tipo['checklist']['inicio']})")
check(por_tipo["kicker"]["inicio"] == 4.0, "kicker ancora no apontar mais perto de 4,5 s")
check(por_tipo["pilula"]["inicio"] == 6.0 and any("amo_voce" in a for a in avisos), "gesto que não aconteceu mantém o tempo e avisa")
check("gesto" not in por_tipo["kicker"], "a chave `gesto` não vai para as props do Remotion")
it2, av2 = GR.normalizar({"itens": [{"tipo": "pilula", "gesto": "polegar_cima", "inicio": 2.0, "texto": "X"}]}, pal)
check(it2[0]["inicio"] == 2.0 and any("detectar_gestos" in a for a in av2), "sem eventos, item com gesto fica no tempo dado e o aviso ensina o caminho")
it3, _ = GR.normalizar({"gestos": str(gj), "itens": [{"tipo": "pilula", "gesto": "polegar_cima", "texto": "X"}]}, pal)
check(it3[0]["inicio"] == 1.0, "o plano pode carregar o caminho do gestos.json na chave \"gestos\"")
it4, av4 = GR.normalizar({"gestos": str(tmp / "nao-existe.json"), "itens": [{"tipo": "pilula", "gesto": "polegar_cima", "inicio": 3.0, "texto": "X"}]}, pal)
check(it4[0]["inicio"] == 3.0 and any("não li" in a for a in av4), "gestos.json que não existe vira aviso, não erro")

# --- sugestões no rascunho
sug = GR.sugestoes_de_gestos(ev, GR.palavras_planas(pal))
check([g["tipo"] for g in sug["itens"]] == ["checklist", "kicker"] and all(g.get("gesto") for g in sug["itens"]), f"polegar → checklist, apontar → kicker ({[g['tipo'] for g in sug['itens']]})")
check(len(sug["cutaways"]) == 1 and sug["cutaways"][0]["lado"] == "direita" and any("cutaway" in t for t in sug["texto"]), "virada vira sugestão de cutaway em texto")
auto = GR.plano_auto(pal, gestos=str(gj))
check(auto["origem"].endswith("gestos)") and auto.get("gestos") == str(gj) and "sugestoes" in auto and "cutaways" in auto, "plano_auto com gestos guarda o caminho e as sugestões")
check(any(g.get("gesto") == "polegar_cima" for g in auto["itens"]) and not any(g["tipo"] == "cutaway" for g in auto["itens"]), "item sugerido entra no rascunho; cutaway nunca vira item")
check("gestos" not in GR.plano_auto(pal) and "sugestoes" not in GR.plano_auto(pal), "sem gestos, o rascunho é igual ao de antes")
norm_auto, _ = GR.normalizar(auto, pal)
check(any(i["tipo"] == "checklist" and i["inicio"] == 1.0 for i in norm_auto), "rascunho com gesto normaliza no instante do evento (sem passar gestos de novo)")

# --- servidor
check(callable(getattr(servidor, "detectar_gestos", None)), "ferramenta MCP detectar_gestos registrada")
sig = inspect.signature(servidor.detectar_gestos).parameters
check(all(k in sig for k in ("video", "saida_json", "fps_amostra", "inicio_s", "fim_s")), "detectar_gestos tem video, saida_json, fps_amostra, inicio_s, fim_s")
check("gestos_json" in inspect.signature(servidor.planejar_grafismos).parameters and "gestos_json" in inspect.signature(servidor.validar_grafismos).parameters, "planejar_grafismos e validar_grafismos aceitam gestos_json")
pj = tmp / "pal.json"; pj.write_text(json.dumps(pal), encoding="utf-8")
pg = servidor.planejar_grafismos(str(pj), str(tmp / "out" / "grafismos.json"), gestos_json=str(gj))
check(pg.get("gestos") and pg["gestos"]["cutaways"] and (tmp / "out" / "grafismos.json").exists() and json.loads((tmp / "out" / "grafismos.json").read_text(encoding="utf-8")).get("gestos") == str(gj), "planejar_grafismos devolve as sugestões e o rascunho gravado carrega o gestos.json")
vg = servidor.validar_grafismos(json.dumps(plano), str(pj), gestos_json=str(gj))
check(vg["itens"][0]["inicio"] == 1.0, "validar_grafismos ancora pelo gesto")
check("gesture_recognizer.task" in G.URLS and "face_landmarker.task" in G.URLS and all(u.startswith("https://storage.googleapis.com/mediapipe-models/") for u in G.URLS.values()), "modelos vêm do storage oficial do Google")

# --- detecção real num vídeo sintético (sem rosto, sem mão)
try:
    G.caminho_modelo("gesture_recognizer.task", baixar=False); G.caminho_modelo("face_landmarker.task", baixar=False)
    modelos = True
except ErroFerramenta as e:
    modelos = False; print("SKIP detecção real: modelos .task não disponíveis sem baixar:", str(e)[:160])
if modelos:
    vid = tmp / "v.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x568:d=2:r=10", "-f", "lavfi", "-i", "sine=f=300:d=2", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(vid)], check=True)
    try:
        res = G.detectar_gestos(str(vid), str(tmp / "g.json"), fps_amostra=5, baixar_modelos=False)
        check(res["eventos"] == [] and res["amostras"] >= 8 and (tmp / "g.json").exists(), f"vídeo sem rosto nem mão: zero eventos, sem erro ({res['amostras']} amostras)")
        check(res["olhar"]["amostras_com_rosto"] == 0 and "nenhum gesto" in res["resumo"], "olhar sem rosto e resumo honesto")
        res2 = G.detectar_gestos(str(vid), None, fps_amostra=5, inicio_s=0.5, fim_s=1.5, baixar_modelos=False)
        check(res2["amostras"] <= 6 and res2["inicio_s"] == 0.5, f"inicio_s/fim_s limitam o trecho ({res2['amostras']} amostras)")
        r3 = servidor.detectar_gestos(str(vid), str(tmp / "g3.json"), fps_amostra=5)
        check("eventos" in r3 and "erro" not in r3, "ferramenta MCP roda de ponta a ponta")
    except ErroFerramenta as e:
        print("SKIP detecção real:", str(e)[:160])
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
