"""Ícones/emoji 3D (16/11/2026, lacuna 1 dos Criativos): conjunto curado do Fluent Emoji (MIT) com licença e créditos, apelido pt e palavra falada → ícone,
grafismo `icone3d` e `icone3d` como mídia nos outros tipos. Rodar: python -X utf8 -I testes/teste_icone3d.py"""
import json, os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ["EDITOR_GS_WORKSPACE"] = str(Path(tempfile.mkdtemp(prefix="gs-teste-icone3d-")) / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from PIL import Image
from editor_video import grafismos as g, transicoes as trn

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

pasta = RAIZ / "remotion" / "public" / "icones3d"
lic = (pasta / "LICENSE").read_text(encoding="utf-8")
check("MIT License" in lic and "Copyright (c) Microsoft Corporation" in lic, "LICENSE original (MIT, Microsoft) junto dos ícones")
check("Fluent Emoji (c) Microsoft Corporation, MIT" in (pasta / "CREDITOS.md").read_text(encoding="utf-8"), "CREDITOS.md com a atribuição")
cat = g.catalogo_icones3d()
pngs = sorted(pasta.glob("*.png"))
check(40 <= len(cat) <= 80 and len(pngs) == len(cat), f"conjunto curado ({len(cat)} no catálogo, {len(pngs)} PNGs), não os 1.500")
check(all((pasta / v["arquivo"]).exists() for v in cat.values()), "todo apelido do catálogo tem arquivo")
im = Image.open(pasta / "foguete.png")
check(im.mode == "RGBA" and im.size == (256, 256), f"PNG 3D com transparência {im.size}")
for k in ("celular", "dinheiro", "camera", "microfone", "foguete", "check", "x", "coracao", "fogo", "estrela", "raio", "alvo", "grafico_subindo",
          "relogio", "cadeado", "presente", "lampada", "megafone", "olhos", "joinha", "palmas", "cem", "alerta", "trofeu"):
    if k not in cat:
        check(False, f"falta o ícone {k}")
todas = [w for v in cat.values() for w in v["palavras"]]
check(len(todas) == len(set(todas)), "cada palavra falada chama um ícone só")
pub = (RAIZ / ".gitignore").read_text(encoding="utf-8")
check("remotion/public/icones3d" not in pub and "remotion/public/icones3d" not in (RAIZ / "scripts" / "publicar_plugin.ps1").read_text(encoding="utf-8-sig"),
      "pasta vai no git e no plugin público")

# apelido e palavra falada
check(g.resolver_icone3d("Foguete")["nome"] == "foguete" and g.resolver_icone3d("grafico subindo")["nome"] == "grafico_subindo", "apelido com maiúscula e espaço")
check(g.resolver_icone3d("grana")["nome"] == "dinheiro" and g.icone3d_da_fala("o vídeo viralizou") == "fogo", "palavra falada → ícone (grana → dinheiro, viralizou → fogo)")
check(g.resolver_icone3d("ornitorrinco") is None and g.icone3d_da_fala("bom dia gente") is None, "sem ícone para palavra fora do mapa")

pal = {"palavras": [{"palavra": "ganhei", "inicio": 1.2, "fim": 1.5}, {"palavra": "grana", "inicio": 1.6, "fim": 1.9}, {"palavra": "celular", "inicio": 4.6, "fim": 5.0},
                    {"palavra": "viralizou", "inicio": 8.1, "fim": 8.6}]}
its, av = g.normalizar({"itens": [
    {"tipo": "icone3d", "inicio": 1, "palavra": "grana"},
    {"tipo": "icone3d", "inicio": 4, "itens": [{"icone3d": "foguete", "texto": "Decolou"}, {"palavra": "celular"}, {"icone3d": "nada-disso"}]},
    {"tipo": "icone3d", "inicio": 8, "palavra": "viralizou", "icone3d": "fogo", "texto": "Viral"},
    {"tipo": "icone3d", "inicio": 11, "palavra": "tchau"},
    {"tipo": "fluxo", "inicio": 13, "itens": [{"icone3d": "celular", "texto": "celular"}, {"icone": "usb"}, {"icone3d": "notebook"}]},
]}, pal, duracao_s=20)
a = its[0]
check(a["tipo"] == "icone3d" and a["inicio"] == 1.6 and a["itens"][0]["icone3d"] == "dinheiro" and a["itens"][0]["midia"]["icone3d"], "um ícone só: entra na palavra dita e o ícone sai dela")
b = its[1]
check([x["icone3d"] for x in b["itens"]] == ["foguete", "celular"] and b["itens"][1]["em"] == 4.6, "vários: apelido, palavra dita ancorando o tempo; o inexistente sai")
check(any("nada-disso" in x for x in av) and any("tchau" in x for x in av), "avisa ícone inexistente e palavra sem ícone")
check(its[2]["itens"][0]["icone3d"] == "fogo" and its[2]["itens"][0]["texto"] == "Viral" and "icone3d" not in its[2] and "midia" not in its[2], "campos do topo descem para o subitem")
check(len([x for x in its if x["tipo"] == "icone3d"]) == 3, "item sem ícone nenhum não entra")
fl = next(x for x in its if x["tipo"] == "fluxo")
check(fl["itens"][0]["midia"]["icone3d"] and fl["itens"][1]["midia"]["tipo"] == "svg", "icone3d vale como mídia no fluxo, junto de ícone Lucide")
check(a["fim"] - a["inicio"] == 2.0 and a["entrada"] == "mola", "duração e entrada padrão")

# Remotion: copia como imagem (hardlink) e desenha com pop + flutuação
render = Path(tempfile.mkdtemp(prefix="gs-teste-icone3d-pub-"))
criados = g.preparar_midias(its, render, "t")
check(len(criados) >= 4 and all("origem" not in x["midia"] and x["midia"]["arquivo"].endswith(".png") for x in b["itens"]), "preparar_midias copia o PNG para render/")
tsx = (RAIZ / "remotion" / "src" / "Grafismos.tsx").read_text(encoding="utf-8")
check("case 'icone3d'" in tsx and "Math.sin(tt" in tsx and "m.icone3d" in tsx, "Remotion desenha icone3d (pop, flutuação) e a mídia icone3d inteira")
check("'icone3d'" in (RAIZ / "remotion" / "src" / "tipos.ts").read_text(encoding="utf-8"), "tipos.ts conhece icone3d")
check("icone3d" not in trn.LEITURA, "ícone não é texto de leitura (o tremor pode passar)")
srv = (RAIZ / "mcp" / "editor-de-video" / "servidor.py").read_text(encoding="utf-8")
check("icones3d" in srv and "catalogo_icones3d" in srv, "planejar_grafismos devolve a lista de ícones 3D ao agente")
ref = (RAIZ / "fluxos" / "_acabamento-referencia.md").read_text(encoding="utf-8") + (RAIZ / "workspace" / "AGENTS.md").read_text(encoding="utf-8")
check("icone3d" in ref and "Fluent Emoji" in ref, "regra na referência de acabamento e no AGENTS.md")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
