import os
from .util import caminho, caminho_saida, salvar_json, info_midia, nivel_audio, ErroFerramenta


def escolher_device(device="auto", compute_type=None):
    if device == "auto":
        try:
            import ctranslate2
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
    if not compute_type:
        compute_type = "int8_float16" if device == "cuda" else "int8"
    return device, compute_type


def transcrever(midia, saida_json, modelo="small", device="auto", compute_type=None, idioma="pt", vad=True, saida_srt=None):
    from faster_whisper import WhisperModel
    m = caminho(midia)
    info = info_midia(m)
    if not info["tem_audio"]:
        raise ErroFerramenta("O arquivo não tem faixa de áudio.")
    nivel = nivel_audio(m)
    if nivel["pico_db"] <= -80:
        raise ErroFerramenta(f"Áudio em silêncio digital (pico {nivel['pico_db']} dB): nada para transcrever.")
    dev, ct = escolher_device(device, compute_type)
    try:
        model = WhisperModel(modelo, device=dev, compute_type=ct)
    except Exception as e:
        if dev == "cuda":
            dev, ct = "cpu", "int8"
            model = WhisperModel(modelo, device=dev, compute_type=ct)
        else:
            raise ErroFerramenta(f"Não carreguei o modelo {modelo}: {e}")
    segs, sinfo = model.transcribe(str(m), language=idioma, word_timestamps=True, vad_filter=vad)
    segs = list(segs) if dev != "cuda" else None
    if segs is None:  # a falha de CUDA (ex.: libcublas ausente) só aparece ao consumir o gerador: cai para CPU
        try:
            segs, sinfo = model.transcribe(str(m), language=idioma, word_timestamps=True, vad_filter=vad); segs = list(segs)
        except Exception as e:  # noqa
            dev, ct = "cpu", "int8"
            model = WhisperModel(modelo, device=dev, compute_type=ct)
            segs, sinfo = model.transcribe(str(m), language=idioma, word_timestamps=True, vad_filter=vad); segs = list(segs)
    segmentos, palavras = [], []
    for s in segs:
        ws = []
        for w in (s.words or []):
            p = {"palavra": w.word.strip(), "inicio": round(w.start, 3), "fim": round(w.end, 3), "prob": round(float(w.probability), 3)}
            if p["palavra"]:
                ws.append(p); palavras.append(p)
        segmentos.append({"inicio": round(s.start, 3), "fim": round(s.end, 3), "texto": s.text.strip(), "n_palavras": len(ws)})
    dados = {
        "arquivo": str(m), "modelo": modelo, "device": dev, "compute_type": ct, "idioma": idioma, "vad": vad,
        "duracao_s": info["duracao_s"], "nivel_audio": nivel,
        "n_segmentos": len(segmentos), "n_palavras": len(palavras),
        "fala_s": round(sum(max(0.0, p["fim"] - p["inicio"]) for p in palavras), 2),
        "baixa_confianca": [p for p in palavras if p["prob"] < 0.5],
        "segmentos": segmentos, "palavras": palavras,
    }
    out = salvar_json(saida_json, dados)
    srt = None
    if saida_srt:
        import pysubs2
        subs = pysubs2.SSAFile()
        for s in segmentos:
            subs.append(pysubs2.SSAEvent(start=int(s["inicio"] * 1000), end=int(s["fim"] * 1000), text=s["texto"]))
        srt = str(caminho_saida(saida_srt)); subs.save(srt)
    return {"palavras_json": out, "srt": srt, "device": dev, "n_segmentos": len(segmentos), "n_palavras": len(palavras),
            "fala_s": dados["fala_s"], "duracao_s": info["duracao_s"], "baixa_confianca": len(dados["baixa_confianca"])}
