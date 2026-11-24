"""Cartão de história e grade em cascata (16/11/2026, lacuna 7 dos Criativos): páginas na palavra, tela cheia por padrão, grade com cascata e colunas,
avisos, janela de leitura e desenho no Remotion. Rodar: python -X utf8 -I testes/teste_historia_grade.py"""
import os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ["EDITOR_GS_WORKSPACE"] = str(Path(tempfile.mkdtemp(prefix="gs-teste-historia-")) / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import grafismos as g, transicoes as trn

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

pal = {"palavras": [{"palavra": "equipamento", "inicio": 1.0, "fim": 1.6}, {"palavra": "jeito", "inicio": 3.4, "fim": 3.7}, {"palavra": "microfone", "inicio": 12.6, "fim": 13.0}]}
its, av = g.normalizar({"itens": [
    {"tipo": "historia", "palavra": "equipamento", "inicio": 0.8, "rotulo": "A real", "texto": "Não é falta de equipamento", "destaque": "equipamento",
     "itens": [{"texto": "Não é falta de equipamento"}, {"texto": "É falta de fazer do jeito certo", "sub": "Treine antes da live oficial", "palavra": "jeito"}, {"sub": "sem título"}]},
    {"tipo": "historia", "inicio": 7, "texto": "Uma frase só, com mais de trinta e quatro caracteres aqui", "sub": "apoio", "tela_cheia": False, "posicao": "centro"},
    {"tipo": "grade", "inicio": 11, "colunas": 7, "itens": [{"icone3d": "notebook", "texto": "Computador"}, {"icone3d": "camera_video", "texto": "Webcam"},
                                                           {"icone3d": "microfone", "texto": "Microfone", "palavra": "microfone"}, {"icone": "usb", "texto": "USB"}, {"texto": ""}]},
    {"tipo": "grade", "inicio": 20, "itens": [{"texto": "A"}, {"texto": "B"}, {"texto": "C"}, {"texto": "D"}, {"texto": "E"}, {"texto": "F"}, {"texto": "G"}, {"texto": "H"}, {"texto": "I"}, {"texto": "J"}]},
    {"tipo": "historia", "inicio": 26},
]}, pal, duracao_s=40)
h = [x for x in its if x["tipo"] == "historia"]
check(len(h) == 2, "história sem texto nenhum não entra")
h1 = h[0]
check(h1["tela_cheia"] and h1["posicao"] == "centro", "história em tela cheia por padrão")
check([p["em"] for p in h1["itens"]] == [1.0, 3.4], f"páginas: a primeira na abertura, a segunda na palavra dita ({[p['em'] for p in h1['itens']]})")
check(h1["fim"] >= 3.4 + 1.6, "a última página fica no ar para ser lida")
check(any("página 3: sem texto" in a or "subitem 3" in a for a in av), "página sem texto avisa e sai")
h2 = h[1]
check(not h2["tela_cheia"] and "itens" not in h2 and h2["sub"] == "apoio", "história de uma página só, fora da tela cheia quando pedido")
check(not any("caracteres; na tela" in a and "historia" in a for a in av), "título longo da história não gera aviso de manchete")
gr = [x for x in its if x["tipo"] == "grade"]
g1 = gr[0]
check(len(g1["itens"]) == 4 and g1["colunas"] == 4, "grade: item vazio sai, colunas limitadas a 4")
ems = [x["em"] for x in g1["itens"]]
check(ems[0] == 11.1 and ems[1] == 11.25 and ems[2] == 12.6, f"cascata de 0,15 s; item com palavra entra nela ({ems})")
check(g1["itens"][0]["midia"].get("icone3d") and g1["itens"][3]["midia"]["tipo"] == "svg", "grade aceita ícone 3D e Lucide")
check(len(gr[1]["itens"]) == 9 and any("só os 9 primeiros" in a for a in av), "grade até 9")
jan = trn.janelas_de_leitura(its)
check(any(a <= 2.0 <= z for a, z in jan) and any(a <= 11.5 <= z for a, z in jan), "história e grade são janela de leitura (sem tremor)")
tsx = (RAIZ / "remotion" / "src" / "Grafismos.tsx").read_text(encoding="utf-8")
check("case 'historia'" in tsx and "case 'grade'" in tsx, "Remotion desenha história e grade")
corpo = tsx[tsx.index("case 'historia'"):tsx.index("case 'grade'")]
check("enche" in corpo and "fecha" in corpo, "história tem barras de progresso e saída deslizando")
check("gridTemplateColumns" in tsx, "grade em CSS grid")
check("'historia'" in (RAIZ / "remotion" / "src" / "tipos.ts").read_text(encoding="utf-8"), "tipos.ts conhece historia e grade")
ref = (RAIZ / "fluxos" / "_acabamento-referencia.md").read_text(encoding="utf-8") + (RAIZ / "workspace" / "AGENTS.md").read_text(encoding="utf-8")
check("`historia`" in ref and "`grade`" in ref, "regra na referência e no AGENTS.md")
check("`grade`" in (RAIZ / "mcp" / "editor-de-video" / "servidor.py").read_text(encoding="utf-8"), "planejar_grafismos ensina quando usar")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
