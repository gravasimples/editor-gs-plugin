"""Fase C (07/11/2026): layouts (painel, moldura, tutorial, tela, aula), câmera virtual, barra de passos, cortina e rosto recortado.
Tudo em pasta temporária. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_layouts.py"""
import inspect, json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-layouts-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import layouts as L
from editor_video.util import ErroFerramenta, FFMPEG, preparar_mediapipe
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def fala(texto, inicio=0.0, passo=0.4):
    ws = [{"palavra": w, "inicio": round(inicio + i * passo, 2), "fim": round(inicio + i * passo + 0.3, 2)} for i, w in enumerate(texto.split())]
    return {"palavras": ws, "segmentos": [{"inicio": ws[0]["inicio"], "fim": ws[-1]["fim"], "texto": texto}]}

# blocos
b, av = L.blocos_de("painel@0; tutorial@6; cheio@14", 20, tem_tela=True)
check([x["modo"] for x in b] == ["painel", "tutorial", "cheio"] and b[-1]["fim"] == 20 and b[1]["inicio"] == 6 and b[0]["fim"] == 6, "blocos contíguos do texto modo@segundo")
b, _ = L.blocos_de("moldura", 12)
check(b == [{"modo": "moldura", "inicio": 0.0, "fim": 12}], "um modo só vale para o vídeo todo")
b, av = L.blocos_de("cheio@0; tutorial@5", 10, tem_tela=False)
check(len(b) == 1 and b[0]["modo"] == "cheio" and any("precisa da gravação de tela" in a for a in av), "tutorial sem tela vira cheio com aviso")
b, av = L.blocos_de("painel@0; cheio@5; moldura@5.8", 12)
check([x["modo"] for x in b] == ["painel", "moldura"] and any("menos de" in a for a in av), "bloco curto demais é absorvido pelo seguinte")
b, _ = L.blocos_de('[{"modo": "painel", "inicio": 3}, {"modo": "cheio", "inicio": 8}]', 15)
check(b[0]["inicio"] == 0.0 and b[0]["modo"] == "painel", "JSON aceito e o primeiro bloco começa em 0")
try:
    L.blocos_de("splitscreen@0", 10); check(False, "modo inválido levanta erro")
except ErroFerramenta:
    check(True, "modo inválido levanta erro")
b, av = L.blocos_de("aula", 10, tem_tela=True, tem_recorte=False)
check(any("bolha" in a for a in av), "aula sem recorte avisa que o rosto vai numa bolha")
check(L.cortinas_de(L.blocos_de("painel@0; tutorial@6; cheio@14", 20, tem_tela=True)[0]) == [6.0, 14.0], "cortina em cada troca de bloco")

# passos e focos
pal = fala("primeiro a exposição depois o ISO e por fim o equilíbrio de branco pronto")
ps, av = L.passos_de('[{"texto": "Exposição", "palavra": "exposição"}, {"texto": "ISO", "palavra": "ISO"}, {"texto": "Branco", "palavra": "branco", "inicio": 4}]', pal)
check([p["texto"] for p in ps] == ["Exposição", "ISO", "Branco"] and ps[0]["inicio"] == 0.8 and ps[1]["inicio"] == 2.0, "passos ancoram na palavra dita")
ps, _ = L.passos_de("Áudio@0; Luz@4.5; Câmera@9", None)
check([p["inicio"] for p in ps] == [0.0, 4.5, 9.0], "passos no formato texto@segundo")
ps, av = L.passos_de("; ".join(f"P{i}@{i}" for i in range(7)), None)
check(len(ps) == 5 and any("até 5" in a for a in av), "barra de passos limita a 5")
fs, _ = L.focos_de('[{"inicio": 2, "x": 0.8, "y": 0.2, "zoom": 2, "caixa": [0.7, 0.1, 0.2, 0.1]}, {"inicio": 3.5, "x": 0.3, "y": 0.6}]', None, 10)
check(fs[0]["fim"] == 3.5 and fs[0]["caixa"] == [0.7, 0.1, 0.2, 0.1] and fs[1]["zoom"] == 1.9, "focos: um termina quando o próximo começa; zoom padrão 1,9; caixa preservada")
try:
    L.focos_de('[{"inicio": 1, "x": 640, "y": 300}]'); check(False, "foco em pixels é recusado (vai de 0 a 1)")
except ErroFerramenta:
    check(True, "foco em pixels é recusado (vai de 0 a 1)")
fs, _ = L.focos_de('[{"palavra": "ISO", "x": 0.5, "y": 0.5}]', pal)
check(fs[0]["inicio"] == 2.0, "foco ancora na palavra")

# câmera automática numa tela sintética: fundo parado, "webcam" piscando num canto, um menu que abre no meio em 2 s
tela = tmp / "tela.mp4"
filtro = ("color=c=0x202020:s=640x360:d=6,format=yuv420p[bg];color=c=white:s=120x90:d=6[cam];color=c=0x3080ff:s=140x110:d=6[menu];"
          "[bg][cam]overlay=500:250:enable='lt(mod(t\\,0.5)\\,0.25)'[a];[a][menu]overlay=250:120:enable='gte(t\\,2)'")
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc", "-filter_complex", filtro, "-t", "6", "-an", str(tela)], check=True)
fs, res = L.focos_auto(tela)
check(res["regiao_viva"] > 0 and len(fs) == 1, f"câmera automática ignora a região que pisca e acha 1 mudança ({res})")
check(fs and 1.6 <= fs[0]["inicio"] <= 2.1 and abs(fs[0]["x"] - 320 / 640) < 0.08 and abs(fs[0]["y"] - 175 / 360) < 0.1 and fs[0]["zoom"] >= 1.4,
      "foco automático aproxima onde o menu abriu, quando abriu")

# MediaPipe e recorte
check(bool(preparar_mediapipe()), "libGLESv2 carregada para o MediaPipe (sem ela o detector de rosto caía em 'nenhum')")
from editor_video import rosto
check(rosto._detector()[1] == "mediapipe", "detector de rosto usa o MediaPipe")
check(L.MODELO_SEG.exists() and L.MODELO_SEG_ALTA.exists(), "modelos de recorte presentes (selfie segmenter e multiclass)")
rv = tmp / "rosto.mp4"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:d=1:r=10", "-pix_fmt", "yuv420p", str(rv)], check=True)
rr = L.recortar_rosto(rv, tmp / "rosto.webm")
pf = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream_tags=alpha_mode", "-of", "csv=p=0", str(tmp / "rosto.webm")], capture_output=True, text=True).stdout
check(rr["quadros"] == 10 and "1" in pf, "recorte grava .webm com canal de transparência")
check(L.posicao_rosto(rv) is None, "posição do rosto: vídeo sem rosto devolve None (caixa fica no enquadramento padrão)")
_orig = rosto.rastrear_rosto
rosto.rastrear_rosto = lambda v, fps_amostra=1.0: ([(0, 160, 180), (1, 170, 190), (2, None, None), (3, 150, 170)], "mediapipe")
pr = L.posicao_rosto(rv); rosto.rastrear_rosto = _orig
check(pr and pr["x"] == 0.5 and pr["y"] == 0.75 and pr["achados"] == 3, f"posição do rosto = mediana das detecções de 0 a 1 ({pr})")
check(L.tela_cobre_edl({"manter": [{"inicio": 0, "fim": 5}, {"inicio": 7, "fim": 30}]}, 30.2) and not L.tela_cobre_edl({"manter": [{"inicio": 0, "fim": 30}]}, 12), "tela só recebe os cortes quando cobre o bruto")

# composto (09/11/2026): vídeo vertical com tela em cima e rosto embaixo → 16:9 com tela à esquerda e rosto à direita
b, _ = L.blocos_de("composto", 10)
check(b == [{"modo": "composto", "inicio": 0.0, "fim": 10}], "modo composto aceito nos blocos (não precisa de tela)")
tr = L._trechos_de([True] * 6 + [False] * 2 + [True] * 6 + [False] * 8, 0.5, 11.0, min_s=1.5)
check([(x["inicio"], x["fim"], x["composto"]) for x in tr] == [(0.0, 7.0, True), (7.0, 11.0, False)], f"trecho curto (1 s) é absorvido pelo anterior e vizinhos iguais se fundem ({tr})")
cv = tmp / "composto.mp4"
# 0–4 s: 'tela' cinza-clara em cima com barra escura no fim (linha divisória forte) e 'câmera' azulada embaixo; 4–8 s: só a 'câmera'
filtro = ("color=c=0x606080:s=360x640:d=8:r=10[cam];color=c=0x7a7a7a:s=360x300:d=4:r=10[ui];color=c=0x0a0a0a:s=360x20:d=4:r=10[barra];"
          "[cam][ui]overlay=0:0:enable='lt(t,4)'[a];[a][barra]overlay=0:300:enable='lt(t,4)'")
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc", "-filter_complex", filtro, "-t", "8", "-an", "-pix_fmt", "yuv420p", str(cv)], check=True)
_origc = L.rastrear_rosto_caixas
L.rastrear_rosto_caixas = lambda v, fps_amostra=1.0: ([(t, 0.5, 0.8, 0.4, 0.2) if t < 4 else (t, 0.5, 0.4, 0.4, 0.2) for t in range(8)], "mediapipe")
dc = L.detectar_composto(cv)
L.rastrear_rosto_caixas = _origc
check(dc is not None and abs(dc["divisor"] - 0.5) < 0.03, f"divisor achado na linha entre a tela e a câmera ({dc and dc['divisor']})")
check(dc is not None and [(x["inicio"], x["fim"], x["composto"]) for x in dc["trechos"]] == [(0.0, 4.0, True), (4.0, 8.0, False)], f"trechos composto/só rosto pelo rosto ({dc and dc['trechos']})")
check(dc is not None and dc["rosto_baixo"] == {"x": 0.5, "y": 0.8} and dc["rosto_cima"] == {"x": 0.5, "y": 0.4} and dc["compostos_s"] == 4.0, "posições do rosto nos dois estados e segundos compostos")
L.rastrear_rosto_caixas = lambda v, fps_amostra=1.0: ([(t, 0.5, 0.4, 0.4, 0.2) for t in range(8)], "mediapipe")
check(L.detectar_composto(cv) is None, "rosto sempre no meio: não é composto (16:9 segue com fundo desfocado)")
L.rastrear_rosto_caixas = _origc
hv = tmp / "horizontal.mp4"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:d=1:r=10", "-pix_fmt", "yuv420p", str(hv)], check=True)
check(L.detectar_composto(hv) is None, "vídeo horizontal nunca é composto")
tsx_c = (RAIZ / "remotion" / "src" / "Layout.tsx").read_text()
check("modo === 'composto'" in tsx_c and "trechoComposto(" in tsx_c and "clipPath: `inset(" in tsx_c, "Remotion desenha o composto (tela à esquerda, rosto à direita, faixa recortada)")
acab_c = (RAIZ / "mcp" / "editor-de-video" / "editor_video" / "acabamento.py").read_text()
check('composto = lay.detectar_composto(v)' in acab_c and 'layout = "composto"' in acab_c, "montar_remotion detecta o composto sozinho no 16:9 de vídeo vertical")
check("modoAgora === 'cheio'" in (RAIZ / "remotion" / "src" / "Montagem.tsx").read_text(), "fundo desfocado continua no bloco cheio quando a orientação muda")

# servidor, motor e Remotion
for nome in ("focos_da_tela", "recortar_rosto"):
    check(callable(getattr(servidor, nome, None)), f"ferramenta MCP {nome}")
sig = inspect.signature(servidor.montar_remotion).parameters
check(all(k in sig for k in ("layout", "tela", "focos", "passos", "rosto_recortado", "cortina")), "montar_remotion aceita layout, tela, focos, passos, rosto_recortado e cortina")
from editor_video import acabamento
fonte = inspect.getsource(acabamento)
check('"layout": lay_cfg' in fonte and "aplicar_cortes(tela_src" in fonte and "cortinas_s" in fonte, "acabamento: props levam o layout, tela recebe os cortes, cortinas entram no som")
tsx = (RAIZ / "remotion" / "src" / "Layout.tsx").read_text(encoding="utf-8")
check(all(f"modo === '{m}'" in tsx for m in L.MODOS if m != "cheio"), "Remotion desenha todos os modos de layout")
mont = (RAIZ / "remotion" / "src" / "Montagem.tsx").read_text(encoding="utf-8")
check("CamadaLayout" in mont and "BarraPassos" in mont and "Cortina" in mont and "painel={" in mont, "Montagem usa a camada de layout, passos, cortina e grafismos no painel")
check("rosto_pos" in fonte and "posRosto(" in tsx and "passosVisiveis(lay, tv)" in mont, "caixas de rosto enquadram pela posição do rosto; barra de passos só nos blocos de tela")
ag = (RAIZ / "workspace" / "AGENTS.md").read_text(encoding="utf-8")
check("layout=" in ag and "focos" in ag and "passos" in ag, "AGENTS.md ensina os layouts")
from servico import plataforma as _plat
node = _plat.node_bin() or Path.home() / ".nvm/versions/node/v24.22.1/bin"
r = subprocess.run([_plat.npx(), "tsc", "--noEmit", "-p", "."], cwd=RAIZ / "remotion", capture_output=True, text=True, env={**os.environ, "PATH": f"{node}{os.pathsep}{os.environ['PATH']}"})
check(r.returncode == 0, f"Remotion compila sem erro de tipo {r.stdout[-300:]}")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
