"""Pacote pré-montado do instalador Windows (scripts/editor_gs.py): escolha do asset na release, verificação do VERSAO.txt,
fallback sem pacote, EDITOR_GS_SEM_PACOTE e EDITOR_GS_PACOTE_URL. Sem rede: download e JSON da release são substituídos por funções falsas.
Isolado (EDITOR_GS_HOME e EDITOR_GS_VENV em pasta temporária; nada de produção é lido ou tocado).
Rodar: ~/.venvs/editor-gs/Scripts/python.exe -I -X utf8 testes/teste_pacote.py"""
import importlib.util, io, os, sys, tempfile, zipfile
from contextlib import redirect_stdout
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(RAIZ))
tmp = Path(tempfile.mkdtemp(prefix="pacote-"))
os.environ["EDITOR_GS_HOME"] = str(tmp / "home"); os.environ["EDITOR_GS_VENV"] = str(tmp / "venv"); os.environ["EDITOR_GS_PORTA"] = "3999"
os.environ.pop("EDITOR_GS_SEM_PACOTE", None); os.environ.pop("EDITOR_GS_PACOTE_URL", None)
(tmp / "home").mkdir()
spec = importlib.util.spec_from_file_location("editor_gs", RAIZ / "scripts" / "editor_gs.py"); eg = importlib.util.module_from_spec(spec); spec.loader.exec_module(eg)

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

# --- escolher_asset
rel = {"tag_name": "v1.2.1", "assets": [
    {"name": "instalar-editor-gs.ps1", "browser_download_url": "https://x/ps1"},
    {"name": "editor-gs-win64-cuda-1.2.1.zip", "browser_download_url": "https://x/cuda.zip"},
    {"name": "editor-gs-win64-1.2.1.zip", "browser_download_url": "https://x/base.zip"},
    {"name": "editor-gs-win64-1.2.1.zip.sha256", "browser_download_url": "https://x/sha"}]}
e = eg.escolher_asset(rel)
check(e["base"] == "https://x/base.zip" and e["nome"] == "editor-gs-win64-1.2.1.zip", f"asset base escolhido: {e}")
check(e["cuda"] == "https://x/cuda.zip" and e["versao"] == "v1.2.1", "asset cuda e tag")
e2 = eg.escolher_asset({"tag_name": "v9", "assets": [{"name": "editor-gs-linux-9.tar.gz", "browser_download_url": "https://x/l"}]})
check(e2["base"] is None and e2["cuda"] is None, "release sem zip Windows → base None")
check(eg.escolher_asset({})["base"] is None and eg.escolher_asset(None)["base"] is None, "release vazia/None não quebra")

# --- verificar_pacote
p = tmp / "p1"; (p / "python").mkdir(parents=True); (p / "python" / "python.exe").write_bytes(b"x")
check(not eg.verificar_pacote(p), "sem VERSAO.txt → inválido")
(p / "VERSAO.txt").write_text("data=hoje\n", encoding="utf-8")
check(not eg.verificar_pacote(p), "VERSAO.txt sem versao= → inválido")
(p / "VERSAO.txt").write_text("versao=1.2.1\ndata=hoje\n", encoding="utf-8")
check(eg.verificar_pacote(p), "VERSAO.txt com versao= e python.exe → válido")
check(not eg.verificar_pacote(tmp / "nao-existe"), "pasta inexistente → inválido")
p2 = tmp / "p2"; p2.mkdir(); (p2 / "VERSAO.txt").write_text("versao=1\n", encoding="utf-8")
check(not eg.verificar_pacote(p2), "VERSAO.txt sem python\\ → inválido")

# --- obter_pacote: funções falsas de rede
def zip_falso(com_versao: bool):
    def baixar(url, destino, rotulo):
        destino.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destino, "w") as z:
            z.writestr("editor-gs-win64-1.2.1/python/python.exe", "x")
            z.writestr("editor-gs-win64-1.2.1/node/node.exe", "x")
            if com_versao:
                z.writestr("editor-gs-win64-1.2.1/VERSAO.txt", "versao=1.2.1\ncommit=abc\n")
        return destino
    return baixar
chamadas = []
def json_ok(url): chamadas.append(url); return rel
def json_falha(url): raise OSError("sem rede")
def json_vazio(url): return {"tag_name": "v0", "assets": []}
home = tmp / "home"

def rodar(**k):
    buf = io.StringIO()
    with redirect_stdout(buf):
        r = eg.obter_pacote(home, **k)
    return r, buf.getvalue()

r, saida = rodar(buscar_json=json_ok, baixar=zip_falso(True))
check(r and r["pasta"] == home / "pacote" and r["origem"] == "release" and r["cuda"] == "https://x/cuda.zip", f"release com pacote → extraído: {r}")
check((home / "pacote" / "VERSAO.txt").is_file() and (home / "pacote" / "node" / "node.exe").is_file(), "pasta raiz do zip removida (conteúdo direto em pacote/)")
check(not list((home / "_downloads").glob("*.zip")), "zip apagado depois de extrair")
check(chamadas == [eg.URL_RELEASE], "consultou as releases do repositório público")
r2, saida2 = rodar(buscar_json=json_falha, baixar=zip_falso(True))
check(r2 and r2["origem"] == "ja_extraido" and "já extraído" in saida2, "segunda chamada reaproveita o pacote sem rede")
import shutil; shutil.rmtree(home / "pacote")
r3, saida3 = rodar(buscar_json=json_ok, baixar=zip_falso(False))
check(r3 is None and not (home / "pacote").exists() and "VERSAO.txt" in saida3, "zip sem VERSAO.txt → None e pasta limpa")
r4, saida4 = rodar(buscar_json=json_falha, baixar=zip_falso(True))
check(r4 is None and "caminho antigo" in saida4, "sem rede → None sem exceção")
r5, _ = rodar(buscar_json=json_vazio, baixar=zip_falso(True))
check(r5 is None, "release sem asset Windows → None")
def baixar_falha(url, destino, rotulo): raise OSError("download caiu")
r6, saida6 = rodar(buscar_json=json_ok, baixar=baixar_falha)
check(r6 is None and "download caiu" in saida6, "download falha → None com motivo no log")
os.environ["EDITOR_GS_SEM_PACOTE"] = "1"
def json_proibido(url): raise AssertionError("não devia consultar a rede")
r7, saida7 = rodar(buscar_json=json_proibido, baixar=baixar_falha)
check(r7 is None and "EDITOR_GS_SEM_PACOTE" in saida7, "EDITOR_GS_SEM_PACOTE=1 desliga sem tocar na rede")
os.environ.pop("EDITOR_GS_SEM_PACOTE")
os.environ["EDITOR_GS_PACOTE_URL"] = "https://meu.servidor/editor-gs-win64-local.zip?x=1"
urls = []
def baixar_url(url, destino, rotulo): urls.append((url, destino.name)); return zip_falso(True)(url, destino, rotulo)
r8, _ = rodar(buscar_json=json_proibido, baixar=baixar_url)
check(r8 and r8["origem"] == "url" and urls == [("https://meu.servidor/editor-gs-win64-local.zip?x=1", "editor-gs-win64-local.zip")], f"EDITOR_GS_PACOTE_URL sobrepõe a release: {urls}")
os.environ.pop("EDITOR_GS_PACOTE_URL")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
