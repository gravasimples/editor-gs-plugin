"""Fase B (07/11/2026): plano de grafismos semântico, logos reais, legenda fora da tela cheia e modo série.
Tudo em pasta temporária (EDITOR_GS_WORKSPACE). Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_grafismos.py"""
import inspect, json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-grafismos-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import grafismos as g
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def fala(texto, inicio=0.0, passo=0.4):
    ws = [{"palavra": w, "inicio": round(inicio + i * passo, 2), "fim": round(inicio + i * passo + 0.3, 2)} for i, w in enumerate(texto.split())]
    return {"palavras": ws, "segmentos": [{"inicio": ws[0]["inicio"], "fim": ws[-1]["fim"], "texto": texto}], "duracao_s": ws[-1]["fim"] + 0.5}

pal = fala("Áudio bom não custa caro você não precisa configurar nada sem instalar sem depender de ninguém dá pra usar no Meet no Zoom e no OBS e paga até R$ 100 reais")
ws = g.palavras_planas(pal)

# ancoragem na palavra
check(g.ancorar("caro", ws) == 1.6, "ancora na palavra dita (caro → 1,6 s)")
check(g.ancorar("não", ws, perto=3.0) == 2.4, "com várias ocorrências, pega a mais perto do tempo dado")
check(g.ancorar("no zoom", ws) is not None, "expressão de duas palavras também ancora")
check(g.ancorar("webcam", ws) is None, "palavra que não foi dita devolve None")

# mídia
lg = g.resolver_logo("Meet")
check(lg and lg["tipo"] == "svg" and lg["marca"] and lg["cor"].startswith("#") and "<path" in lg["svg"], "logo do Meet vem do Simple Icons com a cor oficial")
check(g.resolver_logo("obs studio")["svg"] == g.resolver_logo("obs")["svg"], "apelidos falados levam ao mesmo logo")
check(g.resolver_logo("canva") is None, "logo que não existe devolve None (não inventa)")
(tmp / "ws" / "marca" / "logos").mkdir(parents=True)
from PIL import Image
Image.new("RGB", (64, 64), "white").save(tmp / "ws" / "marca" / "logos" / "canva.png")
check(g.resolver_logo("canva")["tipo"] == "img", "arquivo em marca/logos/ entra quando o Simple Icons não tem")
Image.new("RGB", (64, 64), "red").save(tmp / "ws" / "marca" / "logos" / "zoom.png")
check(g.resolver_logo("zoom")["tipo"] == "img", "arquivo da marca tem prioridade sobre o Simple Icons")
ic = g.resolver_icone("usb")
check(ic and not ic["marca"] and "stroke" in ic["svg"], "ícone de objeto vem do Lucide")

# normalização
plano = {"itens": [
    {"tipo": "manchete", "palavra": "caro", "inicio": 1.0, "rotulo": "Áudio bom", "texto": "Não custa caro", "destaque": "caro", "ondas": True},
    {"tipo": "riscado", "palavra": "configurar", "texto": "Configurar", "troca": "Plugou, usou"},
    {"tipo": "checklist", "inicio": 4.0, "itens": [{"texto": "Sem instalar", "palavra": "instalar"}, {"texto": "Sem depender", "palavra": "depender"}]},
    {"tipo": "logos", "inicio": 7.0, "itens": [{"logo": "meet", "palavra": "meet"}, {"logo": "zoom", "palavra": "zoom"}, {"logo": "obs", "palavra": "obs"}, {"logo": "inexistente-xyz"}]},
    {"tipo": "numero", "palavra": "100", "tela_cheia": True, "rotulo": "até", "texto": "R$ 100", "fim": 99},
    {"tipo": "foguete", "inicio": 2.0},
    {"tipo": "pilula", "inicio": 3.0},
]}
itens, avisos = g.normalizar(plano, pal)
tipos = [i["tipo"] for i in itens]
check(tipos == ["manchete", "riscado", "checklist", "logos", "numero"], f"tipos válidos em ordem, inválidos fora ({tipos})")
check(any("foguete" in a for a in avisos) and any("pilula" in a and "sem texto" in a for a in avisos), "avisa tipo desconhecido e texto faltando")
check(itens[0]["inicio"] == 1.6 and itens[0]["posicao"] == "peito", "manchete entra na palavra e fica no peito")
check(all(i["fim"] <= j["inicio"] for i, j in zip(itens, itens[1:]) if i["posicao"] == j["posicao"]), "mesma posição não sobrepõe")
lo = itens[3]
check([x["em"] for x in lo["itens"][:3]] == sorted(x["em"] for x in lo["itens"][:3]) and lo["itens"][0]["midia"]["marca"], "logos acumulam na ordem em que são ditos")
check(any("inexistente-xyz" in a for a in avisos), "logo inexistente vira aviso")
nu = itens[4]
check(nu["tela_cheia"] and nu["posicao"] == "centro" and nu["fim"] <= pal["duracao_s"], "tela cheia vai para o centro e o fim respeita a duração")
check(g.trechos_tela_cheia(itens) == [(nu["inicio"], nu["fim"])], "trechos de tela cheia listados")
it2, av2 = g.normalizar({"itens": [{"tipo": "manchete", "inicio": 1, "texto": "x" * 40}]}, pal)
check(any("caracteres" in a for a in av2), "texto longo vira aviso")
it3, av3 = g.normalizar({"itens": [{"tipo": "riscado", "inicio": 1, "texto": "A", "troca": "B", "troca_em": 5}, {"tipo": "pilula", "inicio": 3, "texto": "C"}]}, pal)
check(any("adiante o próximo" in a for a in av3), "troca que cai depois do fim (próximo ocupou o lugar) vira aviso")
it4, av4 = g.normalizar({"itens": [{"tipo": "pilula", "inicio": 1, "texto": "A"}, {"tipo": "pilula", "inicio": 1.2, "texto": "B"}]}, pal)
check(it4[1]["inicio"] >= it4[0]["inicio"] + 0.7 and any("brigam" in a for a in av4), "dois no mesmo lugar ao mesmo tempo: o segundo atrasa e avisa")
arq = tmp / "plano.json"; arq.write_text(json.dumps(plano), encoding="utf-8")
check(len(g.normalizar(str(arq), pal)[0]) == 5 and len(g.normalizar(json.dumps(plano), pal)[0]) == 5, "aceita caminho ou JSON inline")

# mídias locais copiadas para o render
pub = tmp / "pub"; pub.mkdir()
itens_img, _ = g.normalizar({"itens": [{"tipo": "logos", "inicio": 1, "itens": [{"logo": "canva"}]}]}, pal)
criados = g.preparar_midias(itens_img, pub, "abc")
m = itens_img[0]["itens"][0]["midia"]
check(len(criados) == 1 and criados[0].exists() and m["arquivo"] == criados[0].name and "origem" not in m, "imagem local vai para public/render e o caminho local some das props")

# plano automático
pal_auto = fala("você não precisa configurar nada isso é muito bom de verdade gente olha só funciona sem instalar e sem depender de ninguém tá vendo como é simples "
                "e dá pra usar no Meet e no Zoom também e tudo isso custa até R$ 100 reais", passo=0.5)
auto = g.plano_auto(pal_auto)
ta = [i["tipo"] for i in auto["itens"]]
check("checklist" in ta and "riscado" in ta and "logos" in ta and "numero" in ta, f"regras acham checklist, riscado, logos e número ({ta})")
num = next(i for i in auto["itens"] if i["tipo"] == "numero")
check(num["texto"].startswith("R$"), f"número com R$ sai junto ({num['texto']})")
check(len(g.plano_auto(fala("tem 5 jeitos de fazer"))["itens"]) == 0 or all(i["tipo"] != "numero" for i in g.plano_auto(fala("tem 5 jeitos de fazer"))["itens"]), "número solto sem unidade não vira gráfico")
check(len(g.frases(pal)) == 1 and g.frases(pal)[0].startswith("[0.00–"), "fala em linhas [ini–fim] para o agente")

# legenda some na tela cheia
ass = tmp / "l.ass"
ass.write_text("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
               "Dialogue: 0,0:00:01.00,0:00:02.00,Legenda,,0,0,0,,antes\nDialogue: 0,0:00:10.00,0:00:11.00,Legenda,,0,0,0,,dentro\nDialogue: 0,0:00:20.00,0:00:21.00,Legenda,,0,0,0,,depois\n", encoding="utf-8")
g.ass_sem_trechos(ass, [(9.5, 12.0)], tmp / "l2.ass")
t2 = (tmp / "l2.ass").read_text(encoding="utf-8")
check("antes" in t2 and "depois" in t2 and "dentro" not in t2 and "[Events]" in t2, "ASS perde só as falas da tela cheia")

# séries
r = g.salvar_serie("O óbvio precisa ser dito", "O óbvio precisa ser dito", destaque="precisa ser dito", trilha="trilhas/x.mp3")
check(Path(r["arquivo"]).name == "o-obvio-precisa-ser-dito.json" and str(tmp) in r["arquivo"], "série salva em workspace/series/ com nome limpo")
check(g.carregar_serie("o óbvio precisa ser dito")["destaque"] == "precisa ser dito", "série carrega pelo nome falado")
check([s["slug"] for s in g.listar_series()] == ["o-obvio-precisa-ser-dito"], "listar_series")
try:
    g.carregar_serie("não existe"); check(False, "série inexistente dá erro claro")
except Exception as e:
    check("salvar_serie" in str(e), "série inexistente dá erro claro")

# servidor e motor
for nome in ("planejar_grafismos", "validar_grafismos", "salvar_serie", "listar_series"):
    check(callable(getattr(servidor, nome, None)), f"ferramenta MCP {nome}")
sig = inspect.signature(servidor.montar_remotion).parameters
check(all(k in sig for k in ("grafismos", "serie", "parte")), "montar_remotion aceita grafismos, serie e parte")
pj = tmp / "pal.json"; pj.write_text(json.dumps(pal), encoding="utf-8")
pg = servidor.planejar_grafismos(str(pj), str(tmp / "out" / "grafismos.json"))
check("fala" in pg and "tipos" in pg and (tmp / "out" / "grafismos.json").exists(), "planejar_grafismos devolve fala, tipos e grava o rascunho")
vg = servidor.validar_grafismos(json.dumps(plano), str(pj))
check(len(vg["itens"]) == 5 and "<path" not in json.dumps(vg), "validar_grafismos devolve itens sem despejar o SVG inteiro")
from editor_video import acabamento
fonte = inspect.getsource(acabamento)  # 13/11: ass_sem_trechos fica em _acabar_montagem, chamada pelo montar_remotion
check("chaves = []" in fonte and "ass_sem_trechos" in fonte and '"grafismos": graf_itens' in fonte, "acabamento: grafismos substituem palavras-chave, legenda some na tela cheia, props levam o plano")
for nome in ("profissional", "lista"):
    e = json.loads((RAIZ / "estilos" / f"{nome}.json").read_text(encoding="utf-8"))
    check(e["montagem"].get("grafismos") == "auto" and e["legenda"].get("posicao") == "baixa", f"estilo {nome}: grafismos ligados e legenda embaixo")
ag = (RAIZ / "workspace" / "AGENTS.md").read_text(encoding="utf-8") + (RAIZ / "fluxos" / "_acabamento-referencia.md").read_text(encoding="utf-8")  # 13/11: parâmetros foram para a referência
check("planejar_grafismos" in ag and "validar_grafismos" in ag and "serie=" in ag, "AGENTS.md ensina o plano de grafismos e o modo série")
tsx = (RAIZ / "remotion" / "src" / "Grafismos.tsx").read_text(encoding="utf-8")
check(all(f"case '{t}'" in tsx for t in list(g.TIPOS) + ["serie"]), "Remotion desenha todos os tipos do catálogo")
from servico import plataforma as _plat
node = _plat.node_bin() or Path.home() / ".nvm/versions/node/v24.22.1/bin"
r = subprocess.run([_plat.npx(), "tsc", "--noEmit", "-p", "."], cwd=RAIZ / "remotion", capture_output=True, text=True, env={**os.environ, "PATH": f"{node}{os.pathsep}{os.environ['PATH']}"})
check(r.returncode == 0, f"Remotion compila sem erro de tipo {r.stdout[-300:]}")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
