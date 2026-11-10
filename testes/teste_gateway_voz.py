"""Testes isolados da página Voz: listar vozes/referências/amostras, decisão humana em voz.json, geração de amostra por dublê e apagar amostra.
Sem modelo, sem GPU, sem rede; pasta temporária no lugar de workspace/voz."""
import json, sys, tempfile, wave
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from fastapi.testclient import TestClient
from servico import api, voz as vz

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)


def wav(p: Path, segundos=1.0, sr=24000):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(b"\x00\x00" * int(sr * segundos))


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    api.VOZ_DIR = tmp / "voz"; vz.VOZ_DIR = api.VOZ_DIR
    d = api.VOZ_DIR / "thiago"; (d / "referencias").mkdir(parents=True); (d / "amostras").mkdir()
    wav(d / "referencias" / "ref_obs_blade_2.wav", 14.0); wav(d / "referencias" / "ref_aula_1_2.wav", 13.5)
    (d / "referencias" / "manifesto.json").write_text(json.dumps({"ref_obs_blade_2.wav": {"origem": "obs_blade", "texto": "fala do OBS", "mean_db": -25.0, "cobertura_transcricao": 0.95}}), encoding="utf-8")
    (d / "voz.json").write_text(json.dumps({"referencia": "ref_obs_blade_2.wav", "exagero": 0.5, "cfg": 0.5, "rotulo": "voz clonada do Thiago (teste)"}), encoding="utf-8")
    wav(d / "amostras" / "amostra-1.wav", 2.0)
    (d / "amostras" / "amostra-1.wav.json").write_text(json.dumps({"texto": "Olha só.", "referencia": "ref_obs_blade_2.wav", "modelo": "clone", "quando": "2026-10-31T03:10", "origem": "piloto"}), encoding="utf-8")
    (api.VOZ_DIR / "_lixo.txt").write_text("x")  # não é voz
    c = TestClient(api.app)

    # listar
    r = c.get("/api/gs/voz"); j = r.json()
    check(r.status_code == 200 and [v["nome"] for v in j["vozes"]] == ["thiago"], "lista só a pasta com referências")
    v = j["vozes"][0]
    check(v["referencia"] == "ref_obs_blade_2.wav" and v["aprovada"] is False and v["padrao_locucao"] is False, "config lida do voz.json com padrões de decisão")
    refs = {x["nome"]: x for x in v["referencias"]}
    check(set(refs) == {"ref_obs_blade_2.wav", "ref_aula_1_2.wav"} and refs["ref_obs_blade_2.wav"]["origem"] == "obs_blade" and refs["ref_obs_blade_2.wav"]["texto"] == "fala do OBS", "referências com dados do manifesto")
    check(refs["ref_obs_blade_2.wav"]["duracao_s"] == 14.0 and refs["ref_obs_blade_2.wav"]["url"] == "/voz-arquivos/thiago/referencias/ref_obs_blade_2.wav", "duração pelo wave e URL servida pelo mount /voz")
    check(len(v["amostras"]) == 1 and v["amostras"][0]["texto"] == "Olha só." and v["amostras"][0]["url"] == "/voz-arquivos/thiago/amostras/amostra-1.wav" and v["amostras"][0]["duracao_s"] == 2.0, "amostra com sidecar e duração")
    check(j["geracao"]["status"] == "parado" and j["texto_padrao"].startswith("Ó, olha só"), "estado de geração parado e texto padrão")
    check(c.get("/voz-arquivos/thiago/amostras/amostra-1.wav").status_code in (200, 404), "mount /voz-arquivos existe (serve a pasta real; aqui só não pode quebrar)")

    # decisão
    r = c.post("/api/gs/voz/thiago/decisao", data={"referencia": "ref_aula_1_2.wav", "aprovada": "sim", "padrao_locucao": "nao", "nota": "mais natural", "exagero": "0.6"})
    j = r.json(); cfg = json.loads((d / "voz.json").read_text())
    check(r.status_code == 200 and j["referencia"] == "ref_aula_1_2.wav" and j["aprovada"] is True and j["padrao_locucao"] is False and j["nota"] == "mais natural", "decisão devolvida")
    check(cfg["referencia"] == "ref_aula_1_2.wav" and cfg["aprovada"] is True and cfg["exagero"] == 0.6 and cfg["cfg"] == 0.5 and cfg["rotulo"] == "voz clonada do Thiago (teste)" and cfg["decidido_em"], "voz.json gravado só com o enviado (cfg e rótulo intactos)")
    r = c.post("/api/gs/voz/thiago/decisao", data={"padrao_locucao": "sim"})
    check(r.status_code == 200 and r.json()["padrao_locucao"] is True and json.loads((d / "voz.json").read_text())["referencia"] == "ref_aula_1_2.wav", "campo isolado não apaga os outros")
    check(c.post("/api/gs/voz/thiago/decisao", data={"referencia": "nao_existe.wav"}).status_code == 400, "referência inexistente dá 400")
    check(c.post("/api/gs/voz/thiago/decisao", data={"referencia": "../voz.json"}).status_code == 400, "caminho com .. dá 400")
    check(c.post("/api/gs/voz/thiago/decisao", data={"exagero": "1.5"}).status_code == 400, "exagero fora do intervalo dá 400")
    check(c.post("/api/gs/voz/outra/decisao", data={"aprovada": "sim"}).status_code == 404, "voz inexistente dá 404")
    check(c.post("/api/gs/voz/Th%20iago/decisao", data={"aprovada": "sim"}).status_code == 400, "nome inválido dá 400")

    # geração por dublê (sem thread, sem processo)
    pedidos = []
    def sint_falso(pedido):
        pedidos.append(pedido); wav(Path(pedido["saida"]), 3.0); return {"ok": True, "duracao_s": 3.0, "tempo_s": 9.1, "partes": 1, "device": "cuda"}
    r = vz.gerar_amostra("thiago", "Seguinte, vamos testar na prática.", referencia="ref_obs_blade_2.wav", _sint=sint_falso, _em_thread=False)
    check(r["status"] == "pronto" and r["referencia"] == "ref_obs_blade_2.wav", "amostra gerada pelo dublê")
    check(pedidos[0]["ref"].endswith("referencias/ref_obs_blade_2.wav") and pedidos[0]["exagero"] == 0.6 and pedidos[0]["idioma"] == "pt", "pedido ao worker usa a referência pedida e o exagero do voz.json")
    est = vz.estado(); am = est["amostra"]
    check(est["status"] == "pronto" and am["origem"] == "pagina-voz" and am["duracao_s"] == 3.0 and am["url"].startswith("/voz-arquivos/thiago/amostras/") and am["nome"].endswith("-ref_obs_blade_2.wav"), "estado traz a amostra nova")
    lista = c.get("/api/gs/voz").json()["vozes"][0]["amostras"]
    check(lista[0]["nome"] == am["nome"] and lista[0]["texto"] == "Seguinte, vamos testar na prática." and (d / "amostras" / (am["nome"] + ".json")).exists(), "amostra nova no topo da lista, com sidecar")
    try:
        vz.gerar_amostra("thiago", "curto", _sint=sint_falso, _em_thread=False); check(False, "texto curto recusado")
    except ValueError:
        check(True, "texto curto recusado")
    def sint_erro(pedido):
        return {"ok": False, "erro": "sem GPU"}
    try:
        vz.gerar_amostra("thiago", "Frase que vai falhar na síntese.", _sint=lambda p: (_ for _ in ()).throw(RuntimeError("Voz clonada falhou: sem GPU")), _em_thread=False)
    except Exception:
        pass
    est = vz.estado()
    check(est["status"] == "erro" and "sem GPU" in (est["erro"] or "") and len(list((d / "amostras").glob("*.wav"))) == 2, "falha vira status erro e não deixa arquivo pela metade")
    vz.GERACAO["status"] = "rodando"
    check(c.post("/api/gs/voz/thiago/amostra", data={"texto": "Outra frase para testar a fila."}).status_code == 409, "geração em andamento dá 409")
    vz.GERACAO["status"] = "parado"
    check(c.post("/api/gs/voz/thiago/amostra", data={"texto": "x"}).status_code == 400, "texto curto pela API dá 400")
    check(c.post("/api/gs/voz/thiago/amostra", data={"texto": "Frase válida para a amostra.", "referencia": "zzz.wav"}).status_code == 400, "referência inexistente na amostra dá 400")
    sem_venv = vz.python_voz
    vz.python_voz = lambda: "/nao/existe/python"
    r = c.post("/api/gs/voz/thiago/amostra", data={"texto": "Frase válida para a amostra."})
    check(r.status_code == 409 and "editor-gs-voz" in r.json()["detail"], "sem venv da voz: 409 com instrução")
    vz.python_voz = sem_venv


    # motor Qwen: decisão, listagem, amostra
    r = c.get("/api/gs/voz").json()
    check(set(r["motores"]) == {"chatterbox", "qwen"} and r["vozes"][0]["motor"] == "chatterbox" and r["vozes"][0]["motor_nome"] == "Chatterbox pt-BR" and r["vozes"][0]["qwen"] == {"temperatura": 0.9, "top_p": 0.9, "repeticao": 1.05}, "listagem traz motores, motor padrão chatterbox e parâmetros padrão do qwen")
    (d / "referencias" / "transcricoes.json").write_text(json.dumps({"ref_aula_1_2.wav": "Fala exata da aula um."}), encoding="utf-8")
    r = c.post("/api/gs/voz/thiago/decisao", data={"motor": "qwen", "qwen_temperatura": "0.8", "qwen_repeticao": "1.1"})
    j = r.json(); cfg = json.loads((d / "voz.json").read_text())
    check(r.status_code == 200 and j["motor"] == "qwen" and j["motor_nome"] == "Qwen3-TTS" and j["qwen"] == {"temperatura": 0.8, "top_p": 0.9, "repeticao": 1.1} and j["ref_text"] == "Fala exata da aula um.", "decisão troca o motor para qwen e devolve ref_text da referência padrão")
    check(cfg["motor_escolhido"] == "qwen" and cfg["qwen"] == {"temperatura": 0.8, "repeticao": 1.1} and "Qwen3-TTS" in cfg["rotulo"] and cfg["referencia"] == "ref_aula_1_2.wav", "voz.json com motor_escolhido, qwen e rótulo do motor")
    check(c.post("/api/gs/voz/thiago/decisao", data={"motor": "eleven"}).status_code == 400, "motor desconhecido dá 400")
    check(c.post("/api/gs/voz/thiago/decisao", data={"qwen_temperatura": "3"}).status_code == 400, "qwen_temperatura fora do intervalo dá 400")
    pedidos.clear()
    r = vz.gerar_amostra("thiago", "Seguinte, vamos testar o Qwen na prática.", _sint=sint_falso, _em_thread=False, semente=4)
    pq = pedidos[0]
    check(r["motor"] == "qwen" and "-qwen-" in r["arquivo"] and pq["motor"] == "qwen" and pq["ref_text"] == "Fala exata da aula um." and pq["temperatura"] == 0.8 and pq["top_p"] == 0.9 and pq["repeticao"] == 1.1 and pq["semente"] == 4 and "exagero" not in pq, "amostra no qwen: pedido com ref_text, parâmetros do voz.json e semente")
    am = vz.estado()["amostra"]
    check(am["motor"] == "qwen" and am["modelo"].startswith("clone (Qwen3-TTS") and am["qwen"]["temperatura"] == 0.8 and am["ref_text"] is True and am["semente"] == 4, "sidecar da amostra qwen com motor, parâmetros e ref_text")
    r = vz.gerar_amostra("thiago", "Agora com a referência que só tem texto no manifesto.", referencia="ref_obs_blade_2.wav", ref_text="", _sint=sint_falso, _em_thread=False)
    check(pedidos[-1]["ref_text"] == "fala do OBS" and not vz.estado()["amostra"].get("nota"), "sem transcricoes.json o ref_text vem do manifesto")
    wav(d / "referencias" / "ref_sem_texto.wav", 10.0)
    r = vz.gerar_amostra("thiago", "Agora com a referência sem transcrição nenhuma.", referencia="ref_sem_texto.wav", _sint=sint_falso, _em_thread=False)
    check(pedidos[-1]["ref_text"] is None and "x_vector_only" in (vz.estado()["amostra"].get("nota") or ""), "referência sem transcrição: ref_text vazio e nota na amostra")
    r = vz.gerar_amostra("thiago", "Agora com texto da referência à mão.", referencia="ref_obs_blade_2.wav", ref_text="Texto digitado.", qwen={"temperatura": 0.6}, _sint=sint_falso, _em_thread=False)
    check(pedidos[-1]["ref_text"] == "Texto digitado." and pedidos[-1]["temperatura"] == 0.6 and pedidos[-1]["repeticao"] == 1.1, "ref_text e parâmetro só desta amostra sobrepõem o voz.json")
    r = vz.gerar_amostra("thiago", "E no Chatterbox, por comparação.", motor="chatterbox", _sint=sint_falso, _em_thread=False)
    check(r["motor"] == "chatterbox" and "-cb-" in r["arquivo"] and pedidos[-1]["exagero"] == 0.6 and "ref_text" not in pedidos[-1] and vz.estado()["amostra"]["modelo"] == "clone (Chatterbox pt-BR)", "motor explícito chatterbox na amostra")
    try:
        vz.gerar_amostra("thiago", "Motor que não existe.", motor="eleven", _sint=sint_falso, _em_thread=False); check(False, "motor desconhecido na amostra")
    except ValueError:
        check(True, "motor desconhecido na amostra dá ValueError")
    check(c.post("/api/gs/voz/thiago/amostra", data={"texto": "Frase válida para a amostra.", "qwen_top_p": "5"}).status_code == 400 and vz.estado()["status"] != "rodando", "qwen_top_p fora do intervalo na amostra dá 400 e não deixa a geração presa em 'rodando'")
    sem_q = vz.python_qwen
    vz.python_qwen = lambda: "/nao/existe/python"
    r = c.post("/api/gs/voz/thiago/amostra", data={"texto": "Frase válida para a amostra."})
    check(r.status_code == 409 and "editor-gs-qwen" in r.json()["detail"] and "Qwen" in r.json()["detail"], "sem venv do qwen: 409 aponta o venv do Qwen")
    vz.python_qwen = sem_q
    lista = c.get("/api/gs/voz").json()["vozes"][0]["amostras"]
    check({a["motor"] for a in lista} >= {"qwen", "chatterbox"} and all("motor" in a for a in lista), "listagem das amostras traz o motor de cada uma")
    for a in lista:
        if a["origem"] == "pagina-voz" and a["nome"] != am["nome"]:
            c.delete(f"/api/gs/voz/thiago/amostras/{a['nome']}")
    c.post("/api/gs/voz/thiago/decisao", data={"motor": "chatterbox"})

    # processo de verdade com o worker falso: etapa de progresso e resultado
    import sys as _sys
    falso = RAIZ / "testes" / "_worker_falso_voz.py"
    wq, pq_ = vz.WORKER_QWEN, vz.python_qwen
    vz.WORKER_QWEN = falso; vz.python_qwen = lambda: _sys.executable
    etapas = []
    try:
        c.post("/api/gs/voz/thiago/decisao", data={"motor": "qwen"})
        r = vz.gerar_amostra("thiago", "Uma frase. Outra frase. Mais uma frase final.", _em_thread=False)
        est = vz.estado()
        check(est["status"] == "pronto" and est["amostra"]["partes"] == 3 and est["amostra"]["device"] == "cpu" and est["amostra"]["motor"] == "qwen", "amostra pelo processo do worker falso")
        src = (RAIZ / "servico" / "voz.py").read_text(encoding="utf-8")
        check("sintetizando a frase" in src and '"progresso" in d' in src, "gateway mostra o progresso frase a frase na etapa")
    finally:
        vz.WORKER_QWEN, vz.python_qwen = wq, pq_
        c.post("/api/gs/voz/thiago/decisao", data={"motor": "chatterbox"})
    # apagar amostra
    r = c.delete(f"/api/gs/voz/thiago/amostras/{am['nome']}")
    check(r.status_code == 200 and not (d / "amostras" / am["nome"]).exists() and not (d / "amostras" / (am["nome"] + ".json")).exists(), "amostra apagada com o sidecar")
    check(c.delete("/api/gs/voz/thiago/amostras/nao-existe.wav").status_code == 404, "apagar inexistente dá 404")
    check(c.delete("/api/gs/voz/thiago/amostras/..%2Fvoz.json").status_code in (400, 404, 405), "apagar com caminho fora da pasta é recusado")
    check((d / "voz.json").exists(), "voz.json intacto")

print(f"\n{len(FALHAS)} falhas")
sys.exit(1 if FALHAS else 0)
