import os, time
from pathlib import Path
from .util import FFMPEG, caminho, caminho_saida, caminho_previa, rodar, info_midia, ErroFerramenta, CRF_PREVIA

ALVOS = {("9x16", "720p"): (720, 1280), ("9x16", "1080p"): (1080, 1920), ("16x9", "720p"): (1280, 720),
         ("16x9", "1080p"): (1920, 1080), ("1x1", "720p"): (720, 720), ("1x1", "1080p"): (1080, 1080)}
FONTES_PADRAO = Path(__file__).resolve().parents[3] / "fontes"


def _esc(p):
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def montar(video, saida_video, formato="9x16", legenda_ass=None, resolucao="1080p", fps=30, crf=20, fontes_dir=None,
           enquadramento="auto", preset="medium", previa=False):
    """previa=True (10/11/2026): render barato em 720p (crf mais alto, fps igual) para o arquivo `<saida>_previa`, para a pessoa aprovar antes do 1080p.
    O resultado ganha `previa`, `resolucao` e `tempo_s`; nada mais muda."""
    t0 = time.monotonic()
    v = caminho(video); info = info_midia(v)
    if previa:
        resolucao = "720p"; crf = max(int(crf), CRF_PREVIA); preset = "veryfast"; saida_video = caminho_previa(saida_video)
    if (formato, resolucao) not in ALVOS:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    W, H = ALVOS[(formato, resolucao)]
    if enquadramento == "auto":
        # orientação diferente da saída (vertical → horizontal ou vice-versa): fundo desfocado em vez de cortar o quadro
        src = (info["largura"] or W) / (info["altura"] or H); alvo = W / H
        enquadramento = "desfocado" if (src > 1) != (alvo > 1) and formato != "1x1" else "centro"
    leg = ""
    if legenda_ass:
        fd = Path(fontes_dir) if fontes_dir else FONTES_PADRAO
        leg = f",subtitles='{_esc(caminho(legenda_ass))}':fontsdir='{_esc(fd)}'"
    if enquadramento == "centro":
        filtro = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}{leg}[v]"
    elif enquadramento == "bordas":
        filtro = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=#000921{leg}[v]"
    elif enquadramento == "desfocado":
        filtro = (f"[0:v]split=2[fundo][frente];[fundo]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"boxblur=luma_radius=40:luma_power=2,eq=brightness=-0.15[bg];[frente]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
                  f"[bg][fg]overlay=(W-w)/2:(H-h)/2{leg}[v]")
    else:
        raise ErroFerramenta("enquadramento deve ser 'auto', 'centro', 'bordas' ou 'desfocado'")
    out = caminho_saida(saida_video)
    cmd = [FFMPEG, "-y", "-hide_banner", "-nostats", "-i", v, "-filter_complex", filtro, "-map", "[v]"]
    cmd += (["-map", "0:a?"] if info["tem_audio"] else [])
    cmd += ["-r", str(fps), "-c:v", "libx264",
           "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += (["-c:a", "aac", "-b:a", "160k"] if info["tem_audio"] else ["-an"])
    rodar(cmd + [out])
    o = info_midia(out)
    res = {"video": str(out), "largura": o["largura"], "altura": o["altura"], "duracao_s": o["duracao_s"], "tamanho_mb": o["tamanho_mb"],
           "legenda_queimada": bool(legenda_ass), "enquadramento": enquadramento}
    if previa:
        res |= {"previa": True, "resolucao": f"{o['largura']}x{o['altura']}", "tempo_s": round(time.monotonic() - t0, 1)}
    return res


def montar_dividido(video_rosto, video_tela, saida_video, formato="9x16", resolucao="1080p", proporcao_rosto=0.42, audio="rosto", inicio_tela_s=0.0,
                    legenda_ass=None, fps=30, crf=20, preset="medium", fontes_dir=None, cor_fundo="#000921"):
    """Tela dividida: rosto (câmera) + tela (gravação do OBS/print em vídeo) no mesmo quadro, estilo tutorial.
    9x16 e 1x1: rosto em cima (proporcao_rosto da altura, recortado no centro) e tela embaixo (inteira, com faixas marinho se sobrar);
    16x9: rosto à esquerda (proporcao_rosto da largura) e tela à direita. audio: rosto | tela | mix. inicio_tela_s desloca a tela (positivo = começa mais tarde;
    negativo = pula o começo dela). A duração é a do vídeo do rosto. Legenda ASS opcional queimada por cima."""
    vr = caminho(video_rosto); vt = caminho(video_tela); ir = info_midia(vr); it = info_midia(vt)
    if (formato, resolucao) not in ALVOS:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    if not 0.2 <= float(proporcao_rosto) <= 0.7:
        raise ErroFerramenta("proporcao_rosto deve ficar entre 0.2 e 0.7")
    if audio not in ("rosto", "tela", "mix"):
        raise ErroFerramenta("audio deve ser rosto, tela ou mix")
    W, H = ALVOS[(formato, resolucao)]; p = float(proporcao_rosto); dur = ir["duracao_s"]
    leg = ""
    if legenda_ass:
        fd = Path(fontes_dir) if fontes_dir else FONTES_PADRAO
        leg = f",subtitles='{_esc(caminho(legenda_ass))}':fontsdir='{_esc(fd)}'"
    off = float(inicio_tela_s or 0.0)
    tela_in = f"[1:v]setpts=PTS-STARTPTS,tpad=start_duration={off:.3f}:color={cor_fundo}" if off > 0 else "[1:v]setpts=PTS-STARTPTS"
    if formato == "16x9":
        wr = int(round(W * p / 2) * 2); wt = W - wr
        filtro = (f"[0:v]scale={wr}:{H}:force_original_aspect_ratio=increase,crop={wr}:{H},setsar=1[r];"
                  f"{tela_in},scale={wt}:{H}:force_original_aspect_ratio=decrease,pad={wt}:{H}:(ow-iw)/2:(oh-ih)/2:color={cor_fundo},setsar=1[t];"
                  f"[r][t]hstack=inputs=2:shortest=1{leg}[v]")
        layout = {"rosto": {"x": 0, "y": 0, "w": wr, "h": H}, "tela": {"x": wr, "y": 0, "w": wt, "h": H}}
    else:
        hr = int(round(H * p / 2) * 2); ht = H - hr
        filtro = (f"[0:v]scale={W}:{hr}:force_original_aspect_ratio=increase,crop={W}:{hr},setsar=1[r];"
                  f"{tela_in},scale={W}:{ht}:force_original_aspect_ratio=decrease,pad={W}:{ht}:(ow-iw)/2:(oh-ih)/2:color={cor_fundo},setsar=1[t];"
                  f"[r][t]vstack=inputs=2:shortest=1{leg}[v]")
        layout = {"rosto": {"x": 0, "y": 0, "w": W, "h": hr}, "tela": {"x": 0, "y": hr, "w": W, "h": ht}}
    out = caminho_saida(saida_video)
    cmd = [FFMPEG, "-y", "-hide_banner", "-nostats", "-i", vr]
    cmd += (["-ss", f"{-off:.3f}"] if off < 0 else []) + ["-i", vt, "-filter_complex", filtro, "-map", "[v]"]
    tem_r, tem_t = ir["tem_audio"], it["tem_audio"]
    if audio == "mix" and tem_r and tem_t:
        cmd[cmd.index("-filter_complex") + 1] = filtro + f";[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]"; cmd += ["-map", "[a]"]
    elif audio == "tela" and tem_t:
        cmd += ["-map", "1:a"]
    elif tem_r:
        cmd += ["-map", "0:a"]
    cmd += ["-t", f"{dur:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += (["-c:a", "aac", "-b:a", "160k"] if (tem_r or tem_t) else ["-an"])
    rodar(cmd + [out])
    o = info_midia(out)
    return {"video": str(out), "largura": o["largura"], "altura": o["altura"], "duracao_s": o["duracao_s"], "tamanho_mb": o["tamanho_mb"], "layout": layout,
            "audio": audio, "inicio_tela_s": off, "legenda_queimada": bool(legenda_ass),
            "dica": "legenda: use posicao 'baixa' do estilo (cai sobre a tela) ou gere o ASS com formato igual ao da saída; para alinhar as duas gravações use sincronizar_audio e passe o deslocamento em inicio_tela_s"}


# --- Formatos que engajam (02/11/2026): rosto em bolha sobre a tela (PiP) e antes/depois ------------------------------------------------

def montar_pip(video_tela, video_rosto, saida_video, formato="9x16", resolucao="1080p", tamanho=0.34, posicao="inferior-direita", forma="circulo",
               audio="rosto", inicio_tela_s=0.0, legenda_ass=None, fps=30, crf=20, preset="medium", fontes_dir=None, cor_fundo="#000921", cor_borda="#F79615"):
    """Tela cheia (gravação do OBS, print em vídeo) com o rosto do Thiago numa bolha por cima (tutorial "olha a tela"): forma circulo (borda laranja) ou
    cartao (cantos 20 px). tamanho = fração da largura do quadro (0,2–0,5). posicao: inferior-direita | inferior-esquerda | superior-direita | superior-esquerda.
    audio: rosto | tela | mix. inicio_tela_s desloca a tela. Duração = a do vídeo do rosto. Legenda ASS opcional (use posicao 'baixa' sem bater na bolha: prefira bolha em cima)."""
    vt = caminho(video_tela); vr = caminho(video_rosto); ir = info_midia(vr); it = info_midia(vt)
    if (formato, resolucao) not in ALVOS:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    if not 0.2 <= float(tamanho) <= 0.5:
        raise ErroFerramenta("tamanho deve ficar entre 0.2 e 0.5 (fração da largura)")
    if posicao not in ("inferior-direita", "inferior-esquerda", "superior-direita", "superior-esquerda"):
        raise ErroFerramenta("posicao inválida")
    if forma not in ("circulo", "cartao") or audio not in ("rosto", "tela", "mix"):
        raise ErroFerramenta("forma deve ser circulo ou cartao; audio rosto, tela ou mix")
    W, H = ALVOS[(formato, resolucao)]; dur = ir["duracao_s"]
    d = int(round(W * float(tamanho) / 2) * 2); margem = int(W * 0.04); borda = max(4, int(d * 0.03))
    x = W - d - margem if posicao.endswith("direita") else margem
    y = H - d - int(H * 0.06) if posicao.startswith("inferior") else int(H * 0.05)
    off = float(inicio_tela_s or 0.0)
    tela_in = f"[0:v]setpts=PTS-STARTPTS,tpad=start_duration={off:.3f}:color={cor_fundo}" if off > 0 else "[0:v]setpts=PTS-STARTPTS"
    leg = ""
    if legenda_ass:
        fd = Path(fontes_dir) if fontes_dir else FONTES_PADRAO
        leg = f",subtitles='{_esc(caminho(legenda_ass))}':fontsdir='{_esc(fd)}'"
    r_int = d // 2 - borda
    if forma == "circulo":
        mascara = (f"[1:v]scale={d}:{d}:force_original_aspect_ratio=increase,crop={d}:{d},setsar=1,format=rgba,"
                   f"geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='if(lte(hypot(X-{d/2},Y-{d/2}),{r_int}),255,0)'[rosto];"
                   f"color=c={cor_borda}:s={d}x{d},format=rgba,geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='if(lte(hypot(X-{d/2},Y-{d/2}),{d/2}),255,0)'[anel];"
                   f"[anel][rosto]overlay=0:0:format=auto[bolha];")
    else:
        rc = 20
        mascara = (f"[1:v]scale={d}:{d}:force_original_aspect_ratio=increase,crop={d}:{d},setsar=1,format=rgba,"
                   f"geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='if(lte(hypot(max(abs(X-{d/2})-({d/2}-{rc}),0),max(abs(Y-{d/2})-({d/2}-{rc}),0)),{rc}),255,0)'[bolha];")
    filtro = (f"{tela_in},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={cor_fundo},setsar=1[t];"
              f"{mascara}[t][bolha]overlay={x}:{y}:shortest=1{leg}[v]")
    out = caminho_saida(saida_video)
    cmd = [FFMPEG, "-y", "-hide_banner", "-nostats"] + (["-ss", f"{-off:.3f}"] if off < 0 else []) + ["-i", vt, "-i", vr, "-filter_complex", filtro, "-map", "[v]"]
    tem_r, tem_t = ir["tem_audio"], it["tem_audio"]
    if audio == "mix" and tem_r and tem_t:
        cmd[cmd.index("-filter_complex") + 1] = filtro + ";[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=2[a]"; cmd += ["-map", "[a]"]
    elif audio == "tela" and tem_t:
        cmd += ["-map", "0:a"]
    elif tem_r:
        cmd += ["-map", "1:a"]
    cmd += ["-t", f"{dur:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += (["-c:a", "aac", "-b:a", "160k"] if (tem_r or tem_t) else ["-an"])
    rodar(cmd + [out])
    o = info_midia(out)
    return {"video": str(out), "largura": o["largura"], "altura": o["altura"], "duracao_s": o["duracao_s"], "tamanho_mb": o["tamanho_mb"],
            "bolha": {"x": x, "y": y, "diametro": d, "forma": forma, "posicao": posicao}, "audio": audio, "legenda_queimada": bool(legenda_ass),
            "dica": "legenda no estilo com posicao 'baixa' bate na bolha inferior: use a bolha em cima (superior-direita) ou a legenda 'centro'"}


def montar_antes_depois(video_antes, video_depois, saida_video, formato="9x16", resolucao="1080p", rotulo_antes="ANTES", rotulo_depois="DEPOIS", modo="auto",
                        audio="depois", legenda_ass=None, fps=30, crf=20, preset="medium", fontes_dir=None, cor_fundo="#000921", cor_destaque="#F79615"):
    """Antes/depois no mesmo quadro (setup, luz, áudio, cenário): 9x16 e 1x1 empilham (antes em cima, depois embaixo); 16x9 põe lado a lado; modo
    força 'empilhado' ou 'lado_a_lado'. Rótulos em pílula (antes em cinza, depois em laranja). audio: antes | depois | mix. Duração = a do mais curto."""
    va = caminho(video_antes); vd = caminho(video_depois); ia = info_midia(va); idp = info_midia(vd)
    if (formato, resolucao) not in ALVOS:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    if modo not in ("auto", "empilhado", "lado_a_lado") or audio not in ("antes", "depois", "mix"):
        raise ErroFerramenta("modo deve ser auto, empilhado ou lado_a_lado; audio antes, depois ou mix")
    W, H = ALVOS[(formato, resolucao)]
    empilhado = (formato != "16x9") if modo == "auto" else (modo == "empilhado")
    fd = Path(fontes_dir) if fontes_dir else FONTES_PADRAO; fonte = _esc(fd / "Inter-ExtraBold.ttf")
    leg = f",subtitles='{_esc(caminho(legenda_ass))}':fontsdir='{_esc(fd)}'" if legenda_ass else ""
    tam = int((H if empilhado else W) * 0.028)
    def rotulo(cor_caixa, cor_texto, texto, x="(w-tw)/2", y="h*0.04"):
        return f"drawtext=fontfile='{fonte}':text='{texto}':fontsize={tam}:fontcolor={cor_texto}:box=1:boxcolor={cor_caixa}:boxborderw={max(6, tam // 2)}:x={x}:y={y}"
    if empilhado:
        hh = H // 2
        filtro = (f"[0:v]scale={W}:{hh}:force_original_aspect_ratio=increase,crop={W}:{hh},setsar=1,{rotulo('#272A33@0.85', 'white', rotulo_antes)}[a];"
                  f"[1:v]scale={W}:{hh}:force_original_aspect_ratio=increase,crop={W}:{hh},setsar=1,{rotulo(cor_destaque, cor_fundo, rotulo_depois)}[d];"
                  f"[a][d]vstack=inputs=2:shortest=1,drawbox=x=0:y={hh - 3}:w={W}:h=6:color={cor_destaque}:t=fill{leg}[v]")
        layout = {"antes": {"x": 0, "y": 0, "w": W, "h": hh}, "depois": {"x": 0, "y": hh, "w": W, "h": H - hh}}
    else:
        ww = W // 2
        filtro = (f"[0:v]scale={ww}:{H}:force_original_aspect_ratio=increase,crop={ww}:{H},setsar=1,{rotulo('#272A33@0.85', 'white', rotulo_antes)}[a];"
                  f"[1:v]scale={ww}:{H}:force_original_aspect_ratio=increase,crop={ww}:{H},setsar=1,{rotulo(cor_destaque, cor_fundo, rotulo_depois)}[d];"
                  f"[a][d]hstack=inputs=2:shortest=1,drawbox=x={ww - 3}:y=0:w=6:h={H}:color={cor_destaque}:t=fill{leg}[v]")
        layout = {"antes": {"x": 0, "y": 0, "w": ww, "h": H}, "depois": {"x": ww, "y": 0, "w": W - ww, "h": H}}
    out = caminho_saida(saida_video)
    cmd = [FFMPEG, "-y", "-hide_banner", "-nostats", "-i", va, "-i", vd, "-filter_complex", filtro, "-map", "[v]"]
    tem_a, tem_d = ia["tem_audio"], idp["tem_audio"]
    if audio == "mix" and tem_a and tem_d:
        cmd[cmd.index("-filter_complex") + 1] = filtro + ";[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=2[a]"; cmd += ["-map", "[a]"]
    elif audio == "antes" and tem_a:
        cmd += ["-map", "0:a"]
    elif tem_d:
        cmd += ["-map", "1:a"]
    elif tem_a:
        cmd += ["-map", "0:a"]
    dur = min(ia["duracao_s"], idp["duracao_s"])
    cmd += ["-t", f"{dur:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += (["-c:a", "aac", "-b:a", "160k"] if (tem_a or tem_d) else ["-an"])
    rodar(cmd + [out])
    o = info_midia(out)
    return {"video": str(out), "largura": o["largura"], "altura": o["altura"], "duracao_s": o["duracao_s"], "tamanho_mb": o["tamanho_mb"], "layout": layout, "empilhado": empilhado, "audio": audio, "legenda_queimada": bool(legenda_ass)}


DIREITOS_REACT = ("proprio", "autorizado", "licenca")


def _texto_ff(t):
    return str(t).replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def montar_react(video_reacao, video_referencia, saida_video, credito, direitos, formato="9x16", resolucao="1080p", layout="empilhado",
                 volume_referencia=0.35, inicio_referencia_s=0.0, legenda_ass=None, fps=30, crf=20, preset="medium", fontes_dir=None, cor_fundo="#000921"):
    """React a uma referência (03/11/2026). Só com direitos: `direitos` = proprio | autorizado | licenca e `credito` (ex.: "@perfil") sempre na tela.
    layout empilhado: referência em cima, rosto embaixo (9x16/1x1; 16x9 lado a lado); layout bolha: referência cheia e rosto em bolha (montar_pip).
    Áudio: fala de quem reage + referência baixinha (volume_referencia). Duração = a do vídeo da reação."""
    if (direitos or "").strip().lower() not in DIREITOS_REACT:
        raise ErroFerramenta("react só com direitos: informe direitos = proprio, autorizado ou licenca (vídeo de terceiro sem autorização não entra)")
    if not (credito or "").strip():
        raise ErroFerramenta("informe o crédito da referência (ex.: @perfil): ele fica na tela o tempo todo")
    if layout not in ("empilhado", "bolha"):
        raise ErroFerramenta("layout deve ser empilhado ou bolha")
    if (formato, resolucao) not in ALVOS:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    vr = caminho(video_reacao); vf = caminho(video_referencia); ir = info_midia(vr); ifr = info_midia(vf)
    W, H = ALVOS[(formato, resolucao)]; dur = ir["duracao_s"]; out = caminho_saida(saida_video)
    fd = Path(fontes_dir) if fontes_dir else FONTES_PADRAO; fonte = _esc(fd / "Inter-Bold.ttf")
    tam = max(18, int(W * 0.032)); pad = int(tam * 0.5)
    rotulo = f"drawtext=fontfile='{fonte}':text='{_texto_ff('Fonte: ' + credito.strip())}':fontsize={tam}:fontcolor=white:box=1:boxcolor=0x000921@0.78:boxborderw={pad}:x={int(W * 0.04)}:y={int(H * 0.03)}"
    leg = f",subtitles='{_esc(caminho(legenda_ass))}':fontsdir='{_esc(fd)}'" if legenda_ass else ""
    off = max(0.0, float(inicio_referencia_s or 0))
    if layout == "bolha":
        tmp = out.with_name(out.stem + ".pip.mp4")
        montar_pip(vf, vr, tmp, formato=formato, resolucao=resolucao, posicao="inferior-direita", audio="mix" if ifr["tem_audio"] else "rosto", inicio_tela_s=-off if off else 0.0,
                   fps=fps, crf=crf, preset=preset, fontes_dir=fontes_dir)
        rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", tmp, "-vf", rotulo + leg, "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out])
        tmp.unlink(missing_ok=True)
    else:
        lado = formato == "16x9"; w2, h2 = (W // 2, H) if lado else (W, H // 2)
        filtro = (f"[1:v]setpts=PTS-STARTPTS,scale={w2}:{h2}:force_original_aspect_ratio=decrease,pad={w2}:{h2}:(ow-iw)/2:(oh-ih)/2:color={cor_fundo},setsar=1[ref];"
                  f"[0:v]scale={w2}:{h2}:force_original_aspect_ratio=increase,crop={w2}:{h2},setsar=1[ros];"
                  f"[ref][ros]{'hstack' if lado else 'vstack'}=inputs=2,{rotulo}{leg}[v]")
        cmd = [FFMPEG, "-y", "-hide_banner", "-nostats", "-i", vr] + (["-ss", f"{off:.3f}"] if off else []) + ["-i", vf]
        if ir["tem_audio"] and ifr["tem_audio"]:
            filtro += f";[1:a]volume={float(volume_referencia)}[ra];[0:a][ra]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"; amap = ["-map", "[a]"]
        else:
            amap = ["-map", "0:a"] if ir["tem_audio"] else (["-map", "1:a"] if ifr["tem_audio"] else [])
        cmd += ["-filter_complex", filtro, "-map", "[v]", *amap, "-t", f"{dur:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        cmd += (["-c:a", "aac", "-b:a", "160k"] if amap else ["-an"])
        rodar(cmd + [out])
    o = info_midia(out)
    return {"video": str(out), "largura": o["largura"], "altura": o["altura"], "duracao_s": o["duracao_s"], "tamanho_mb": o["tamanho_mb"], "layout": layout,
            "credito": credito.strip(), "direitos": direitos.strip().lower(), "legenda_queimada": bool(legenda_ass),
            "aviso": "registre a autorização/licença da referência em ## Pendências se não estiver no pedido"}

