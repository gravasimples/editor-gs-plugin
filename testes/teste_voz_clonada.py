"""Testes isolados de voz_clonada.py SEM modelo e SEM rede: o processo de síntese é trocado por um dublê (_pedir) que grava um tom com ffmpeg,
e os tempos por palavra por um dublê (_palavras). A pasta de vozes é temporária (EDITOR_GS_VOZ_DIR). Nunca toca workspace/voz real."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory(prefix="editor-gs-vozclon-", ignore_cleanup_errors=True) as tmp:
    tmp = Path(tmp); os.chdir(tmp)
    os.environ["EDITOR_GS_VOZ_DIR"] = str(tmp / "vozes")
    os.environ["EDITOR_GS_VOZ_PYTHON"] = str(tmp / "nao-existe" / "python")
    from editor_video import voz, voz_clonada
    from editor_video.util import ErroFerramenta, info_midia, FFMPEG

    # sem pasta: nenhuma voz
    check(voz_clonada.listar() == {} and voz_clonada.nome_clonado("thiago") is None, "sem pasta de vozes → nada clonado")
    check(voz.listar_vozes()["clonadas"] == [], "listar_vozes sem clonadas")
    # pasta com referência
    ref = tmp / "vozes" / "thiago" / "referencias"; ref.mkdir(parents=True)
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=3", "-ar", "24000", str(ref / "ref_a.wav")], check=True)
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=3", "-ar", "24000", str(ref / "ref_b.wav")], check=True)
    (tmp / "vozes" / "thiago" / "voz.json").write_text(json.dumps({"referencia": "ref_b.wav", "exagero": 0.4, "rotulo": "voz clonada de teste"}), encoding="utf-8")
    (tmp / "vozes" / "vazia").mkdir()
    lv = voz_clonada.listar()
    check(list(lv) == ["thiago"] and lv["thiago"]["referencia"].endswith("ref_b.wav") and lv["thiago"]["n_referencias"] == 2 and lv["thiago"]["exagero"] == 0.4 and lv["thiago"]["cfg"] == 0.5, "listar lê voz.json e ignora pasta vazia")
    check(voz_clonada.nome_clonado("Thiago") == "thiago" and voz_clonada.nome_clonado("clonada:thiago") == "thiago" and voz_clonada.nome_clonado("antonio") is None, "nome_clonado aceita 'thiago' e 'clonada:thiago'")
    c = voz.listar_vozes()["clonadas"]
    check(len(c) == 1 and c[0]["nome"] == "thiago" and c[0]["tipo"] == "clonada" and c[0]["disponivel"] is False, "listar_vozes mostra a clonada como indisponível sem o venv")
    check(voz_clonada.disponivel() is False, "disponivel() falso sem o venv")
    # indisponível → erro claro
    try:
        voz_clonada.narrar("oi", tmp / "x.wav", "thiago"); check(False, "sem venv dá erro")
    except ErroFerramenta as e:
        check("indispon" in str(e), "sem venv dá erro claro")
    try:
        voz_clonada.sintetizar("oi", tmp / "x.wav", "ninguem", _pedir=lambda p: {"ok": True}); check(False, "voz inexistente dá erro")
    except ErroFerramenta as e:
        check("não encontrada" in str(e), "voz inexistente dá erro")

    # dublês
    pedidos = []
    def pedir_falso(p):
        pedidos.append(p); toks = p["texto"].split(); dur = 0.3 * len(toks) + 0.2
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur:.2f}", "-ar", "24000", p["saida"]], check=True)
        return {"ok": True, "duracao_s": dur, "partes": 1, "tempo_s": 0.1}
    def palavras_falsas(audio, texto, idioma):
        return [{"palavra": t, "inicio": round(0.1 + i * 0.3, 3), "fim": round(0.1 + i * 0.3 + 0.25, 3), "prob": 0.9} for i, t in enumerate(texto.split())]
    r = voz_clonada.narrar("Olha só, o OBS trava a webcam. Pronto, tá gravando!", tmp / "saida" / "n.mp3", "thiago", saida_palavras=tmp / "saida" / "n.json", semente=3, _pedir=pedir_falso, _palavras=palavras_falsas)
    check(r["voz"] == "clonada:thiago" and r["rotulo"] == "voz clonada de teste" and "sintético" in r["aviso"] and r["n_palavras"] == 10, "narrar clonado devolve voz, rótulo e aviso")
    check((tmp / "saida" / "n.mp3").exists() and not (tmp / "saida" / "n.clonada.wav").exists() and 2.5 < r["duracao_s"] < 3.5, f"áudio final convertido e bruto apagado ({r['duracao_s']} s)")
    pj = json.loads((tmp / "saida" / "n.json").read_text(encoding="utf-8"))
    check(pj["origem"] == "tts-clonada" and pj["palavras"][0]["palavra"] == "Olha" and pj["segmentos"][0]["texto"].endswith("webcam.") and len(pj["segmentos"]) == 2, "palavras.json com origem tts-clonada e segmentos por frase")
    check(pedidos[0]["ref"].endswith("ref_b.wav") and pedidos[0]["exagero"] == 0.4 and pedidos[0]["semente"] == 3 and pedidos[0]["idioma"] == "pt", "pedido ao processo leva referência, exagero e semente")
    # narrar genérico encaminha para a clonada quando voz = thiago (com dublês injetados via monkeypatch do módulo)
    original = voz_clonada.narrar
    chamadas = []
    voz_clonada.narrar = lambda *a, **k: (chamadas.append((a, k)) or {"audio": "x", "duracao_s": 1.0, "n_palavras": 1, "voz": "clonada:thiago", "palavras": []})
    try:
        r2 = voz.narrar("texto qualquer", tmp / "saida" / "g.mp3", voz="thiago")
        check(r2["voz"] == "clonada:thiago" and chamadas and chamadas[0][0][2] == "thiago", "voz.narrar(voz='thiago') encaminha para a clonada")
        r3 = voz.narrar("texto qualquer", tmp / "saida" / "g2.mp3", voz="clonada:thiago", idioma="pt")
        check(len(chamadas) == 2, "voz.narrar(voz='clonada:thiago') também")
    finally:
        voz_clonada.narrar = original
    # alinhar_texto: Whisper ouviu diferente, pulou e inventou palavras
    ouv = [{"palavra": "Olha", "inicio": 0.0, "fim": 0.3, "prob": 0.9}, {"palavra": "só,", "inicio": 0.3, "fim": 0.6, "prob": 0.9},
           {"palavra": "o", "inicio": 0.7, "fim": 0.8, "prob": 0.9}, {"palavra": "óbvio", "inicio": 0.8, "fim": 1.2, "prob": 0.4},
           {"palavra": "trava", "inicio": 1.3, "fim": 1.6, "prob": 0.9}, {"palavra": "a", "inicio": 1.6, "fim": 1.7, "prob": 0.9},
           {"palavra": "ebecão.", "inicio": 1.7, "fim": 2.2, "prob": 0.3}, {"palavra": "hum", "inicio": 2.3, "fim": 2.4, "prob": 0.2},
           {"palavra": "Pronto,", "inicio": 2.6, "fim": 2.9, "prob": 0.9}, {"palavra": "gravando!", "inicio": 3.2, "fim": 3.7, "prob": 0.9}]
    al = voz_clonada.alinhar_texto(ouv, "Ó, olha só, o OBS trava a webcam. Pronto, tá gravando!", duracao_s=3.8)
    check([p["palavra"] for p in al] == "Ó, olha só, o OBS trava a webcam. Pronto, tá gravando!".split(), "alinhar_texto devolve exatamente as palavras do texto")
    pel = {p["palavra"]: p for p in al}
    check(pel["OBS"]["inicio"] == 0.8 and pel["OBS"]["fim"] == 1.2 and pel["webcam."]["inicio"] == 1.7 and pel["trava"]["inicio"] == 1.3, "palavras ouvidas diferente herdam o tempo do trecho")
    check(pel["Ó,"]["inicio"] == 0.0 and pel["Ó,"]["fim"] < pel["olha"]["inicio"] + 0.001 and pel["tá"]["inicio"] >= 2.9 and pel["tá"]["fim"] <= 3.2, "palavras não ouvidas são interpoladas entre as vizinhas")
    check(all(al[k]["inicio"] >= al[k - 1]["fim"] - 1e-9 for k in range(1, len(al))) and all(p["fim"] >= p["inicio"] for p in al), "tempos monotônicos")
    check(len(voz_clonada.alinhar_texto([], "um dois três", duracao_s=3.0)) == 3 and voz_clonada.alinhar_texto([], "um dois três", duracao_s=3.0)[2]["inicio"] == 2.0, "sem nada ouvido: divide a duração por igual")
    check(voz_clonada.alinhar_texto(ouv, "") == [], "texto vazio")

    # motor Qwen pelo voz.json: ref_text das transcrições, pedido sem exagero/cfg, aviso sem transcrição, motor na resposta
    os.environ["EDITOR_GS_QWEN_PYTHON"] = str(tmp / "nao-existe" / "python-qwen")
    (ref / "transcricoes.json").write_text(json.dumps({"ref_b.wav": "Texto exato da referência bê."}), encoding="utf-8")
    (tmp / "vozes" / "thiago" / "voz.json").write_text(json.dumps({"referencia": "ref_b.wav", "motor_escolhido": "qwen", "qwen": {"temperatura": 0.7, "repeticao": 1.1}, "rotulo": "voz clonada de teste (Qwen)"}), encoding="utf-8")
    lv = voz_clonada.listar()["thiago"]
    check(lv["motor"] == "qwen" and lv["ref_text"] == "Texto exato da referência bê." and lv["qwen"] == {"temperatura": 0.7, "repeticao": 1.1}, "listar lê motor_escolhido, ref_text e parâmetros do qwen")
    check(voz_clonada.disponivel("qwen") is False and voz_clonada.disponivel("chatterbox") is False and set(voz_clonada.motores_disponiveis()) == {"chatterbox", "qwen"}, "disponivel por motor")
    check(voz_clonada.normalizar_motor("QWEN") == "qwen" and voz_clonada.normalizar_motor("x") == "chatterbox" and voz_clonada.normalizar_motor(None) == "chatterbox", "normalizar_motor")
    try:
        voz_clonada.sintetizar("oi", tmp / "x.wav", "thiago"); check(False, "sem venv do qwen dá erro")
    except ErroFerramenta as e:
        check("editor-gs-qwen" in str(e) and "Qwen" in str(e), "sem venv do qwen o erro aponta o venv certo")
    pedidos.clear()
    r = voz_clonada.sintetizar("Olha só, o OBS trava.", tmp / "q.wav", "thiago", semente=5, _pedir=pedir_falso)
    pq = pedidos[0]
    check(pq["motor"] == "qwen" and pq["ref_text"] == "Texto exato da referência bê." and pq["temperatura"] == 0.7 and pq["repeticao"] == 1.1 and "exagero" not in pq and "cfg" not in pq and pq["semente"] == 5, "pedido ao Qwen leva ref_text e parâmetros, sem exagero/cfg")
    check(r["motor"] == "qwen" and r["rotulo"] == "voz clonada de teste (Qwen)" and r["avisos"] == [], "sintetizar devolve motor, rótulo e sem aviso com transcrição")
    r = voz_clonada.sintetizar("Olha só.", tmp / "q2.wav", "thiago", referencia=str(ref / "ref_a.wav"), _pedir=pedir_falso)
    check(pedidos[-1]["ref"].endswith("ref_a.wav") and pedidos[-1]["ref_text"] is None and any("x_vector_only" in a for a in r["avisos"]), "referência sem transcrição: ref_text vazio e aviso x_vector_only")
    r = voz_clonada.sintetizar("Olha só.", tmp / "q3.wav", "thiago", referencia=str(ref / "ref_a.wav"), ref_text="Texto dado à mão.", motor="chatterbox", _pedir=pedir_falso)
    check(pedidos[-1]["motor"] == "chatterbox" and pedidos[-1]["exagero"] == 0.5 and "ref_text" not in pedidos[-1] and r["avisos"] == [], "motor explícito chatterbox: pedido com exagero/cfg e sem ref_text")
    r = voz_clonada.narrar("Pronto, tá gravando.", tmp / "saida" / "nq.mp3", "thiago", saida_palavras=tmp / "saida" / "nq.json", _pedir=pedir_falso, _palavras=palavras_falsas)
    pj = json.loads((tmp / "saida" / "nq.json").read_text(encoding="utf-8"))
    check(r["motor"] == "qwen" and pj["motor"] == "qwen" and pj["origem"] == "tts-clonada" and r["avisos"] == [], "narrar com Qwen grava motor no retorno e no palavras.json")
    c = voz.listar_vozes()["clonadas"][0]
    check(c["motor"] == "qwen" and c["motor_nome"] == "Qwen3-TTS" and "11 s" in c["tempo_estimado"], "listar_vozes mostra motor e tempo estimado")

    # processo de verdade com worker falso (protocolo pronto → progresso → ok), sem modelo: ponte lê o progresso, fecha com "sair", reergue depois de cair
    falso = RAIZ / "testes" / "_worker_falso_voz.py"
    os.environ["EDITOR_GS_QWEN_PYTHON"] = sys.executable
    worker_qwen_real = voz_clonada.WORKER_QWEN; voz_clonada.WORKER_QWEN = falso
    try:
        w = voz_clonada.worker_para("qwen"); w.fechar()
        vistos = []
        r = voz_clonada.sintetizar("Primeira frase aqui. Segunda frase ali! Terceira?", tmp / "p.wav", "thiago", _pedir=None, ao_progresso=vistos.append)
        check(r["ok"] and r["partes"] == 3 and r["motor"] == "qwen" and r["device"] == "cpu" and (tmp / "p.wav").exists(), "worker falso por processo: resposta final com motor e device")
        check([v["parte"] for v in vistos] == [1, 2, 3] and vistos[-1]["de"] == 3 and w.progresso == vistos[-1], "progresso frase a frase chega ao ao_progresso e fica no worker")
        check(w.p is not None and w.p.poll() is None and w._timer is not None, "processo continua vivo entre pedidos, com descarga ociosa agendada")
        try:
            w.pedir({"texto": "Vai falhar.", "saida": str(tmp / "f.wav"), "ref": "x", "falhar": True}); check(False, "ok=false vira erro")
        except ErroFerramenta as e:
            check("falha pedida" in str(e) and "Qwen" in str(e), "ok=false do worker vira ErroFerramenta com o motor")
        try:
            w.pedir({"texto": "Lenta demais.", "saida": str(tmp / "l.wav"), "ref": "x", "demorar_s": 2}, timeout=0.5); check(False, "tempo limite")
        except ErroFerramenta as e:
            check("demorou" in str(e) and w.p is None, "tempo limite mata o processo e explica a última etapa")
        r = voz_clonada.sintetizar("De novo depois de cair.", tmp / "r.wav", "thiago", _pedir=None)
        check(r["ok"] and w.p is not None, "ponte reergue o processo no pedido seguinte")
        w.fechar()
        check(w.p is None and w._timer is None, "fechar encerra o processo e cancela a descarga")
    finally:
        voz_clonada.WORKER_QWEN = worker_qwen_real
        os.environ["EDITOR_GS_QWEN_PYTHON"] = str(tmp / "nao-existe" / "python-qwen")
    # worker do Qwen: protocolo e reaproveitamento das funções de texto (sem torch)
    srcq = (RAIZ / "mcp" / "editor-de-video" / "editor_video" / "voz_qwen_worker.py").read_text(encoding="utf-8")
    check('"pronto": True' in srcq and '"motor": "qwen"' in srcq and "bfloat16" in srcq and "from voz_clonada_worker import aplicar_pronuncia, dividir" in srcq and "create_voice_clone_prompt" in srcq, "worker do Qwen expõe 'pronto', usa bf16 e reaproveita dividir/aplicar_pronuncia")
    check(voz_clonada.worker_de("qwen").name == "voz_qwen_worker.py" and voz_clonada.worker_de("chatterbox").name == "voz_clonada_worker.py", "worker_de por motor")
    # ocioso: fechar() cancela timer; _fechar_outros só mexe em processo vivo
    w = voz_clonada.worker_para("qwen"); w.fechar(); voz_clonada._fechar_outros("qwen")
    check(w.p is None and w._timer is None, "fechar/ _fechar_outros sem processo não quebram")
    # dividir do worker (sem torch): importa só a função
    import importlib.util
    spec = importlib.util.spec_from_file_location("w", RAIZ / "mcp" / "editor-de-video" / "editor_video" / "voz_clonada_worker.py"); w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
    partes = w.dividir("Frase um. Frase dois! " + "palavra " * 60 + ", depois vírgula, " + "x " * 50 + ". Fim?", max_chars=120)
    check(all(len(p) <= 120 for p in partes) and partes[0].startswith("Frase um. Frase dois!") and partes[-1].endswith("Fim?"), f"dividir respeita o limite e junta frases curtas ({len(partes)} partes)")
    check(w.dividir("curta") == ["curta"] and w.dividir("A. B. C.", 100) == ["A. B. C."], "dividir: texto curto fica inteiro")
    check(w.aplicar_pronuncia("Abra o OBS Studio e o OBS, não o obs nem OBSERVE a URL.") == "Abra o ô bê ésse Studio e o ô bê ésse, não o obs nem OBSERVE a u erre éle.", "aplicar_pronuncia: siglas inteiras, maiúsculas, sem tocar em palavras parecidas")
    check(w.aplicar_pronuncia("Meet e Zoom", {"Meet": "Mít"}) == "Mít e Zoom", "aplicar_pronuncia aceita mapa extra do voz.json")
    check(w.aplicar_pronuncia("Abra o OBS e a webcam", {"webcam": "uébcam"}, base=False) == "Abra o OBS e a uébcam", "aplicar_pronuncia(base=False) ignora o mapa padrão")
    check(w.aplicar_pronuncia("OBS e URL", {"OBS": ""}) == "OBS e u erre éle", "valor vazio em pronuncia apaga a entrada padrão")
    # aparar_bordas do worker do Qwen (só numpy)
    specq = importlib.util.spec_from_file_location("wq", RAIZ / "mcp" / "editor-de-video" / "editor_video" / "voz_qwen_worker.py"); wq = importlib.util.module_from_spec(specq); specq.loader.exec_module(wq)
    import numpy as np
    sr = 24000; sinal = np.zeros(sr * 2, dtype=np.float32); sinal[sr // 2: sr // 2 + sr // 4] = 0.5; sinal[100] = 0.005  # estalo fraco no começo, fala no meio
    ap, nd = wq.aparar_bordas(sinal, sr)
    check(nd == 0 and abs(len(ap) / sr - (0.25 + 0.08)) < 0.003 and ap[0] == 0.0 and ap[-1] == 0.0 and abs(float(ap[len(ap) // 2]) - 0.5) < 1e-6, f"aparar_bordas corta o quase-silêncio das pontas com margem e fade ({len(ap) / sr:.3f} s)")
    check(len(wq.aparar_bordas(np.zeros(sr, dtype=np.float32), sr)[0]) == sr and len(wq.aparar_bordas(np.ones(100, dtype=np.float32), sr)[0]) == 100, "aparar_bordas não mexe em silêncio total nem em áudio minúsculo")
    # som solto do Qwen: estouro de 0,15 s, vão de 0,3 s, fala de 1 s, vão de 0,2 s, estalo de 0,05 s no fim
    rng = np.random.default_rng(1)
    def ruido(seg, amp): return (rng.standard_normal(int(sr * seg)) * amp).astype(np.float32)
    sinal2 = np.concatenate([ruido(0.15, 0.2), np.zeros(int(sr * 0.3), np.float32), ruido(1.0, 0.3), np.zeros(int(sr * 0.2), np.float32), ruido(0.05, 0.2), np.zeros(int(sr * 0.1), np.float32)])
    ap2, nd2 = wq.aparar_bordas(sinal2, sr)
    check(nd2 == 2 and abs(len(ap2) / sr - (1.0 + 0.08)) < 0.03, f"aparar_bordas descarta o som solto antes da fala e o estalo depois ({nd2} removidos, {len(ap2) / sr:.2f} s)")
    sinal3 = np.concatenate([ruido(0.4, 0.2), np.zeros(int(sr * 0.3), np.float32), ruido(1.0, 0.3)])  # palavra curta de verdade (0,4 s) seguida de pausa: fica
    ap3, nd3 = wq.aparar_bordas(sinal3, sr)
    check(nd3 == 0 and abs(len(ap3) / sr - 1.7) < 0.03, "trecho sonoro acima de 0,22 s não é tratado como som solto")
    check(wq.IDIOMAS["pt"] == "Portuguese" and wq.IDIOMAS["en"] == "English" and wq.MAX_CHARS == 200, "idiomas e limite de caracteres do worker do Qwen")
    # worker não é importável sem torch aqui? só checamos que o arquivo existe e tem protocolo
    src = (RAIZ / "mcp" / "editor-de-video" / "editor_video" / "voz_clonada_worker.py").read_text(encoding="utf-8")
    check('"pronto": True' in src and "t3_pt_br.safetensors" in src, "worker expõe 'pronto' e usa o T3 pt-BR")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
