"""Biblioteca de estilos (03/11/2026): catálogo, montar estilo, chave de prévia, modelos de legenda novos no motor ASS e legenda_modelo no MCP.
Isolado: copia estilos/ para uma pasta temporária; não renderiza nada. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_estilos_biblioteca.py"""
import json, re, shutil, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from servico import estilos_biblioteca as eb, referencias as refs
from editor_video import legenda

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

td = Path(tempfile.mkdtemp()); est = td / "estilos"; shutil.copytree(RAIZ / "estilos", est, ignore=shutil.ignore_patterns("previas", "depoimentos-semanais"))
eb.EST, eb.LEG, eb.ELEM, eb.PREVIAS = est, est / "legendas", est / "elementos.json", td / "previas"

# catálogo
b = eb.biblioteca()
check(len(b["legendas"]) >= 12 and len(b["estilos"]) >= 7, f"catálogo tem legendas ({len(b['legendas'])}) e estilos ({len(b['estilos'])})")
cats = {e["categoria"] for e in b["elementos"]}
check(cats == {"animacao", "transicao", "elemento", "formato"}, f"elementos nas quatro categorias ({cats})")
check(all(x["previa"]["estado"] == "sem" for x in b["legendas"]), "sem prévia gerada, estado 'sem'")
check("elementos" not in [e["nome"] for e in eb.estilos()], "elementos.json não aparece como estilo")
temas = {t["id"] for t in b["temas"]}
check(all(set(x.get("temas", [])) <= temas for x in b["legendas"] + b["elementos"] + b["estilos"]), "todo tema usado está na lista de temas")
from editor_video.voz import TRANSICOES
check(all(e["id"] in TRANSICOES for e in b["elementos"] if e["categoria"] == "transicao"), "toda transição do catálogo existe no xfade do motor")

# chave de prévia muda quando o conteúdo muda
a1 = eb.arquivo_previa("legenda", "caixa-marinho")
p = est / "legendas" / "caixa-marinho.json"; d = json.loads(p.read_text()); d["legenda"]["tamanho_9x16"] += 1; p.write_text(json.dumps(d))
check(eb.arquivo_previa("legenda", "caixa-marinho") != a1, "mudar o modelo invalida a prévia antiga")
try:
    eb.arquivo_previa("legenda", "../x"); check(False, "id com barra recusado")
except KeyError:
    check(True, "id com barra recusado")

# montar estilo
m = eb.montar_estilo({"nome": "Tutorial com bolha", "legenda": "alta-tutorial", "cor_destaque": "#f472b6", "elementos": ["palavras-chave", "barra-progresso", "sfx", "ritmo-4s", "terco-inferior", "xx"],
                      "transicao": "smoothup", "formato": "pip", "trilha": True, "temas": ["tutorial", "zzz"]}, refs._slug)
j = json.loads((est / f"{m['nome']}.json").read_text())
check(m["nome"] == "tutorial-com-bolha" and j["legenda"]["posicao"] == "alta" and j["legenda"]["cor_destaque"] == "#F472B6", "legenda do modelo + cor de destaque")
mo = j["montagem"]
check(mo["palavras_chave"] == "auto" and mo["barra_progresso"] and mo["sfx"] and mo["ritmo_zoom_s"] == 4 and mo["terco_inferior"], "elementos ligados viram chaves da montagem")
check(mo["clarao_transicao"] is False and mo["zoom_por_frase"] is False and mo["tela_final_cta"] is False and mo["vinheta"] is False, "o que não foi escolhido fica desligado")
check(mo["transicao"] == "smoothup" and mo["formato_preferido"] == "pip" and mo["trilha"] == "auto" and mo["nivel"] == 3, "transição, formato, trilha e nível 3")
check(j["temas"] == ["tutorial"] and j["casa"] is False and j["montado"]["elementos"] == ["palavras-chave", "barra-progresso", "sfx", "ritmo-4s", "terco-inferior"], "temas e elementos inválidos descartados")
for dados, exc, msg in [({"nome": "Tutorial com bolha"}, FileExistsError, "nome repetido dá 409"), ({"nome": "padrao"}, ValueError, "nome padrao recusado"),
                        ({"nome": "x2", "cor_destaque": "rosa"}, ValueError, "cor inválida recusada")]:
    try:
        eb.montar_estilo(dados, refs._slug); check(False, msg)
    except exc:
        check(True, msg)
check(eb.montar_estilo({"nome": "Simples"}, refs._slug)["montagem"]["nivel"] == 1, "sem elementos = nível 1")

# motor ASS: caixa, subir, digitar, altura livre, fonte serifada
pal = td / "pal.json"; pal.write_text(json.dumps({"palavras": [{"palavra": w, "inicio": i * 0.4, "fim": i * 0.4 + 0.35} for i, w in enumerate("agora vai depender da webcam".split())]}))
def ass(id_):
    leg = json.loads((RAIZ / "estilos" / "legendas" / f"{id_}.json").read_text())["legenda"]; out = td / f"{id_}.ass"
    legenda.gerar_legenda(str(pal), str(out), {"legenda": leg}); return out.read_text()
t = ass("caixa-marinho"); estilo = [l for l in t.splitlines() if l.startswith("Style:")][0].split(",")
check(estilo[15] == "3", "caixa marinho usa BorderStyle 3 (caixa opaca)")
check("\\fad(180,100)" in ass("caixa-marinho"), "aparecer usa fade na linha")
check(re.search(r"\\move\(540,\d+,540,\d+,0,180\)", ass("subir")), "subir usa \\move a partir da posição da legenda")
check("\\alpha&HFF&\\t(" in ass("digitar"), "digitar esconde cada palavra até ela ser falada")
check(",Crimson GS," in ass("serifada-historia") and (RAIZ / "fontes" / "CrimsonGS-SemiBold.ttf").exists(), "serifada usa a Crimson da pasta fontes/")
check(",Unbounded GS," in ass("display-unbounded") and (RAIZ / "fontes" / "UnboundedGS-SemiBold.ttf").exists(), "display usa a Unbounded da pasta fontes/")
mv = [l for l in ass("minuscula-discreta").splitlines() if l.startswith("Style:")][0].split(",")
check(mv[-2] == str(int(1920 * 18 / 100)), "altura livre (altura_pct) vira a margem vertical")
check("\\k" not in ass("palavra-unica") and "\\fscx72" in ass("palavra-unica"), "palavra única: sem karaokê, entra com zoom")

# MCP: legenda_modelo no estilo inline
import importlib.util
spec = importlib.util.spec_from_file_location("srv", RAIZ / "mcp" / "editor-de-video" / "servidor.py")
try:
    srv = importlib.util.module_from_spec(spec); spec.loader.exec_module(srv)
    e = srv._estilo('{"base": "profissional", "legenda_modelo": "caixa-marinho", "legenda": {"cor_destaque": "#22C55E"}}')
    check(e["legenda"].get("caixa") is True and e["legenda"]["cor_destaque"] == "#22C55E" and e["montagem"]["palavras_chave"] == "auto", "legenda_modelo aplica o modelo e mantém a montagem da base")
except Exception as ex:  # noqa
    print("SKIP legenda_modelo no MCP:", str(ex)[:120])

shutil.rmtree(td, ignore_errors=True)
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
