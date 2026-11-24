"""Voz sintética para o Editor GS (edge-tts: vozes neurais da Microsoft, gratuitas, sem chave; precisa de internet).
- narrar: texto → áudio + tempos por palavra (mesmo formato de palavras.json da transcrição, para legenda karaokê).
- montar_locucao: vídeo do zero a partir de cenas (imagem ou vídeo + texto narrado), com legenda no estilo da marca.
- dublar: troca a fala de um vídeo pela narração de um SRT traduzido, bloco a bloco, com legenda opcional.
Não é voz do Thiago: é locução neutra. Clonar a voz dele só com autorização dele e ferramenta própria."""
import asyncio, json, re, shutil, threading
from pathlib import Path
from .util import caminho, caminho_saida, ErroFerramenta, FFMPEG, info_midia, ler_json, rodar

VOZES = {"antonio": "pt-BR-AntonioNeural", "francisca": "pt-BR-FranciscaNeural", "thalita": "pt-BR-ThalitaMultilingualNeural",
         "en-andrew": "en-US-AndrewMultilingualNeural", "en-guy": "en-US-GuyNeural", "en-jenny": "en-US-JennyNeural", "en-ava": "en-US-AvaMultilingualNeural",
         "es-alvaro": "es-ES-AlvaroNeural", "es-elvira": "es-ES-ElviraNeural", "es-mx-jorge": "es-MX-JorgeNeural"}
VOZ_POR_IDIOMA = {"pt": "antonio", "en": "en-andrew", "es": "es-alvaro"}
ALVOS = {("9x16", "720p"): (720, 1280), ("9x16", "1080p"): (1080, 1920), ("16x9", "720p"): (1280, 720), ("16x9", "1080p"): (1920, 1080),
         ("1x1", "720p"): (720, 720), ("1x1", "1080p"): (1080, 1080), ("4x5", "720p"): (720, 900), ("4x5", "1080p"): (1080, 1350)}
_PONT = re.compile(r"^[\s\"'“”‘’(\[]+|[\s\"'“”‘’)\].,;:!?…]+$")


def voz_nome(voz, idioma="pt"):
    v = (voz or "").strip() or VOZ_POR_IDIOMA.get((idioma or "pt")[:2].lower(), "antonio")
    return VOZES.get(v, v)  # também aceita o ShortName da Microsoft (ex.: pt-BR-AntonioNeural)


def listar_vozes():
    from . import voz_clonada
    clonadas = [{"nome": k, "tipo": "clonada", "motor": v["motor"], "motor_nome": voz_clonada.NOMES_MOTOR.get(v["motor"], v["motor"]), "rotulo": v["rotulo"],
                 "n_referencias": v["n_referencias"], "disponivel": voz_clonada.disponivel(v["motor"]),
                 "tempo_estimado": "~11 s de processamento por segundo de fala na GPU (40 s de fala ≈ 8 min)" if v["motor"] == "qwen" else "~3 s de processamento por segundo de fala"}
                for k, v in voz_clonada.listar().items()]
    return {"vozes": [{"nome": k, "microsoft": v, "idioma": v[:5]} for k, v in VOZES.items()], "padrao_por_idioma": VOZ_POR_IDIOMA, "clonadas": clonadas,
            "nota": "edge-tts (gratuito, precisa de internet). Também aceita qualquer ShortName da Microsoft. As vozes 'clonadas' (ex.: thiago) rodam localmente "
                    "no motor escolhido em voz.json (Qwen3-TTS desde 31/10/2026; Chatterbox pt-BR como reserva) e são sempre identificadas como voz sintética clonada "
                    "na entrega, nunca como gravação real. Mais lentas que o edge-tts: avise o tempo no pedido longo."}


async def _sintetizar_async(texto, voz, rate, saida_mp3):
    import edge_tts
    com = edge_tts.Communicate(texto, voz, rate=rate, boundary="WordBoundary")
    palavras = []
    with open(saida_mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                palavras.append({"palavra": ch["text"], "inicio": round(ch["offset"] / 1e7, 3), "fim": round((ch["offset"] + ch["duration"]) / 1e7, 3), "prob": 1.0})
    return palavras


def _sintetizar(texto, voz, rate, saida_mp3):
    """Roda a corrotina mesmo quando já existe um loop (o FastMCP chama a ferramenta dentro de um)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_sintetizar_async(texto, voz, rate, saida_mp3))
    out = {}
    def alvo():
        try:
            out["r"] = asyncio.run(_sintetizar_async(texto, voz, rate, saida_mp3))
        except Exception as e:  # noqa
            out["e"] = e
    t = threading.Thread(target=alvo); t.start(); t.join()
    if "e" in out:
        raise out["e"]
    return out["r"]


def _repor_pontuacao(palavras, texto):
    """O WordBoundary vem sem pontuação; devolve a grafia do texto original (com vírgula, ponto, maiúscula) quando dá para casar."""
    tokens = texto.split(); j = 0
    for p in palavras:
        alvo = _PONT.sub("", p["palavra"]).lower()
        for k in range(j, min(j + 3, len(tokens))):
            if _PONT.sub("", tokens[k]).lower() == alvo:
                p["palavra"] = tokens[k]; j = k + 1; break
    return palavras


def _segmentos(palavras):
    """Agrupa palavras em frases (termina em . ! ? … ou pausa > 0,7 s) para o montar_remotion e o SRT."""
    segs, atual = [], []
    for i, p in enumerate(palavras):
        atual.append(p)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        fim_frase = p["palavra"].rstrip('"”’)').endswith((".", "!", "?", "…", ":"))
        if fim_frase or prox is None or prox["inicio"] - p["fim"] > 0.7:
            segs.append({"inicio": atual[0]["inicio"], "fim": atual[-1]["fim"], "texto": " ".join(x["palavra"] for x in atual)}); atual = []
    return segs


def narrar(texto, saida_audio, voz="", velocidade=0, idioma="pt", saida_palavras=None, _sint=None):
    """Narração de um texto. saida_audio .mp3 (direto) ou .wav/.m4a (convertido). Devolve duração e palavras com tempos."""
    texto = re.sub(r"\s+", " ", (texto or "").replace("*", "")).strip()
    if not texto:
        raise ErroFerramenta("Texto vazio para narrar.")
    if len(texto) > 6000:
        raise ErroFerramenta("Texto longo demais para uma narração (máx. 6000 caracteres): divida em cenas.")
    from . import voz_clonada
    if (nome := voz_clonada.nome_clonado(voz)) and not _sint:
        return voz_clonada.narrar(texto, saida_audio, nome, idioma=idioma, saida_palavras=saida_palavras)
    out = caminho_saida(saida_audio); vz = voz_nome(voz, idioma)
    rate = f"{int(velocidade):+d}%"
    mp3 = out if out.suffix.lower() == ".mp3" else out.with_suffix(".tts.mp3")
    try:
        palavras = (_sint or _sintetizar)(texto, vz, rate, str(mp3))
    except Exception as e:
        raise ErroFerramenta(f"Síntese de voz falhou ({type(e).__name__}: {str(e)[:160]}). Precisa de internet; tente de novo ou outra voz.")
    if not mp3.exists() or mp3.stat().st_size < 1000:
        raise ErroFerramenta("A síntese não devolveu áudio (texto rejeitado ou sem conexão).")
    if mp3 != out:
        rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", mp3, "-ar", "48000", "-ac", "2", out]); mp3.unlink(missing_ok=True)
    palavras = _repor_pontuacao(palavras, texto)
    dur = info_midia(out)["duracao_s"]
    d = {"arquivo": str(out), "origem": "tts", "voz": vz, "idioma": idioma, "texto": texto, "palavras": palavras, "segmentos": _segmentos(palavras)}
    pj = None
    if saida_palavras:
        pj = caminho_saida(saida_palavras); pj.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"audio": str(out), "duracao_s": dur, "n_palavras": len(palavras), "voz": vz, "palavras_json": str(pj) if pj else None, "palavras": palavras}


# --- vídeo do zero: cenas narradas ---------------------------------------------------------------
TRANSICOES = {"fade", "dissolve", "fadeblack", "fadewhite", "smoothleft", "smoothright", "smoothup", "smoothdown", "slideleft", "slideright", "slideup", "slidedown",
              "wipeleft", "wiperight", "circleopen", "circleclose", "zoomin", "distance", "pixelize", "radial", "hblur"}
TRANSICOES_AUTO = ["fade", "smoothleft", "dissolve", "smoothup"]
MOVIMENTOS = ("alternar", "entrar", "sair", "parado")
_FF = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]


def _quadro_pronto(origem, W, H, destino):
    """Imagem no tamanho exato do vídeo: corta quando a orientação bate; com orientação diferente (print 16:9 num 9:16) usa fundo desfocado."""
    from PIL import Image, ImageFilter, ImageOps
    im = Image.open(origem).convert("RGB"); w, h = im.size
    if (w > h) == (W > H) or W == H:
        ImageOps.fit(im, (W, H), method=Image.LANCZOS).save(destino)
    else:
        fundo = ImageOps.fit(im, (W, H), method=Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
        escala = min(W / w, H / h); fg = im.resize((max(1, int(w * escala)), max(1, int(h * escala))), Image.LANCZOS)
        fundo.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2)); fundo.save(destino)
    return destino


def _tipo_cena(c):
    """slide (texto animado ou PNG tipográfico marcado), video ou imagem (print/foto real). `tipo` explícito na cena vence."""
    t = (c.get("tipo") or "").lower()
    if t in ("slide", "video", "imagem"):
        return t
    if t in ("print", "foto"):
        return "imagem"
    return "slide" if c.get("slide") else "video" if c.get("video") else "imagem"


def _movimento(i, padrao, cena):
    m = (cena.get("movimento") or padrao or "alternar").lower()
    if m not in MOVIMENTOS:
        raise ErroFerramenta(f"movimento inválido: {m} (use alternar | entrar | sair | parado)")
    return ("entrar" if i % 2 == 0 else "sair") if m == "alternar" else m


def _cena_slide(cena, W, H, fps, L, destino, estilo, _render=None):
    """Slide tipográfico animado no Remotion (título palavra a palavra, barra laranja, apoio linha a linha). Se o Remotion falhar, cai para o PNG do manual com movimento."""
    from . import acabamento
    s = cena["slide"] if isinstance(cena.get("slide"), dict) else {"titulo": str(cena.get("slide") or "")}
    if not (s.get("titulo") or "").strip():
        raise ErroFerramenta("Cena `slide` precisa de `titulo`.")
    apoio = s.get("apoio") or []
    apoio = [apoio] if isinstance(apoio, str) else [str(a) for a in apoio][:6]
    est = (estilo or {}).get("legenda", estilo or {})
    props = {"duracao_s": round(L, 3), "fps": fps, "largura": W, "altura": H, "titulo": s["titulo"], "destaque": s.get("destaque") or "", "apoio": apoio,
             "fundo": "papel" if (s.get("fundo") or "").lower() == "papel" else "marinho", "animacao": s.get("animacao") or "palavras", "selo": s.get("selo") or "",
             "estilo": {"cor_destaque": est.get("cor_destaque", "#F79615"), "cor_fundo": est.get("contorno", "#000921"), "cor_texto": est.get("cor_texto", "#FFFFFF"),
                        "fonte_titulo": "InterGS", "fonte_texto": "InterGS"}}
    try:
        (_render or acabamento.renderizar_remotion)("CenaTexto", props, destino)
        return {"video": str(destino), "origem": "remotion"}
    except Exception as e:  # noqa — sem Remotion/Chromium o vídeo ainda sai, com o slide parado do manual
        from .imagem import gerar_post_imagem
        png = destino.with_suffix(".png"); fmt = "story" if H / W > 1.5 else "feed" if H > W else "16x9" if W > H else "quadrado"
        gerar_post_imagem(png, s["titulo"], destaque=s.get("destaque") or "", apoio=apoio, formato=fmt, selo=s.get("selo") or "")
        return {"imagem": str(png), "origem": "png", "aviso": f"Slide animado falhou ({str(e)[:140]}); usei o slide PNG com movimento."}


def _cena_video(cena, W, H, fps, L, destino, zoom, movimento):
    """Clipe SEM áudio de uma cena com duração L: imagem com Ken Burns (entrar = aproxima, sair = afasta, parado) ou vídeo (sem o áudio dele) ajustado ao tamanho."""
    frames = max(1, int(round(L * fps)))
    if cena.get("imagem"):
        img = caminho(cena["imagem"]); pronto = destino.with_suffix(".quadro.png"); _quadro_pronto(img, W, H, pronto)
        z = max(1.0, float(zoom)); passo = (z - 1) / frames
        expr = "1" if (movimento == "parado" or z <= 1.0001) else (f"'min(1+{passo:.7f}*on,{z})'" if movimento == "entrar" else f"'max({z}-{passo:.7f}*on,1)'")
        filtro = f"[0:v]scale={W * 2}:{H * 2},zoompan=z={expr}:d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},format=yuv420p,setsar=1[v]"
        cmd = _FF + ["-framerate", str(fps), "-i", pronto, "-filter_complex", filtro, "-map", "[v]"]
    elif cena.get("video"):
        v = caminho(cena["video"]); ini = float(cena.get("inicio_s") or 0)
        filtro = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},format=yuv420p,setsar=1[v]"
        cmd = _FF + ["-stream_loop", "-1", "-ss", f"{ini:.3f}", "-i", v, "-filter_complex", filtro, "-map", "[v]"]
    else:
        raise ErroFerramenta("Cada cena precisa de `imagem`, `video` ou `slide`.")
    rodar(cmd + ["-an", "-t", f"{L:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-video_track_timescale", "90000", destino])
    return destino


def _juntar_video(clipes, durs, d, nomes, fps, saida):
    """Emenda os clipes: com d > 0, xfade entre cada par (o clipe seguinte tem d s a mais no começo, então a transição acontece na pausa, antes da fala)."""
    if d <= 0 or len(clipes) == 1:
        lista = saida.with_suffix(".txt"); lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in clipes), encoding="utf-8")
        rodar(_FF + ["-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", saida]); return saida
    cmd = list(_FF)
    for c in clipes:
        cmd += ["-i", c]
    fc, prev, acc, n = [], "[0:v]", 0.0, len(clipes)
    for k in range(1, n):
        acc += durs[k - 1]; rot = f"[x{k}]" if k < n - 1 else "[v]"
        fc.append(f"{prev}[{k}:v]xfade=transition={nomes[k]}:duration={d:.3f}:offset={acc - d:.3f}{rot}"); prev = rot
    rodar(cmd + ["-filter_complex", ";".join(fc), "-map", "[v]", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", saida])
    return saida


def _narrar_com_cache(texto, saida_mp3, voz, velocidade, idioma, cache_dir, _sint=None):
    """narrar() com cache por (texto, voz, velocidade, idioma) em cache_dir: o áudio e as palavras ficam em <hash>.mp3/.json e são copiados para saida_mp3.
    Vale ouro com a voz clonada (minutos por cena). Cache desligado quando a voz é vazia e o motor é escolhido pelo idioma? Não: a chave inclui a voz resolvida."""
    import hashlib
    chave = hashlib.sha1("|".join([texto.strip(), voz_nome(voz, idioma), str(int(velocidade or 0)), (idioma or "pt")[:2]]).encode("utf-8")).hexdigest()[:20]
    cache_dir = Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    mp3, js = cache_dir / f"{chave}.mp3", cache_dir / f"{chave}.json"
    saida_mp3 = caminho_saida(saida_mp3)
    if mp3.exists() and js.exists() and mp3.stat().st_size > 1000:
        try:
            n = json.loads(js.read_text(encoding="utf-8")); shutil.copy2(mp3, saida_mp3); n["audio"] = str(saida_mp3); n["cache"] = True
            return n
        except Exception:  # noqa
            pass
    n = narrar(texto, saida_mp3, voz=voz, velocidade=velocidade, idioma=idioma, _sint=_sint)
    try:
        shutil.copy2(n["audio"], mp3); js.write_text(json.dumps({k: v for k, v in n.items() if k != "audio"}, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa
        pass
    n["cache"] = False
    return n


def montar_locucao(cenas_json, saida_video, formato="9x16", estilo=None, voz="", velocidade=0, idioma="pt", resolucao="1080p", pausa_s=0.4, zoom=1.08, fps=30,
                   trilha=None, saida_palavras=None, transicao="fade", transicao_s=0.35, movimento="alternar", jcut_s=0.0, _sint=None, _render=None):
    """Vídeo do zero: cada cena = {"texto": fala narrada} mais uma fonte visual: "imagem" (png/jpg; print 16:9 em 9:16 ganha fundo desfocado), "video" (clipe, com "inicio_s")
    ou "slide" ({"titulo", "destaque"?, "apoio"?: [...], "fundo"?: marinho|papel, "selo"?, "animacao"?: palavras|linhas|nenhuma} → texto animado no Remotion).
    A narração dita a duração de cada cena (+ pausa_s). Movimento das imagens: alternar (aproxima/afasta por cena), entrar, sair ou parado (também por cena).
    Transição entre cenas: nome do xfade (fade, dissolve, smoothleft, …), "auto" (varia) ou "nenhuma"; acontece na pausa, antes da fala seguinte.
    jcut_s > 0 (ex.: 0.3): J-cut, a imagem da cena anterior segura jcut_s s já com a fala seguinte começada e só então corta/transita (ritmo de edição
    profissional: o corte cai dentro da frase, não no silêncio). O áudio não muda; só a duração visual de cada cena.
    Saída: vídeo no formato com legenda karaokê do estilo (se estilo), <saida>_palavras.json e .srt, mais capa_sugerida (instante de cena real) e avisos."""
    from . import legenda as leg_mod, montagem
    if (formato, resolucao) not in ALVOS:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    W, H = ALVOS[(formato, resolucao)]
    cenas = ler_json(cenas_json) if isinstance(cenas_json, (str, Path)) else cenas_json
    if isinstance(cenas, dict):
        cenas = cenas.get("cenas", [])
    cenas = [c for c in cenas if (c.get("texto") or "").strip()]
    if not cenas:
        raise ErroFerramenta("Nenhuma cena com texto.")
    if len(cenas) > 40:
        raise ErroFerramenta("Muitas cenas (máx. 40).")
    if (movimento or "alternar") not in MOVIMENTOS:
        raise ErroFerramenta(f"movimento inválido: {movimento} (use alternar | entrar | sair | parado)")
    if (transicao or "fade") == "fade" and isinstance(estilo, dict) and (estilo.get("montagem") or {}).get("transicao"):
        transicao = estilo["montagem"]["transicao"]  # transição escolhida no estilo (página Estilos) vale quando o pedido não diz outra
    trans = (transicao or "").strip().lower()
    if trans in ("", "nenhuma", "none", "sem"):
        trans = ""
    elif trans != "auto" and trans not in TRANSICOES:
        raise ErroFerramenta(f"transicao inválida: {transicao} (use auto, nenhuma ou um xfade: {', '.join(sorted(TRANSICOES))})")
    out = caminho_saida(saida_video); trab = out.parent / "_trabalho" / f"locucao-{out.stem}"; trab.mkdir(parents=True, exist_ok=True)
    # 1) narração de todas as cenas (a duração de cada uma vem da fala)
    narr, durs = [], []
    cache_dir = out.parent / "_trabalho" / "cache_narracao"  # narração por cena reaproveitada entre remontagens ("refaça só a cena 3" não renarra as outras)
    for i, c in enumerate(cenas, 1):
        n = _narrar_com_cache(c["texto"], trab / f"cena-{i:02d}.mp3", voz=c.get("voz") or voz, velocidade=c.get("velocidade", velocidade), idioma=idioma, cache_dir=cache_dir, _sint=_sint)
        dur = n["duracao_s"] + float(c.get("pausa_s", pausa_s))
        if c.get("duracao_min_s"):
            dur = max(dur, float(c["duracao_min_s"]))
        narr.append(n); durs.append(dur)
    d = min(float(transicao_s), min(durs) / 2) if (trans and len(cenas) > 1) else 0.0
    if d < 0.05:
        d = 0.0
    jc = max(0.0, float(jcut_s or 0.0)) if len(cenas) > 1 else 0.0
    if jc:
        jc = min(jc, max(0.0, (min(durs) - d) / 4))  # a cena seguinte nunca perde mais de um quarto da sua duração
    if jc < 0.05:
        jc = 0.0
    dvid = list(durs)  # duração visual de cada cena (com J-cut, a anterior ganha jc e a seguinte perde jc; o áudio segue durs)
    for k in range(len(dvid) - 1):
        if jc:
            dvid[k] += jc; dvid[k + 1] -= jc
    nomes = [None] + [((c.get("transicao") or "").lower() or (TRANSICOES_AUTO[(k - 1) % len(TRANSICOES_AUTO)] if trans == "auto" else trans)) for k, c in enumerate(cenas[1:], 1)]
    for nm in nomes[1:]:
        if d and nm not in TRANSICOES:
            raise ErroFerramenta(f"transicao inválida na cena: {nm}")
    # 2) clipes de vídeo (sem áudio) e áudio de cada cena com a duração exata
    palavras, segmentos, clipes, audios, linhas, avisos, capa, t = [], [], [], [], [], [], None, 0.0
    for i, (c, n, dur) in enumerate(zip(cenas, narr, durs), 1):
        L = dvid[i - 1] + (d if i > 1 else 0.0); tipo = _tipo_cena(c); fonte = c; origem = tipo
        if c.get("slide"):
            r = _cena_slide(c, W, H, fps, L, trab / f"cena-{i:02d}.slide.mp4", estilo, _render=_render); origem = "slide-" + r["origem"]
            fonte = {k: v for k, v in c.items() if k not in ("imagem", "video")}; fonte.update({k: v for k, v in r.items() if k in ("video", "imagem")})
            if r.get("aviso"):
                avisos.append(f"cena {i}: {r['aviso']}")
        mov = _movimento(i - 1, movimento, c) if fonte.get("imagem") else "parado"
        _cena_video(fonte, W, H, fps, L, trab / f"cena-{i:02d}.mp4", float(c.get("zoom", zoom)), mov)
        wav = trab / f"cena-{i:02d}.wav"
        rodar(_FF + ["-i", n["audio"], "-af", "apad", "-t", f"{dur:.3f}", "-ar", "48000", "-ac", "2", wav])
        for p in n["palavras"]:
            palavras.append({**p, "inicio": round(p["inicio"] + t, 3), "fim": round(p["fim"] + t, 3)})
        segmentos.append({"inicio": round(t, 3), "fim": round(t + dur, 3), "texto": n["palavras"] and " ".join(p["palavra"] for p in n["palavras"]) or c["texto"]})
        linhas.append({"cena": i, "inicio": round(t, 3), "fim": round(t + dur, 3), "duracao_s": round(dur, 3), "tipo": tipo, "origem": origem, "movimento": mov,
                       "transicao": nomes[i - 1] if (d and i > 1) else None, "corte_visual_s": round(t + dvid[i - 1], 3) if i < len(cenas) else None, "texto": c["texto"][:80]})
        if capa is None and tipo in ("imagem", "video"):
            capa = {"cena": i, "instante_s": round(t + min(0.8, dur / 2), 3), "tipo": tipo}
        clipes.append(trab / f"cena-{i:02d}.mp4"); audios.append(wav); t += dur
    # 3) emenda (xfade na pausa) + áudio contínuo
    video_so = _juntar_video(clipes, dvid, d, nomes, fps, trab / "video.mp4")
    la = trab / "audios.txt"; la.write_text("".join(f"file '{p.as_posix()}'\n" for p in audios), encoding="utf-8")
    audio = trab / "audio.wav"; rodar(_FF + ["-f", "concat", "-safe", "0", "-i", la, "-c", "copy", audio])
    base = trab / "base.mp4"
    rodar(_FF + ["-i", video_so, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", base])
    pj = caminho_saida(saida_palavras) if saida_palavras else out.with_name(out.stem + "_palavras.json")
    pj.write_text(json.dumps({"arquivo": str(base), "origem": "tts", "voz": voz_nome(voz, idioma), "idioma": idioma, "palavras": palavras, "segmentos": segmentos}, ensure_ascii=False, indent=1), encoding="utf-8")
    ass = srt = None
    if estilo:
        ass = trab / "legenda.ass"; srt = out.with_suffix(".srt")
        leg_mod.gerar_legenda(pj, ass, estilo, formato=formato if formato in ("9x16", "16x9", "1x1") else "9x16", saida_srt=srt)
        montagem.montar(base, out, formato=formato if (formato, resolucao) in montagem.ALVOS else "9x16", legenda_ass=ass, resolucao=resolucao, enquadramento="centro", preset="veryfast")
    else:
        shutil.copy2(base, out)
    if trilha:
        from .longos import adicionar_trilha
        com_trilha = out.with_name(out.stem + ".trilha.mp4"); adicionar_trilha(out, trilha, com_trilha); com_trilha.replace(out)
    if capa is None:
        capa = {"cena": None, "instante_s": None, "dica": "todas as cenas são slides: faça a capa com gerar_post_imagem (story/16x9) ou gerar_capa(imagem=foto real), não com um quadro do vídeo"}
    info = info_midia(out)
    return {"video": str(out), "duracao_s": info["duracao_s"], "largura": info["largura"], "altura": info["altura"], "n_cenas": len(cenas), "cenas_do_cache": sum(1 for n in narr if n.get("cache")), "cenas": linhas,
            "transicao": {"tipo": (trans or "nenhuma") if d else "nenhuma", "duracao_s": d}, "movimento": movimento, "jcut_s": jc, "capa_sugerida": capa, "avisos": avisos,
            "palavras_json": str(pj), "srt": str(srt) if srt else None, "legenda_ass": str(ass) if ass else None, "voz": voz_nome(voz, idioma), "trabalho": str(trab)}


# --- dublagem a partir de um SRT traduzido -------------------------------------------------------
def _blocos_srt(srt):
    import pysubs2
    try:
        subs = pysubs2.load(str(caminho(srt)), encoding="utf-8")
    except Exception as e:
        raise ErroFerramenta(f"SRT inválido: {e}")
    blocos = []
    for ev in subs:
        if ev.is_comment:
            continue
        txt = re.sub(r"\{[^}]*\}", "", ev.plaintext.replace("\\N", " ")).replace("*", "")
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            blocos.append({"inicio": ev.start / 1000, "fim": ev.end / 1000, "texto": txt})
    if not blocos:
        raise ErroFerramenta("SRT sem blocos com texto.")
    return sorted(blocos, key=lambda b: b["inicio"])


def _velocidade_automatica(blocos, narr, dur_v, velocidade, limite=20):
    """Se a maioria dos blocos não cabe na janela, devolve uma velocidade maior da voz (edge-tts, soa natural) para renarrar; senão None.
    Usa a mediana dos fatores necessários; nunca passa de `limite` % além da velocidade pedida."""
    fatores = []
    for i, (b, n) in enumerate(zip(blocos, narr)):
        prox = blocos[i + 1]["inicio"] if i + 1 < len(blocos) else dur_v
        janela = max(0.6, prox - b["inicio"]); fatores.append(n["duracao_s"] / janela)
    apertados = sum(1 for f in fatores if f > 1.02)
    if len(blocos) < 2 or apertados * 2 < len(blocos):
        return None
    med = sorted(fatores)[len(fatores) // 2]
    extra = int(round((med - 1) * 100)) + 2
    if extra < 5:
        return None
    return int(velocidade) + min(limite, extra)


def dublar(video, srt, saida_video, idioma="en", voz="", velocidade=0, original_db=-22.0, max_acelerar=1.35, estilo=None, formato="9x16", resolucao="1080p",
           saida_palavras=None, auto_velocidade=True, _sint=None):
    """Narra cada bloco do SRT (já traduzido) na hora certa, acelera até max_acelerar quando a fala não cabe no bloco, abaixa a voz original
    (original_db; None ou -99 remove) e devolve o vídeo dublado; com estilo, queima a legenda karaokê no idioma novo.
    auto_velocidade: se metade ou mais dos blocos não cabe, renarra tudo com a voz um pouco mais rápida (até +20 %) antes de recorrer ao atempo."""
    from . import legenda as leg_mod, montagem
    v = caminho(video); info = info_midia(v); dur_v = info["duracao_s"]
    if not info.get("tem_audio", True) and original_db is not None:
        original_db = None
    blocos = _blocos_srt(srt)
    out = caminho_saida(saida_video); trab = out.parent / "_trabalho" / f"dublagem-{out.stem}"; trab.mkdir(parents=True, exist_ok=True)
    narr = [narrar(b["texto"], trab / f"bloco-{i + 1:03d}.wav", voz=voz, velocidade=velocidade, idioma=idioma, _sint=_sint) for i, b in enumerate(blocos)]
    velocidade_usada = int(velocidade)
    if auto_velocidade:
        nova = _velocidade_automatica(blocos, narr, dur_v, velocidade)
        if nova is not None:
            velocidade_usada = nova
            narr = [narrar(b["texto"], trab / f"bloco-{i + 1:03d}.wav", voz=voz, velocidade=nova, idioma=idioma, _sint=_sint) for i, b in enumerate(blocos)]
    pecas, palavras, cursor, acelerados, atraso_max = [], [], 0.0, 0, 0.0
    for i, b in enumerate(blocos):
        n = narr[i]
        prox = blocos[i + 1]["inicio"] if i + 1 < len(blocos) else dur_v
        janela = max(0.6, prox - b["inicio"])
        fator = 1.0; aud = Path(n["audio"]); dur = n["duracao_s"]
        if dur > janela * 1.02:
            fator = min(float(max_acelerar), dur / janela)
            if fator > 1.02:
                rap = trab / f"bloco-{i + 1:03d}.rapido.wav"
                rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", aud, "-af", f"atempo={fator:.4f}", rap]); aud = rap; dur = info_midia(rap)["duracao_s"]; acelerados += 1
        inicio = max(b["inicio"], cursor)  # se a fala anterior invadiu, começa logo depois dela
        atraso_max = max(atraso_max, inicio - b["inicio"])
        if inicio > cursor + 0.01:
            sil = trab / f"sil-{i + 1:03d}.wav"
            rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{inicio - cursor:.3f}", sil]); pecas.append(sil)
        pecas.append(aud); cursor = inicio + dur
        for p in n["palavras"]:
            palavras.append({**p, "inicio": round(inicio + p["inicio"] / fator, 3), "fim": round(inicio + p["fim"] / fator, 3)})
    lista = trab / "dub.txt"; lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in pecas), encoding="utf-8")
    dub = trab / "dub.wav"
    rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lista, "-ar", "48000", "-ac", "2", dub])
    sem_leg = trab / "dublado.mp4"
    if original_db is None or original_db <= -90 or not info.get("tem_audio", True):
        rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", v, "-i", dub, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", sem_leg])
    else:
        fc = f"[0:a]volume={float(original_db):.1f}dB[o];[1:a]apad[d];[o][d]amix=inputs=2:duration=first:normalize=0[a]"
        rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", v, "-i", dub, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", sem_leg])
    pj = caminho_saida(saida_palavras) if saida_palavras else out.with_name(out.stem + "_palavras.json")
    pj.write_text(json.dumps({"arquivo": str(sem_leg), "origem": "dublagem", "voz": voz_nome(voz, idioma), "idioma": idioma, "palavras": palavras, "segmentos": _segmentos(palavras)}, ensure_ascii=False, indent=1), encoding="utf-8")
    ass = srt_out = None
    if estilo:
        ass = trab / "legenda.ass"; srt_out = out.with_suffix(".srt")
        leg_mod.gerar_legenda(pj, ass, estilo, formato=formato, saida_srt=srt_out)
        montagem.montar(sem_leg, out, formato=formato, legenda_ass=ass, resolucao=resolucao, preset="veryfast")
    else:
        shutil.copy2(sem_leg, out)
    return {"video": str(out), "duracao_s": info_midia(out)["duracao_s"], "n_blocos": len(blocos), "acelerados": acelerados, "atraso_max_s": round(atraso_max, 2),
            "velocidade": velocidade_usada, "velocidade_automatica": velocidade_usada != int(velocidade),
            "voz": voz_nome(voz, idioma), "original_db": original_db, "palavras_json": str(pj), "srt": str(srt_out) if srt_out else None, "trabalho": str(trab)}
