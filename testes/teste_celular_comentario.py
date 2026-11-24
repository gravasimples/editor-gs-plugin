"""Celular com conversa e cartão de comentário (16/11/2026, lacuna 3 dos Criativos): bolhas uma a uma com lado e tempo, comentário com estrelas,
avisos, janela de leitura (sem tremor em cima) e desenho no Remotion sem marca de app. Rodar: python -X utf8 -I testes/teste_celular_comentario.py"""
import os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
os.environ["EDITOR_GS_WORKSPACE"] = str(Path(tempfile.mkdtemp(prefix="gs-teste-celular-")) / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import grafismos as g, transicoes as trn

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

pal = {"palavras": [{"palavra": "mandou", "inicio": 2.0, "fim": 2.3}, {"palavra": "funciona", "inicio": 4.1, "fim": 4.5}, {"palavra": "comentou", "inicio": 12.0, "fim": 12.4}]}
its, av = g.normalizar({"itens": [
    {"tipo": "celular", "inicio": 1.5, "nome": "Cliente", "itens": [{"texto": "Oi! Isso funciona no celular?"}, {"texto": "Funciona sim", "lado": "eu", "palavra": "funciona"},
                                                                    {"texto": ""}, {"texto": "x" * 100, "lado": "EU"}]},
    {"tipo": "comentario", "palavra": "comentou", "inicio": 11.5, "nome": "Aluna de SP", "texto": "Fiz minha primeira live com o celular e deu certo demais!", "estrelas": 7, "rotulo": "há 2 h"},
    {"tipo": "comentario", "inicio": 16, "itens": [{"nome": "M.", "texto": "Ajudou muito", "estrelas": 4.6}, {"nome": "R.", "texto": "Top"}, {"nome": "Z."}]},
    {"tipo": "comentario", "inicio": 20},
    {"tipo": "celular", "inicio": 23, "itens": []},
]}, pal, duracao_s=30)
cel = next(x for x in its if x["tipo"] == "celular")
b = cel["itens"]
check(cel["posicao"] == "centro" and cel["nome"] == "Cliente", "celular no centro com o nome do contato")
check(len(b) == 3 and [x["lado"] for x in b] == ["outro", "eu", "eu"], "bolhas sem texto saem; lado normalizado (outro por padrão)")
check(b[0]["em"] == 2.0 and b[1]["em"] == 4.1, f"primeira bolha 0,5 s depois de abrir; a seguinte na palavra dita ({b[0]['em']}, {b[1]['em']})")
check(b[2]["em"] - b[1]["em"] >= 1.0 or b[2]["em"] == round(1.5 + 0.5 + 1.1 * 3, 2), "sem `em`, uma bolha a cada 1,1 s")
check(cel["fim"] >= b[-1]["em"] + 1.5, "o celular fica na tela até a última bolha ser lida")
check(any("bolha 3: sem texto" in a for a in av) and any("100 caracteres" in a for a in av), "avisa bolha vazia e mensagem longa")
coms = [x for x in its if x["tipo"] == "comentario"]
check(len(coms) == 2, "comentário sem texto nenhum não entra")
c1 = coms[0]
check(c1["inicio"] == 12.0 and c1["estrelas"] == 5 and c1["nome"] == "Aluna de SP" and c1["rotulo"] == "há 2 h", "comentário único: na palavra, estrelas limitadas a 5")
check(not any("caracteres; na tela" in a and "comentario" in a for a in av), "texto longo do comentário não gera aviso de manchete")
c2 = coms[1]
check([x["nome"] for x in c2["itens"]] == ["M.", "R."] and c2["itens"][0]["estrelas"] == 5, "vários comentários empilhados; sem texto sai; estrela arredonda")
check(any("(celular): sem itens" in a for a in av) and any("(comentario): sem texto" in a for a in av), "avisa celular vazio e comentário sem texto")

# leitura: tremor nunca em cima de conversa/comentário
jan = trn.janelas_de_leitura(its)
check(any(a <= 3.0 <= z for a, z in jan) and any(a <= 13.0 <= z for a, z in jan), "celular e comentário entram nas janelas de leitura")
planos = [{"inicio": 0.0, "fim": 3.0, "entrada": "seco", "z0": 1, "z1": 1, "dur": 0}, {"inicio": 3.0, "fim": 5.0, "entrada": "tremor", "z0": 1, "z1": 1, "dur": 0.3}]
pl, reb = trn.limitar_efeitos(planos, 30, jan)
check(pl[1]["entrada"] != "tremor" and reb["tremor"] == 1, "tremor dentro da conversa é rebaixado")

tsx = (RAIZ / "remotion" / "src" / "Grafismos.tsx").read_text(encoding="utf-8")
check("case 'celular'" in tsx and "case 'comentario'" in tsx and "const Avatar" in tsx, "Remotion desenha celular, comentário e avatar genérico")
corpo = tsx[tsx.index("case 'celular'"):tsx.index("case 'ondas'")].lower()
check(not any(m in corpo for m in ("whatsapp", "instagram", "#25d366", "#075e54", "#128c7e", "staticfile(")), "sem marca nem cor de app real e sem imagem externa")
check("digitando" in corpo and "★" in corpo, "tem o \"digitando\" e as estrelas")
check("'celular'" in (RAIZ / "remotion" / "src" / "tipos.ts").read_text(encoding="utf-8"), "tipos.ts conhece celular e comentario")
ref = (RAIZ / "fluxos" / "_acabamento-referencia.md").read_text(encoding="utf-8") + (RAIZ / "workspace" / "AGENTS.md").read_text(encoding="utf-8")
check("`celular`" in ref and "`comentario`" in ref and "pseudonim" in ref, "regra na referência e no AGENTS.md (autor pseudonimizado)")
check("`celular`" in (RAIZ / "mcp" / "editor-de-video" / "servidor.py").read_text(encoding="utf-8"), "planejar_grafismos ensina quando usar")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
