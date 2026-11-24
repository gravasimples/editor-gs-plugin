"""Testes isolados de voz.py (narrar, montar_locucao, dublar) SEM rede: a síntese é trocada por um dublê que gera um tom com ffmpeg e tempos de palavra sintéticos.
Rodar com EDITOR_GS_REDE=1 para incluir uma narração real curta pelo edge-tts. Tudo em pasta temporária."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import voz
from editor_video.util import ErroFerramenta, info_midia, FFMPEG

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def sint_falso(texto, vz, rate, saida_mp3):
    """0,35 s por palavra: tom de 440 Hz com a duração total; palavras sem pontuação como o edge-tts faz."""
    toks = texto.split(); dur = 0.35 * len(toks) + 0.2
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur:.2f}", "-ar", "24000", "-b:a", "48k", saida_mp3], check=True)
    return [{"palavra": re.sub(r"[^\wÀ-ÿ]+", "", t), "inicio": round(0.1 + i * 0.35, 3), "fim": round(0.1 + i * 0.35 + 0.3, 3), "prob": 1.0} for i, t in enumerate(toks)]

with tempfile.TemporaryDirectory(prefix="editor-gs-voz-", ignore_cleanup_errors=True) as tmp:
    tmp = Path(tmp); os.chdir(tmp)
    estilo = json.loads((RAIZ / "estilos" / "padrao.json").read_text(encoding="utf-8"))
    check(voz.voz_nome("", "pt") == "pt-BR-AntonioNeural" and voz.voz_nome("en-ava") == "en-US-AvaMultilingualNeural" and voz.voz_nome("pt-BR-FranciscaNeural") == "pt-BR-FranciscaNeural" and voz.voz_nome("", "en") == "en-US-AndrewMultilingualNeural", "nome da voz por apelido, idioma ou ShortName")
    check(len(voz.listar_vozes()["vozes"]) >= 8, "listar_vozes")

    # narrar
    r = voz.narrar("Olha só, o OBS trava a webcam. Pronto, tá gravando!", tmp / "n.wav", saida_palavras=tmp / "n.json", _sint=sint_falso)
    check(Path(r["audio"]).exists() and r["duracao_s"] > 2 and r["n_palavras"] == 10, f"narrar grava o áudio convertido e devolve palavras ({r['n_palavras']}, {r['duracao_s']} s)")
    pal = [p["palavra"] for p in r["palavras"]]
    check(pal[:3] == ["Olha", "só,", "o"] and pal[-1] == "gravando!", f"pontuação do texto é devolvida às palavras ({pal})")
    d = json.loads((tmp / "n.json").read_text(encoding="utf-8"))
    check(d["origem"] == "tts" and len(d["segmentos"]) == 2 and d["segmentos"][0]["texto"].endswith("webcam."), "palavras.json tem segmentos por frase")
    try:
        voz.narrar("   ", tmp / "x.mp3", _sint=sint_falso); check(False, "texto vazio dá erro")
    except ErroFerramenta:
        check(True, "texto vazio dá erro")
    (tmp / "entrada").mkdir()
    try:
        voz.narrar("oi", tmp / "entrada" / "x.mp3", _sint=sint_falso); check(False, "não grava em entrada/")
    except ErroFerramenta:
        check(True, "não grava em entrada/")

    # cenas: print 16:9 (fundo desfocado) + slide 9:16 + trecho de vídeo
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=1:d=1", "-frames:v", "1", str(tmp / "print.png")], check=True)
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x000921:size=1080x1920:rate=1:d=1", "-frames:v", "1", str(tmp / "slide.png")], check=True)
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:d=3", "-f", "lavfi", "-i", "sine=frequency=300:duration=3", "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(tmp / "clipe.mp4")], check=True)
    cenas = [{"texto": "Primeira cena com um print do OBS.", "imagem": str(tmp / "print.png")}, {"texto": "Segunda cena, slide da marca.", "imagem": str(tmp / "slide.png"), "zoom": 1.0},
             {"texto": "Terceira cena vem de um vídeo.", "video": str(tmp / "clipe.mp4"), "inicio_s": 0.5}]
    (tmp / "cenas.json").write_text(json.dumps(cenas), encoding="utf-8")
    r = voz.montar_locucao(tmp / "cenas.json", tmp / "saida" / "final_9x16.mp4", formato="9x16", resolucao="720p", estilo=estilo, _sint=sint_falso)
    info = info_midia(r["video"])
    check(info["largura"] == 720 and info["altura"] == 1280 and info["tem_audio"], f"vídeo 9x16 720p com áudio ({info['largura']}x{info['altura']})")
    esperado = sum(0.35 * len(c["texto"].split()) + 0.2 + 0.4 for c in cenas)
    check(abs(r["duracao_s"] - esperado) < 0.8 and r["n_cenas"] == 3, f"duração segue a narração + pausa ({r['duracao_s']} ≈ {esperado:.1f})")
    check(r["cenas"][1]["inicio"] > 2 and r["cenas"][2]["inicio"] > r["cenas"][1]["fim"] - 0.01, "cenas em sequência com início e fim")
    pj = json.loads(Path(r["palavras_json"]).read_text(encoding="utf-8"))
    check(pj["palavras"][7]["inicio"] > r["cenas"][1]["inicio"] and len(pj["segmentos"]) == 3, "palavras deslocadas para o tempo do vídeo")
    check(Path(r["srt"]).exists() and "Segunda cena" in Path(r["srt"]).read_text(encoding="utf-8") and Path(r["legenda_ass"]).exists(), "SRT e ASS gerados")
    import pysubs2
    ev = sorted(pysubs2.load(r["srt"]), key=lambda e: e.start)
    check(len(ev) >= 3 and all(a.end <= b.start for a, b in zip(ev, ev[1:])), f"linhas da legenda não se sobrepõem com palavras contíguas do TTS ({len(ev)} linhas)")
    check((tmp / "saida" / "_trabalho").exists() and not any(p.suffix == ".mp3" for p in (tmp / "saida").iterdir()), "áudios de cena ficam em _trabalho/")
    # J-cut: a cena anterior segura jcut_s já com a fala seguinte; duração total e áudio não mudam
    # cache de narração por cena: remontar com as mesmas falas não sintetiza de novo; cena alterada sintetiza só ela
    chamadas = []
    def sint_contado(texto, vz, rate, saida_mp3):
        chamadas.append(texto); return sint_falso(texto, vz, rate, saida_mp3)
    r2 = voz.montar_locucao(tmp / "cenas.json", tmp / "saida" / "final_9x16.mp4", formato="9x16", resolucao="720p", estilo=estilo, _sint=sint_contado)
    check(chamadas == [] and r2.get("cenas_do_cache") == len(cenas) and (tmp / "saida" / "_trabalho" / "cache_narracao").exists(), f"remontagem igual: 0 sínteses, {r2.get('cenas_do_cache')} cenas do cache")
    cenas_alt = json.loads(json.dumps(cenas)); cenas_alt[0]["texto"] = "Fala nova só na primeira cena."
    (tmp / "cenas-alt.json").write_text(json.dumps(cenas_alt), encoding="utf-8")
    r3 = voz.montar_locucao(tmp / "cenas-alt.json", tmp / "saida" / "final_9x16.mp4", formato="9x16", resolucao="720p", estilo=estilo, _sint=sint_contado)
    check(chamadas == ["Fala nova só na primeira cena."] and r3.get("cenas_do_cache") == len(cenas) - 1, "só a cena alterada é narrada de novo")
    rj = voz.montar_locucao(tmp / "cenas.json", tmp / "saida" / "jcut.mp4", formato="9x16", resolucao="720p", estilo=None, transicao="nenhuma", jcut_s=0.3, _sint=sint_falso)
    c1 = info_midia(Path(rj["trabalho"]) / "cena-01.mp4"); c2 = info_midia(Path(rj["trabalho"]) / "cena-02.mp4")
    check(rj["jcut_s"] == 0.3 and abs(rj["duracao_s"] - r["duracao_s"]) < 0.15, f"J-cut mantém a duração total ({rj['duracao_s']} vs {r['duracao_s']})")
    check(abs(c1["duracao_s"] - (rj["cenas"][0]["duracao_s"] + 0.3)) < 0.1 and abs(c2["duracao_s"] - rj["cenas"][1]["duracao_s"]) < 0.1, f"clipe 1 ganha 0,3 s e o do meio mantém (ganha e perde) ({c1['duracao_s']:.2f}, {c2['duracao_s']:.2f})")
    check(abs(rj["cenas"][0]["corte_visual_s"] - (rj["cenas"][0]["fim"] + 0.3)) < 0.01 and rj["cenas"][-1]["corte_visual_s"] is None, "corte visual registrado 0,3 s depois do fim da fala da cena")
    rj0 = voz.montar_locucao(cenas[:1], tmp / "saida" / "jcut1.mp4", formato="9x16", resolucao="720p", estilo=None, jcut_s=0.3, _sint=sint_falso)
    check(rj0["jcut_s"] == 0.0, "com uma cena só o J-cut é ignorado")
    r2 = voz.montar_locucao(cenas[:1], tmp / "saida" / "sem_legenda_16x9.mp4", formato="16x9", resolucao="720p", estilo=None, pausa_s=0.0, _sint=sint_falso)
    i2 = info_midia(r2["video"]); check(i2["largura"] == 1280 and i2["altura"] == 720 and r2["legenda_ass"] is None, "16x9 sem legenda")
    try:
        voz.montar_locucao([{"texto": "sem imagem"}], tmp / "saida" / "x.mp4", resolucao="720p", _sint=sint_falso); check(False, "cena sem imagem nem vídeo dá erro")
    except ErroFerramenta as e:
        check("imagem" in str(e), "cena sem imagem nem vídeo dá erro")
    try:
        voz.montar_locucao([], tmp / "saida" / "x.mp4", resolucao="720p", _sint=sint_falso); check(False, "sem cenas dá erro")
    except ErroFerramenta:
        check(True, "sem cenas dá erro")

    # dublar: vídeo de 6 s com voz original (tom), SRT de 3 blocos, o segundo longo demais
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=30:d=6", "-f", "lavfi", "-i", "sine=frequency=200:duration=6", "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(tmp / "base.mp4")], check=True)
    (tmp / "en.srt").write_text("1\n00:00:00,500 --> 00:00:02,000\nTurn on Studio Mode\n\n2\n00:00:02,000 --> 00:00:03,000\nthis block has far too many words to fit in one second of video\n\n3\n00:00:04,500 --> 00:00:05,800\nDone, recording.\n", encoding="utf-8")
    r = voz.dublar(tmp / "base.mp4", tmp / "en.srt", tmp / "saida" / "final_9x16_en_dub.mp4", resolucao="720p", idioma="en", estilo=estilo, _sint=sint_falso)
    i3 = info_midia(r["video"])
    check(i3["tem_audio"] and abs(i3["duracao_s"] - 6) < 0.6 and i3["largura"] == 720, f"dublado mantém o vídeo ({i3['duracao_s']} s)")
    check(r["n_blocos"] == 3 and r["acelerados"] >= 1 and r["atraso_max_s"] > 0, f"bloco longo é acelerado e o atraso é medido ({r['acelerados']}, {r['atraso_max_s']} s)")
    pj = json.loads(Path(r["palavras_json"]).read_text(encoding="utf-8"))
    check(abs(pj["palavras"][0]["inicio"] - 0.6) < 0.05 and pj["palavras"][-1]["inicio"] >= 4.5, "palavras dubladas começam no tempo de cada bloco")
    check(Path(r["srt"]).exists() and "Studio Mode" in Path(r["srt"]).read_text(encoding="utf-8"), "SRT da dublagem no idioma novo")
    r4 = voz.dublar(tmp / "base.mp4", tmp / "en.srt", tmp / "saida" / "sem_original.mp4", resolucao="720p", idioma="en", original_db=None, estilo=None, _sint=sint_falso)
    check(r4["original_db"] is None and info_midia(r4["video"])["tem_audio"], "original_db=None tira a voz original")
    # velocidade automática: dublê que respeita o rate (+N% encurta a fala); SRT apertado em todos os blocos → renarra mais rápido e acelera menos
    def sint_rate(texto, vz, rate, saida_mp3):
        pal = sint_falso(texto, vz, rate, saida_mp3); f = 1 + int(rate.rstrip("%")) / 100
        dur = (0.35 * len(texto.split()) + 0.2) / f
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur:.2f}", "-ar", "24000", "-b:a", "48k", saida_mp3], check=True)
        return [{**p, "inicio": round(p["inicio"] / f, 3), "fim": round(p["fim"] / f, 3)} for p in pal]
    (tmp / "apertado.srt").write_text("1\n00:00:00,000 --> 00:00:01,500\none two three four five\n\n2\n00:00:01,500 --> 00:00:03,000\nsix seven eight nine ten\n\n3\n00:00:03,000 --> 00:00:04,500\neleven twelve thirteen fourteen fifteen\n\n4\n00:00:04,500 --> 00:00:06,000\nsixteen seventeen\n", encoding="utf-8")
    r5 = voz.dublar(tmp / "base.mp4", tmp / "apertado.srt", tmp / "saida" / "auto.mp4", resolucao="720p", idioma="en", estilo=None, _sint=sint_rate)
    r6 = voz.dublar(tmp / "base.mp4", tmp / "apertado.srt", tmp / "saida" / "sem_auto.mp4", resolucao="720p", idioma="en", estilo=None, auto_velocidade=False, _sint=sint_rate)
    check(r5["velocidade_automatica"] and 5 <= r5["velocidade"] <= 20 and r6["velocidade"] == 0 and not r6["velocidade_automatica"], f"velocidade automática entra quando a maioria dos blocos não cabe (+{r5['velocidade']} %)")
    check(r5["acelerados"] <= r6["acelerados"] and r5["atraso_max_s"] <= r6["atraso_max_s"] + 0.01, f"com a voz mais rápida, menos blocos passam pelo atempo ({r5['acelerados']} ≤ {r6['acelerados']}; atraso {r5['atraso_max_s']} ≤ {r6['atraso_max_s']})")
    (tmp / "folgado.srt").write_text("1\n00:00:00,000 --> 00:00:02,500\nhello there\n\n2\n00:00:02,500 --> 00:00:05,000\nall good\n\n3\n00:00:05,000 --> 00:00:05,600\none two three four\n", encoding="utf-8")
    r7 = voz.dublar(tmp / "base.mp4", tmp / "folgado.srt", tmp / "saida" / "folgado.mp4", resolucao="720p", idioma="en", estilo=None, _sint=sint_rate)
    check(not r7["velocidade_automatica"] and r7["velocidade"] == 0, "SRT com só um bloco apertado (minoria) não muda a velocidade")
    try:
        voz.dublar(tmp / "base.mp4", tmp / "nao.srt", tmp / "saida" / "x.mp4", resolucao="720p", _sint=sint_falso); check(False, "SRT inexistente dá erro")
    except ErroFerramenta:
        check(True, "SRT inexistente dá erro")

    # transições (xfade na pausa), movimento alternado e cena `slide` (Remotion trocado por um dublê que gera um clipe de cor)
    def render_falso(composicao, props, saida):
        check(composicao == "CenaTexto" and props["titulo"] and props["largura"] == 720 and props["duracao_s"] > 1, f"render recebe CenaTexto com props ({props['titulo']!r}, {props['duracao_s']} s)")
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x0B193D:size={props['largura']}x{props['altura']}:rate={props['fps']}:d={props['duracao_s']:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(saida)], check=True)
        return Path(saida)
    def render_quebrado(composicao, props, saida):
        raise RuntimeError("sem chromium")
    cenas2 = [{"texto": "Abre com um slide animado de título.", "slide": {"titulo": "Sua webcam trava no OBS?", "destaque": "trava", "apoio": ["Desliga o driver antigo"], "selo": "Dica"}},
              {"texto": "Depois um print real do OBS.", "imagem": str(tmp / "print.png")},
              {"texto": "E fecha com um trecho de vídeo.", "video": str(tmp / "clipe.mp4"), "transicao": "circleopen"}]
    r = voz.montar_locucao(cenas2, tmp / "saida" / "trans.mp4", formato="9x16", resolucao="720p", estilo=estilo, transicao="auto", _sint=sint_falso, _render=render_falso)
    esperado = sum(0.35 * len(c["texto"].split()) + 0.2 + 0.4 for c in cenas2)
    check(abs(r["duracao_s"] - esperado) < 0.8, f"com xfade a duração continua a da narração + pausa ({r['duracao_s']} ≈ {esperado:.1f})")
    check(r["transicao"] == {"tipo": "auto", "duracao_s": 0.35} and r["cenas"][1]["transicao"] == "fade" and r["cenas"][2]["transicao"] == "circleopen" and r["cenas"][0]["transicao"] is None, f"transição auto por cena, com override na cena ({[c['transicao'] for c in r['cenas']]})")
    check([c["origem"] for c in r["cenas"]] == ["slide-remotion", "imagem", "video"] and [c["movimento"] for c in r["cenas"]] == ["parado", "sair", "parado"], f"origem e movimento por cena ({[(c['origem'], c['movimento']) for c in r['cenas']]})")
    check(r["capa_sugerida"]["cena"] == 2 and r["capa_sugerida"]["tipo"] == "imagem" and r["cenas"][1]["inicio"] < r["capa_sugerida"]["instante_s"] < r["cenas"][1]["fim"], f"capa sugerida na primeira cena real ({r['capa_sugerida']})")
    check(r["avisos"] == [] and (Path(r["trabalho"]) / "cena-01.slide.mp4").exists(), "slide animado renderizado em _trabalho sem avisos")
    pj = json.loads(Path(r["palavras_json"]).read_text(encoding="utf-8"))
    check(abs(pj["palavras"][0]["inicio"] - 0.1) < 0.05 and abs(pj["segmentos"][1]["inicio"] - r["cenas"][1]["inicio"]) < 0.01, "tempos das palavras não mudam com a transição (ela acontece na pausa)")
    r = voz.montar_locucao(cenas2[:1] + [{"texto": "Segundo slide, de fundo claro.", "slide": {"titulo": "Pronto, tá gravando", "fundo": "papel"}, "movimento": "entrar"}], tmp / "saida" / "so_slides.mp4", resolucao="720p", estilo=None, transicao="nenhuma", movimento="parado", _sint=sint_falso, _render=render_quebrado)
    check(r["transicao"]["duracao_s"] == 0 and r["transicao"]["tipo"] == "nenhuma" and Path(r["video"]).exists(), "transicao=nenhuma emenda por concat")
    check([c["origem"] for c in r["cenas"]] == ["slide-png", "slide-png"] and len(r["avisos"]) == 2 and "PNG" in r["avisos"][0] and (Path(r["trabalho"]) / "cena-02.slide.png").exists(), f"Remotion quebrado cai para slide PNG com aviso ({r['avisos'][0][:60]})")
    check(r["capa_sugerida"]["instante_s"] is None and "gerar_post_imagem" in r["capa_sugerida"]["dica"], "só slides: capa sugerida pede gerar_post_imagem / gerar_capa(imagem=)")
    check([c["movimento"] for c in r["cenas"]] == ["parado", "entrar"], f"movimento global parado e override por cena ({[c['movimento'] for c in r['cenas']]})")
    for ruim, kw in ((dict(transicao="explosao"), "transicao"), (dict(movimento="girar"), "movimento"), ):
        try:
            voz.montar_locucao(cenas[:2], tmp / "saida" / "x.mp4", resolucao="720p", estilo=None, _sint=sint_falso, **ruim); check(False, f"{kw} inválido dá erro")
        except ErroFerramenta as e:
            check(kw in str(e), f"{kw} inválido dá erro")
    try:
        voz.montar_locucao([{"texto": "sem título", "slide": {"apoio": ["x"]}}], tmp / "saida" / "x.mp4", resolucao="720p", estilo=None, _sint=sint_falso, _render=render_falso); check(False, "slide sem título dá erro")
    except ErroFerramenta as e:
        check("titulo" in str(e), "slide sem título dá erro")

    # capa a partir de uma imagem (sem quadro do vídeo)
    from editor_video import acabamento
    cp = acabamento.gerar_capa("", tmp / "saida" / "capa_img.png", "Webcam travada no OBS", destaque="travada", estilo=estilo, imagem=tmp / "print.png", posicao="baixo")
    check(cp["instante_s"] is None and cp["imagem"].endswith("print.png") and cp["largura"] == 1080 and cp["altura"] == 1920 and (tmp / "saida" / "capa_img.png").stat().st_size > 5000, f"gerar_capa(imagem=) sem vídeo ({cp['linhas']})")

    if os.environ.get("EDITOR_GS_REDE") == "1":
        r = voz.narrar("Olha só: o OBS trava a webcam quando o driver antigo fica ativo.", tmp / "real.mp3", saida_palavras=tmp / "real.json")
        check(r["duracao_s"] > 2 and r["n_palavras"] >= 10 and r["palavras"][0]["palavra"] == "Olha", f"narração real pelo edge-tts ({r['duracao_s']} s, {r['n_palavras']} palavras)")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
