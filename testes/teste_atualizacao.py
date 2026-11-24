"""Atualização automática do plugin e escolha da release com pacote (scripts/editor_gs.py, 12/11/2026).
Sem rede e sem claude: versão publicada, instalar e pastas_dados são substituídos por funções falsas; as "pastas do plugin" são temporárias.
Isolado (EDITOR_GS_HOME e EDITOR_GS_VENV em pasta temporária; nada de produção é lido ou tocado).
Rodar: ~/.venvs/editor-gs/Scripts/python.exe -I -X utf8 testes/teste_atualizacao.py"""
import importlib.util, io, json, os, sys, tempfile, time
from contextlib import redirect_stdout
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(RAIZ))
tmp = Path(tempfile.mkdtemp(prefix="atualizacao-"))
os.environ["EDITOR_GS_HOME"] = str(tmp / "home"); os.environ["EDITOR_GS_VENV"] = str(tmp / "venv"); os.environ["EDITOR_GS_PORTA"] = "3998"
for k in ("EDITOR_GS_SEM_ATUALIZAR", "EDITOR_GS_RAIZ_ANTERIOR"):
    os.environ.pop(k, None)
(tmp / "home").mkdir()
spec = importlib.util.spec_from_file_location("editor_gs", RAIZ / "scripts" / "editor_gs.py"); eg = importlib.util.module_from_spec(spec); spec.loader.exec_module(eg)

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def calado(f, *a, **k):
    buf = io.StringIO()
    with redirect_stdout(buf):
        r = f(*a, **k)
    return r, buf.getvalue()

# --- escolher_release
def rel(tag, com_zip, **extra):
    a = [{"name": "Instalar-Editor-GS.cmd", "browser_download_url": f"https://x/{tag}/cmd"}]
    if com_zip:
        a.append({"name": f"editor-gs-win64-{tag}.zip", "browser_download_url": f"https://x/{tag}/base.zip"})
    return {"tag_name": tag, "assets": a, **extra}
e = eg.escolher_release([rel("v1.2.3", False), rel("v1.2.2", False, draft=True), rel("v1.2.1", True)])
check(e["base"] == "https://x/v1.2.1/base.zip" and e["versao"] == "v1.2.1", f"release mais nova sem pacote é pulada: {e['versao']}")
e = eg.escolher_release([rel("v1.3.0", True, prerelease=True), rel("v1.2.4", True)])
check(e["versao"] == "v1.2.4", "pré-lançamento é pulado")
check(eg.escolher_release(rel("v1.2.1", True))["base"], "aceita uma release só (formato antigo)")
check(eg.escolher_release([])["base"] is None and eg.escolher_release([rel("v9", False)])["base"] is None, "sem pacote em nenhuma → base None")
check(eg.URL_RELEASE.endswith("/releases?per_page=20"), "consulta a lista de releases, não só a latest")

# --- versões e modo plugin
check(eg._tupla("1.2.10") > eg._tupla("1.2.9") and eg._tupla("v1.3.0") > eg._tupla("1.2.99") and eg._tupla("") == (), "comparação numérica de versão")
plug = tmp / "u" / ".claude" / "plugins" / "cache" / "editor-gs"
check(eg.modo_plugin(plug / "1.2.2") and not eg.modo_plugin(Path("C:/Users/x/projetos/editor-gs")), "modo plugin só dentro de .claude/plugins")
check(not eg.modo_plugin(), "este repositório (desenvolvimento) não é modo plugin")

def raiz_falsa(versao, pkg="v1", app="a1"):
    r = plug / versao
    (r / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (r / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "editor-gs", "version": versao}), encoding="utf-8")
    (r / "scripts").mkdir(exist_ok=True); (r / "scripts" / "editor_gs.py").write_text("# falso", encoding="utf-8")
    (r / "remotion").mkdir(exist_ok=True); (r / "remotion" / "package.json").write_text(pkg, encoding="utf-8")
    (r / "app" / "src").mkdir(parents=True, exist_ok=True); (r / "app" / "src" / "main.tsx").write_text(app, encoding="utf-8")
    (r / "app" / "package.json").write_text("{}", encoding="utf-8")
    (r / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    return r

velha = raiz_falsa("1.2.2")
(velha / "remotion" / "node_modules" / "remotion").mkdir(parents=True); (velha / "remotion" / "node_modules" / "remotion" / "index.js").write_text("x", encoding="utf-8")
(velha / "app" / "dist").mkdir(); (velha / "app" / "dist" / "index.html").write_text("velho", encoding="utf-8")
check(eg.versao_de(velha) == "1.2.2" and eg.versao_de(tmp / "nada") == "", "versão lida do plugin.json")

# --- registro da pasta e raiz_anterior
eg.RAIZ = velha
eg.registrar_raiz()
reg = json.loads((tmp / "home" / "estado" / "raiz.json").read_text(encoding="utf-8"))
check(reg["raiz"] == str(velha) and reg["versao"] == "1.2.2", "subir/instalar gravam a pasta e a versão")
check(eg.raiz_anterior() is None, "a própria pasta não conta como anterior")

# --- migração: Remotion igual é movido; app que mudou não
nova = raiz_falsa("1.2.3", pkg="v1", app="a2")
eg.RAIZ = nova
check(eg.raiz_anterior() == velha, "versão nova enxerga a anterior pelo registro")
mov, saida = calado(eg.migrar_de_raiz_anterior, velha)
check(mov == ["remotion/node_modules"] and (nova / "remotion" / "node_modules" / "remotion" / "index.js").exists() and not (velha / "remotion" / "node_modules").exists(), f"Remotion sem mudança vai para a versão nova: {mov}")
check(not (nova / "app" / "dist").exists() and "app/dist: mudou" in saida, "app que mudou não reaproveita a tela velha")
(nova / "app" / "dist").mkdir(); (nova / "app" / "dist" / "index.html").write_text("novo", encoding="utf-8")
mov2, _ = calado(eg.migrar_de_raiz_anterior, velha)
check(mov2 == [] and (nova / "app" / "dist" / "index.html").read_text(encoding="utf-8") == "novo", "nunca sobrescreve o que já existe na versão nova")
outra = raiz_falsa("1.2.4", pkg="v2", app="a3")
(velha / "remotion" / "node_modules").mkdir(parents=True)
eg.RAIZ = outra
mov3, saida3 = calado(eg.migrar_de_raiz_anterior, velha)
check(mov3 == [] and "remotion/node_modules: mudou" in saida3, "package.json do Remotion mudou → refaz em vez de mover")

# --- pos_atualizacao: sem mudança de bibliotecas não reinstala; com mudança, instala
chamadas = []
eg.instalar = lambda: (chamadas.append("instalar"), 0)[1]
eg.pastas_dados = lambda: chamadas.append("pastas_dados")
(tmp / "venv" / "Scripts").mkdir(parents=True); (tmp / "venv" / "Scripts" / "python.exe").write_bytes(b"x")
(tmp / "venv" / "bin").mkdir(); (tmp / "venv" / "bin" / "python").write_bytes(b"x")
eg.RAIZ = nova
os.environ["EDITOR_GS_RAIZ_ANTERIOR"] = str(velha)
r, _ = calado(eg.pos_atualizacao)
check(r == 0 and chamadas == ["pastas_dados"], f"tudo reaproveitado: só reescreve o .mcp.json do workspace ({chamadas})")
check(json.loads((tmp / "home" / "estado" / "raiz.json").read_text(encoding="utf-8"))["versao"] == "1.2.3", "registro passa para a versão nova")
chamadas.clear(); (nova / "requirements.txt").write_text("fastapi\nnova-lib\n", encoding="utf-8")
r, saida = calado(eg.pos_atualizacao)
check(chamadas == ["instalar"] and "bibliotecas do motor mudaram" in saida, "requirements mudou → roda a instalação (só o que falta)")
os.environ.pop("EDITOR_GS_RAIZ_ANTERIOR")

# --- atualizar: guardas (sem rede, sem claude)
eg.RAIZ = RAIZ
check(calado(eg.atualizar, auto=True, buscar_versao=lambda: "9.9.9")[0] is None, "pasta de desenvolvimento nunca se atualiza")
eg.RAIZ = nova
marca = tmp / "home" / "estado" / "ultima-checagem-versao"
check(calado(eg.atualizar, auto=True, buscar_versao=lambda: "1.2.3")[0] is None and marca.exists(), "mesma versão → nada; marca a checagem")
def proibido(): raise AssertionError("não devia consultar")
check(calado(eg.atualizar, auto=True, buscar_versao=proibido)[0] is None, "checou há pouco → não consulta de novo (6 h)")
os.utime(marca, (time.time() - 7 * 3600, time.time() - 7 * 3600))
def sem_rede(): raise OSError("sem rede")
check(calado(eg.atualizar, auto=True, buscar_versao=sem_rede)[0] is None, "sem rede → segue com a versão atual")
eg._claude = lambda: None
r, saida = calado(eg.atualizar, auto=False, buscar_versao=lambda: "1.2.9")
check(r is None and "1.2.3 → 1.2.9" in saida and "não achei o claude" in saida, "versão nova sem claude → avisa e segue")
os.environ["EDITOR_GS_SEM_ATUALIZAR"] = "1"
check(calado(eg.atualizar, auto=False, buscar_versao=proibido)[0] is None, "EDITOR_GS_SEM_ATUALIZAR=1 desliga")
os.environ.pop("EDITOR_GS_SEM_ATUALIZAR")

print("\nTUDO OK" if not FALHAS else f"\n{len(FALHAS)} FALHA(S)")
sys.exit(1 if FALHAS else 0)
