"""Lacuna 8 dos Criativos (16/11/2026): etiqueta do passo junto do mouse na gravação de tela.
Tela sintética com uma seta de cursor andando e parando num botão; texto curto da fala; limites; posição pelo cursor, pelo foco e do agente.
Tudo em pasta temporária. Rodar: python -X utf8 -I testes/teste_etiqueta_mouse.py"""
import inspect, json, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-etiqueta-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
import cv2
from editor_video import etiqueta_mouse as E, grafismos as G, acabamento
from editor_video.util import FFMPEG
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def fala(texto, inicio=0.0, passo=0.3):
    ws = [{"palavra": w, "inicio": round(inicio + i * passo, 2), "fim": round(inicio + i * passo + 0.25, 2)} for i, w in enumerate(texto.split())]
    return {"palavras": ws, "segmentos": [{"inicio": ws[0]["inicio"], "fim": ws[-1]["fim"], "texto": texto}]}

def seta(img, x, y, k=1.0):
    pts = (np.array([[0, 0], [0, 17], [4, 13], [7, 20], [10, 19], [7, 12], [12, 12]]) * k + [x, y]).astype(np.int32)
    cv2.fillPoly(img, [pts], 255); cv2.polylines(img, [pts], True, 0, 1)

W, H, FPS, DUR = 1280, 720, 30, 6.0
PARA = (900, 420)  # a seta anda de (120, 150) até o botão e para ali em 3 s
def tela_sintetica(arq, com_cursor=True, menu=True):
    p = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "16", str(arq)], stdin=subprocess.PIPE)
    for i in range(int(DUR * FPS)):
        t = i / FPS
        img = np.full((H, W), 40, np.uint8)
        cv2.rectangle(img, (0, 0), (W, 40), 70, -1); cv2.rectangle(img, (860, 400), (1000, 440), 90, -1)   # barra de menus e o botão
        if menu and t >= 3.4:
            cv2.rectangle(img, (860, 445), (1100, 640), 120, -1)                                          # menu abre embaixo do botão
        if com_cursor:
            q = min(1.0, t / 3.0)
            seta(img, int(120 + (PARA[0] - 120) * q), int(150 + (PARA[1] - 150) * q), 1.4)
        p.stdin.write(img.tobytes())
    p.stdin.close(); p.wait()

tela = tmp / "tela.mp4"; tela_sintetica(tela)
tela_parada = tmp / "tela-sem-cursor.mp4"; tela_sintetica(tela_parada, com_cursor=False)

# 1. cursor: diferença de 3 quadros + miolo branco com borda preta
r = E.rastro_cursor(tela, 0.0, 3.6)
check(len(r) >= 15, f"cursor visto enquanto anda ({len(r)} posições em 3,6 s)")
def verdade(t):
    q = min(1.0, t / 3.0); return (120 + (PARA[0] - 120) * q) / W, (150 + (PARA[1] - 150) * q) / H
erro = max(max(abs(x - verdade(t)[0]), abs(y - verdade(t)[1])) for t, x, y in r) if r else 1
check(erro < 0.03, f"ponta da seta no lugar certo (erro máximo {erro:.3f} da tela)")
check(r and abs(r[-1][1] - PARA[0] / W) < 0.02 and abs(r[-1][2] - PARA[1] / H) < 0.03, "última posição vista = botão onde o cursor parou")
check(E.rastro_cursor(tela_parada, 0.0, 6.0) == [], "tela sem cursor: nada visto (o menu abrindo não é cursor)")

# 2. texto da fala: verbo de ação dito ao espectador, até 4 palavras
casos = {"e agora você vai clicar nesse maisinho aqui, tá bom?": "Clique no Maisinho", "você vai aqui em cima ó, em ferramentas, ok?": "Vá em Ferramentas",
         "aqui você vai pra pasta de downloads e ó": "Vá pra Downloads", "e clicar em abrir, perfeito.": "Clique em Abrir"}
for f, esperado in casos.items():
    got = [a["texto"] for a in E.acoes_da_fala(fala(f))]
    check(got == [esperado], f"'{f}' → {got}")
check(E.acoes_da_fala(fala("ele vai pra sua pasta de downloads")) == [], "'ele vai pra pasta' não é instrução: sem etiqueta")
check(E.acoes_da_fala(fala("o som ficou muito bom hoje")) == [], "fala sem verbo de ação: sem etiqueta")
check(all(len(E.curto(t).split()) <= 4 for t in ("Clique com o botão direito do mouse", "Abra as configurações avançadas de vídeo agora")), "texto cortado em 4 palavras")

# 3. auto na tela sintética: nasce no verbo, ancorada no cursor, acompanha e não cobre o ponto
pal = fala("agora você vai clicar nesse botão aqui", inicio=1.2)  # "clicar" em 2,1 s, com o cursor ainda andando
blocos = [{"modo": "tela", "inicio": 0.0, "fim": DUR}]
ets, res = E.etiquetas_de("auto", pal, DUR, tela=tela, focos=[], blocos=blocos)
check(len(ets) == 1 and ets[0]["texto"] == "Clique no Botão", f"uma etiqueta 'Clique no Botão' ({[e['texto'] for e in ets]})")
e = ets[0] if ets else {}
t_verbo = pal["palavras"][3]["inicio"]
check(e.get("inicio") == t_verbo and 1.5 <= e.get("fim", 0) - e.get("inicio", 0) <= 2.6, "entra no verbo dito e fica ~2,4 s")
check(e.get("origem") == "cursor" and abs(e.get("x", 0) - verdade(t_verbo)[0]) < 0.04 and abs(e.get("y", 0) - verdade(t_verbo)[1]) < 0.05,
      f"ancorada na ponta do cursor naquele instante ({e.get('x')}, {e.get('y')})")
check(len(e.get("rastro", [])) >= 2 and e["rastro"][-1][1] > e["x"], "leva o rastro do cursor andando (a etiqueta acompanha)")
check((e.get("lado"), e.get("vert")) == ("dir", "cima"), "balão acima e à direita da ponta (a seta desce para baixo e à direita)")
check(E.lado_de(0.9, 0.5) == ("esq", "cima") and E.lado_de(0.3, 0.05) == ("dir", "baixo"), "perto da borda o balão vira (nunca sai da tela nem cobre a ponta)")

# 4. sem cursor: centro do foco ativo; sem foco: fica fora com aviso
foco = [{"inicio": 3.2, "fim": 6.0, "x": 0.76, "y": 0.75, "zoom": 1.5}]
ets2, res2 = E.etiquetas_de("auto", pal, DUR, tela=tela_parada, focos=foco, blocos=blocos)
check(len(ets2) == 1 and ets2[0]["origem"] == "foco" and (ets2[0]["x"], ets2[0]["y"]) == (0.76, 0.75), "sem cursor visto: ancora no centro do foco ativo")
ets3, res3 = E.etiquetas_de("auto", pal, DUR, tela=tela_parada, focos=[], blocos=blocos)
check(ets3 == [] and res3["puladas"].get("sem_posicao") == 1 and res3["avisos"], "sem cursor e sem foco: fora, com aviso")

# 4b. a câmera virtual não deixa a ponta fora do quadro: o foco anda até ela
fz = [{"inicio": 0.3, "fim": 3.3, "x": 0.64, "y": 0.56, "zoom": 1.3}]
n_aj = E.ajustar_focos(fz, [{"inicio": 1.9, "fim": 4.3, "x": 0.43, "y": 0.15, "rastro": [[2.2, 0.41, 0.11]]}])
meia = 0.5 / fz[0]["zoom"]
check(n_aj == 1 and fz[0]["y"] - meia <= 0.11 - 0.05 and fz[0]["x"] - meia <= 0.41, f"foco que cobria outro lugar anda até o cursor ({fz[0]})")

# 5. limites
dois = fala("você vai clicar em salvar e você vai clicar em fechar", inicio=1.0)
ets4, res4 = E.etiquetas_de("auto", dois, DUR, tela=None, focos=[{"inicio": 0.5, "fim": 6, "x": 0.5, "y": 0.5, "zoom": 1.4}], blocos=blocos)
check(len(ets4) == 1 and res4["puladas"].get("perto_da_anterior") == 1, "3 s entre etiquetas: a segunda, 1,8 s depois, sai")
leit = [{"tipo": "manchete", "inicio": 3.0, "fim": 5.0}]
ets5, res5 = E.etiquetas_de("auto", pal, DUR, tela=tela, focos=[], blocos=blocos, grafismos=leit)
check(ets5 == [] and res5["puladas"].get("em_cima_de_texto") == 1, "não entra em cima de grafismo de leitura")
ets6, res6 = E.etiquetas_de("auto", pal, DUR, tela=tela, focos=[], blocos=[{"modo": "cheio", "inicio": 0, "fim": DUR}])
check(ets6 == [] and res6["puladas"].get("fora_da_tela") == 1, "fora de bloco de tela não entra")
muitas = [{"texto": f"Clique em item {i}", "inicio": i * 4.1, "x": 0.4, "y": 0.4} for i in range(14)]
ets7, res7 = E.etiquetas_de(muitas, None, 60.0, blocos=[{"modo": "tutorial", "inicio": 0, "fim": 60.0}])
check(len(ets7) == E.POR_MIN and res7["puladas"].get("teto_por_minuto"), f"no máximo {E.POR_MIN} por minuto")

# 6. pedido do agente: texto@segundo, palavra e x/y
ets8, res8 = E.etiquetas_de("Abra o menu Configurações agora mesmo@1.0", None, DUR, tela=tela, blocos=blocos)
check(len(ets8) == 1 and len(ets8[0]["texto"].split()) <= 4 and any("4 palavras" in a for a in res8["avisos"]), "texto@segundo do agente, cortado em 4 palavras com aviso")
ets9, _ = E.etiquetas_de([{"texto": "Clique aqui", "palavra": "botão", "x": 0.7, "y": 0.58}], pal, DUR, tela=tela, blocos=blocos)
check(len(ets9) == 1 and ets9[0]["origem"] == "agente" and ets9[0]["inicio"] == pal["palavras"][5]["inicio"], "x/y e palavra do agente valem")

# 7. no plano de grafismos: `etiqueta_mouse` sai para a camada da tela e o normalizar não a trata como grafismo do quadro
plano = {"itens": [{"tipo": "manchete", "texto": "Zoom no OBS", "inicio": 0.5}, {"tipo": "etiqueta_mouse", "texto": "Clique no botão", "palavra": "clicar"}]}
resto, etq = E.separar_do_plano(json.dumps(plano))
check(len(etq) == 1 and [g["tipo"] for g in resto["itens"]] == ["manchete"], "separar_do_plano tira a etiqueta do plano de grafismos")
its, av = G.normalizar(plano, pal, DUR)
check([g["tipo"] for g in its] == ["manchete"] and not any("etiqueta" in a for a in av), "normalizar ignora etiqueta_mouse sem aviso (vive na tela)")
check("etiqueta_mouse" in G.TIPOS, "tipo registrado em grafismos.TIPOS (o agente vê no planejar_grafismos)")

# 8. ligações: acabamento, MCP, Remotion e regra do agente
fonte = inspect.getsource(acabamento)
check('etq.separar_do_plano' in fonte and 'cfg["etiquetas"]' in fonte and 'lay_cfg or {}).get("etiquetas"' in fonte, "acabamento: plano → camada da tela; janela da etiqueta vira janela de leitura (sem tremor)")
check("etiquetas" in inspect.signature(servidor.montar_remotion).parameters and "etiquetas" in inspect.signature(acabamento.montar_remotion).parameters, "montar_remotion (MCP) aceita etiquetas")
tsx = (RAIZ / "remotion" / "src" / "Layout.tsx").read_text(encoding="utf-8"); tipos = (RAIZ / "remotion" / "src" / "tipos.ts").read_text(encoding="utf-8")
check("export type Etiqueta" in tipos and "etiquetas?: Etiqueta[]" in tipos, "tipos.ts: Etiqueta e LayoutCfg.etiquetas")
check("EtiquetaMouse" in tsx and tsx.count("etiquetas={cfg.etiquetas}") == 2 and "Easing.back(2.2)" in tsx, "Layout.tsx desenha a etiqueta com pop na tela do tutorial e da tela/aula")
ref = (RAIZ / "fluxos" / "_acabamento-referencia.md").read_text(encoding="utf-8")
check("etiquetas=" in ref and "etiqueta_mouse" in ref, "referência de acabamento ensina quando usar")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
