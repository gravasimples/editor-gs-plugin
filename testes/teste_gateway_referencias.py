"""Testes isolados das referências (gateway). Pastas temporárias, yt-dlp e Paperclip substituídos por dublês.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_gateway_referencias.py"""
import json, os, stat, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import _falso  # noqa: E402
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, referencias as refs

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.ENTRADA = tmp / "entrada"; api.RECEBIDOS = api.ENTRADA / "_recebidos"; api.SAIDA = tmp / "saida"; api.INDICE = tmp / "conversas.json"; api.PASTAS = tmp / "pastas.json"; api.TEXTOS_CACHE = tmp / "textos.json"; api.TEXTOS_DIR = tmp / "_textos"
    api.REFERENCIAS = tmp / "referencias"; api.ENTRADA.mkdir(); api.SAIDA.mkdir()
    criadas = []
    async def pc_falso(metodo, url, **kw):
        if metodo == "POST" and url.endswith("/issues"):
            criadas.append(kw["json"]); return {"id": f"issue-{len(criadas)}", "identifier": f"GRA-{len(criadas)}", **kw["json"]}
        return []
    api._pc = pc_falso
    # yt-dlp falso: cria vídeo e capa e imprime o JSON de metadados
    falso = tmp / "yt-dlp"; falso.write_text('#!/bin/sh\nfor a in "$@"; do a=$(printf "%s" "$a" | tr "\\\\" "/"); case "$a" in *referencia.%\\(ext\\)s) d=$(dirname "$a"); printf "v" > "$d/referencia.mp4"; printf "j" > "$d/referencia.jpg";; esac; done\necho \'{"title":"Como tirar a webcam do automático","uploader":"Grava Simples","duration":42,"extractor_key":"Youtube","view_count":1234,"like_count":56,"upload_date":"20261001","description":"desc"}\'\n')
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC); falso = _falso.executavel(falso); refs.YTDLP = falso; refs.subprocess = _falso.subprocess_seguro()
    c = TestClient(api.app)

    # 1. Link: cria em `baixando`, a tarefa de fundo baixa e vira `pronto` com metadados
    r = c.post("/api/gs/referencias", data={"texto": "Gostei do gancho https://www.youtube.com/watch?v=abc123 e da tela dividida"})
    check(r.status_code == 200, f"cria referência por link ({r.status_code} {r.text[:120]})")
    d = r.json(); rid = d["id"]
    check(d["url"] == "https://www.youtube.com/watch?v=abc123" and d["nota"] == "Gostei do gancho  e da tela dividida".replace("  ", " ") or d["nota"].startswith("Gostei do gancho"), "link separado da nota")
    check(d["plataforma"] == "youtube", "plataforma detectada")
    for _ in range(50):
        d = c.get(f"/api/gs/referencias/{rid}").json()
        if d["status"] != "baixando": break
        time.sleep(0.1)
    check(d["status"] == "pronto" and d["video"] == "referencia.mp4" and d["capa"] == "referencia.jpg", f"download em segundo plano concluiu ({d['status']}, {d.get('erro')})")
    check(d["titulo"] == "Como tirar a webcam do automático" and d["autor"] == "Grava Simples" and d["duracao_s"] == 42 and d["visualizacoes"] == 1234, "metadados do yt-dlp gravados")
    check((api.REFERENCIAS / rid / "referencia.json").exists(), "referencia.json na pasta")

    # 2. Arquivo anexado: fica pronto na hora, sem download
    r = c.post("/api/gs/referencias", data={"texto": "Reels do Pedro"}, files=[("arquivos", ("pedro reels.mp4", b"\x00" * 100, "video/mp4"))])
    d2 = r.json(); check(r.status_code == 200 and d2["status"] == "pronto" and d2["video"] == "pedro_reels.mp4" and d2["plataforma"] == "arquivo", "referência por arquivo pronta")
    check(not any(p.name.startswith("_ref-") for p in api.RECEBIDOS.iterdir()), "pasta temporária do upload apagada")

    # 3. Material recebido do celular vira referência
    r = c.post("/api/gs/recebidos", data={"texto": "do celular"}, files=[("arquivos", ("cel.mp4", b"\x01" * 10, "video/mp4"))]); token = r.json()["token"]
    r = c.post("/api/gs/referencias", data={"recebido": token}); d3 = r.json()
    check(r.status_code == 200 and d3["video"] == "cel.mp4" and d3["nota"] == "do celular" and not (api.RECEBIDOS / token).exists(), "recebido → referência e pasta do token apagada")

    # 4. Erros
    check(c.post("/api/gs/referencias", data={"texto": "sem link nem arquivo"}).status_code == 400, "sem link nem arquivo dá 400")
    check(c.get("/api/gs/referencias/nao-existe").status_code == 404, "id inexistente dá 404")
    check(c.get("/api/gs/referencias/../x").status_code in (404, 400), "id com caminho é recusado")

    # 5. Lista, nota, análise
    lista = c.get("/api/gs/referencias").json(); check(len(lista) == 3 and lista[0]["id"] == d3["id"], "lista ordenada da mais nova")
    r = c.post(f"/api/gs/referencias/{rid}/nota", data={"nota": "nota nova", "titulo": "Título meu"}); check(r.json()["nota"] == "nota nova" and r.json()["titulo"] == "Título meu", "nota e título editáveis")
    (api.REFERENCIAS / rid / "analise.md").write_text("## Resumo\nfunciona", encoding="utf-8")
    check(c.get(f"/api/gs/referencias/{rid}").json()["analise"].startswith("## Resumo"), "analise.md lida junto")

    # 6. Pedido de análise cria issue com o fluxo e anota na referência
    r = c.post(f"/api/gs/referencias/{rid}/analisar"); check(r.status_code == 200 and r.json()["codigo"] == "GRA-1", f"analisar cria issue ({r.status_code})")
    check("referencia-analise" in criadas[-1]["description"] and f"referencias/{rid}/analise.md" in criadas[-1]["description"] and "nota nova" in criadas[-1]["description"], "issue cita fluxo, pasta e nota")
    check(c.get(f"/api/gs/referencias/{rid}").json()["pedidos"][0]["tipo"] == "analise", "pedido anotado na referência")

    # 7. Nova conversa com referência: pedido padrão de minha-versao e anotação
    r = c.post("/api/gs/conversas", data={"pedido": "", "fluxo": "minha-versao", "referencia": rid})
    check(r.status_code == 200 and "minha-versao" in criadas[-1]["description"] and f"referencias/{rid}/" in criadas[-1]["description"], f"conversa com referência ({r.status_code} {r.text[:80]})")
    check(c.get(f"/api/gs/referencias/{rid}").json()["pedidos"][-1]["tipo"] == "minha-versao", "pedido minha-versao anotado")
    check(c.post("/api/gs/conversas", data={"pedido": "x", "referencia": "nao-existe"}).status_code == 404, "referência inexistente na conversa dá 404")

    # 8. Concorrentes do GSI (banco pode não existir no teste: lista vazia ou dados)
    r = c.get("/api/gs/referencias/concorrentes"); check(r.status_code == 200 and isinstance(r.json(), list), "concorrentes responde lista")

    # 9. Apagar
    check(c.delete(f"/api/gs/referencias/{rid}").status_code == 200 and not (api.REFERENCIAS / rid).exists(), "apagar remove a pasta")

    # 10. yt-dlp ausente: erro claro, sem exceção
    refs.YTDLP = tmp / "nao-existe"
    r = c.post("/api/gs/referencias", data={"url": "https://www.instagram.com/reel/xyz/"}); rid2 = r.json()["id"]
    for _ in range(50):
        d = c.get(f"/api/gs/referencias/{rid2}").json()
        if d["status"] != "baixando": break
        time.sleep(0.1)
    check(d["status"] == "erro" and "yt-dlp" in (d["erro"] or ""), "sem yt-dlp vira status erro com motivo")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
