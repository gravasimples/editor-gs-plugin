"""Testes isolados: criar/apagar fluxos e estilos pelo app e busca nas conversas (Paperclip por dublê, pastas temporárias)."""
import json, sys, tempfile, shutil
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.FLUXOS_DIR = tmp / "fluxos"; api.ESTILOS_DIR = tmp / "estilos"; api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    api.FLUXOS_DIR.mkdir(); api.ESTILOS_DIR.mkdir(); api.SAIDA.mkdir()
    shutil.copy(RAIZ / "estilos" / "padrao.json", api.ESTILOS_DIR / "padrao.json")
    issues = [{"id": "i1", "identifier": "GRA-1", "title": "Edite o vídeo da webcam", "description": "Corte dinâmico, legenda padrão <!-- gs-slug: s1 -->", "status": "done"},
              {"id": "i2", "identifier": "GRA-2", "title": "Carrossel sobre áudio", "description": "x", "status": "todo"}]
    async def pc_falso(metodo, url, **kw):
        return issues if url.endswith("/issues") else []
    api._pc = pc_falso
    api.INDICE.write_text(json.dumps({"i1": {"slug": "s1"}}))
    (api.SAIDA / "s1").mkdir(); (api.SAIDA / "s1" / "relatorio.md").write_text("# Relatório\nRemovido 68,9% por refações. ISO com confiança baixa.", encoding="utf-8")
    c = TestClient(api.app)

    # fluxos
    r = c.post("/api/gs/fluxos", data={"nome": "Reels do celular", "descricao": "Vídeo gravado no celular", "passos": "1. transcrever\n2. cortar"})
    check(r.status_code == 200 and r.json()["nome"] == "reels-do-celular" and (api.FLUXOS_DIR / "reels-do-celular.md").exists(), "fluxo criado em fluxos/<slug>.md")
    check("# Fluxo: Reels do celular" in r.json()["conteudo"] and "Passos para o Editor:" in r.json()["conteudo"], "fluxo com título e passos")
    check(c.post("/api/gs/fluxos", data={"nome": "Reels do celular", "passos": "x"}).status_code == 409, "fluxo repetido dá 409")
    check(c.post("/api/gs/fluxos", data={"nome": "reels-padrao", "passos": "x"}).status_code == 400, "fluxo fixo não é sobrescrito")
    check(c.delete("/api/gs/fluxos/reels-padrao").status_code == 400, "fluxo fixo não é apagado")
    check(c.delete("/api/gs/fluxos/reels-do-celular").status_code == 200 and not (api.FLUXOS_DIR / "reels-do-celular.md").exists(), "fluxo do app apagado")

    # estilos
    r = c.post("/api/gs/estilos", data={"nome": "Amarelo grande", "cor_destaque": "#ffd400", "tamanho_9x16": 90, "maiusculas": "sim", "zoom_por_frase": "sim"})
    j = r.json(); check(r.status_code == 200 and j["nome"] == "amarelo-grande" and j["legenda"]["cor_destaque"] == "#FFD400" and j["legenda"]["tamanho_9x16"] == 90 and j["legenda"]["tamanho_16x9"] == 67 and j["legenda"]["maiusculas"] is True and j["montagem"]["zoom_por_frase"] is True, f"estilo criado com cor, tamanho, maiúsculas e zoom ({r.status_code})")
    check(json.loads((api.ESTILOS_DIR / "padrao.json").read_text())["legenda"]["cor_destaque"] == "#F79615", "estilo base intocado")
    check(c.post("/api/gs/estilos", data={"nome": "x1", "cor_destaque": "laranja"}).status_code == 400, "cor inválida dá 400")
    check(c.post("/api/gs/estilos", data={"nome": "padrao"}).status_code == 400, "não sobrescreve o padrão")
    check(c.post("/api/gs/estilos", data={"nome": "Amarelo grande"}).status_code == 409, "estilo repetido dá 409")
    check(c.delete("/api/gs/estilos/padrao").status_code == 400 and c.delete("/api/gs/estilos/amarelo-grande").status_code == 200, "apagar: padrão protegido, criado apagado")

    # busca
    r = c.get("/api/gs/busca?q=webcam"); check(r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["codigo"] == "GRA-1" and r.json()[0]["onde"] == "título", "busca por título")
    r = c.get("/api/gs/busca?q=refacoes"); check(len(r.json()) == 1 and r.json()[0]["onde"] == "relatorio.md" and "refações" in r.json()[0]["trecho"], "busca sem acento acha no relatório")
    r = c.get("/api/gs/busca?q=gra-2"); check(len(r.json()) == 1 and r.json()[0]["codigo"] == "GRA-2", "busca por código")
    check(c.get("/api/gs/busca?q=a").json() == [], "termo curto devolve vazio")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
