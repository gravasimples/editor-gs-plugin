"""Portão técnico do Revisor (14/11/2026, item 2 da ordem autorizada): mede o vídeo final com ffmpeg e numpy, sem modelo e sem custo,
antes do Gemini. O Gemini assiste e julga sentido; isto aqui pega o que se mede: quadro preto, imagem parada, flash de 1 quadro, trecho mudo,
volume e pico fora do alvo, áudio e vídeo com durações diferentes, clique e salto de nível em cada emenda e palavra dita duas vezes.
Cada achado sai no mesmo formato dos problemas do Gemini (instante_s, gravidade, tipo, descricao, sugestao) com origem "medido"."""
import re, subprocess
import numpy as np
from .util import FFMPEG, FFPROBE, caminho, ler_json, normalizar, salvar_json, ALVO_LUFS

# limites por formato: imagem parada máxima (s), pausa muda máxima (s)
LIMITES = {"reels": (4.0, 0.7), "aula": (6.0, 1.8), "longo": (6.0, 1.2)}
PRETO_MIN_S = 0.03       # um quadro a 30 fps
LUFS_TOL = 1.5
PICO_MAX_DB = -1.0
DESSINCRONIA_S = 0.15
CLIQUE_DB = 12.0         # pico curto acima do entorno na emenda
SALTO_DB = 6.0           # diferença de nível da voz antes × depois da emenda
NATURAIS = {"que"}       # "o que que é isso": repetição da fala comum, não é refação
LADO_S = 0.25            # entorno do clique
NIVEL_LADO_S = 1.0       # janela do nível da voz


def _p(instante, gravidade, tipo, descricao, sugestao):
    return {"instante_s": round(float(instante), 2), "gravidade": gravidade, "tipo": tipo, "descricao": descricao, "sugestao": sugestao, "origem": "medido"}


def _ffmpeg_log(args, timeout=1800):
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", *args, "-f", "null", "-"], capture_output=True, text=True, timeout=timeout, errors="ignore")
    return r.stderr


def _duracoes(v):
    import json
    d = json.loads(subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(v)],
                                  capture_output=True, text=True, timeout=120).stdout or "{}")
    dur = lambda t: next((float(s["duration"]) for s in d.get("streams", []) if s.get("codec_type") == t and s.get("duration")), None)
    vs = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    fps = 30.0
    if vs.get("avg_frame_rate", "0/0") != "0/0":
        n, m = vs["avg_frame_rate"].split("/"); fps = float(n) / float(m) if float(m) else 30.0
    return dur("video"), dur("audio"), float(d.get("format", {}).get("duration") or 0), fps


def ler_video(log, parada_max_s, fps):
    """Lê o log de blackdetect + freezedetect + showinfo (mudanças de cena) e devolve os achados de imagem."""
    out = []
    cenas = sorted(float(x) for x in re.findall(r"pts_time:([\d.]+)", log))
    perto = lambda t: any(abs(c - t) <= 0.1 for c in cenas)
    for a, z in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log):
        a, z = float(a), float(z)
        # fundo marinho da passagem para a tela final escurece aos poucos (sem mudança brusca de imagem); quadro preto solto na emenda entra e sai de golpe
        if z - a < 0.2 and not (perto(a) or perto(z)):
            continue
        out.append(_p(a, "alta" if z - a >= 0.2 else "media", "quadro_preto", f"tela preta de {z - a:.2f} s",
                      "conferir a emenda ou o trecho de origem; tirar o quadro preto"))
    ini = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    fim = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)]
    for i, a in enumerate(ini):
        z = fim[i] if i < len(fim) else None
        dur = f"{z - a:.1f} s" if z else "até o fim"
        out.append(_p(a, "media", "imagem_parada", f"imagem parada por {dur} (limite {parada_max_s:.0f} s)",
                      "trocar o enquadramento, pôr b-roll ou zoom lento nesse trecho"))
    q = 1.0 / (fps or 30.0)
    for a, b in zip(cenas, cenas[1:]):
        if 0 < b - a <= 2.5 * q:
            out.append(_p(a, "baixa", "flash", f"mudança de imagem que dura {round((b - a) / q)} quadro(s)",
                          "se não for o clarão planejado, é um quadro solto na emenda: ajustar a borda do corte"))
    return out, cenas


def ler_audio(log, pausa_max_s, duracao_s):
    out, med = [], {}
    sil_a = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", log)]
    sil_z = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    for i, a in enumerate(sil_a):
        z = sil_z[i] if i < len(sil_z) else duracao_s
        if a <= 0.05 or z >= duracao_s - 0.3:  # respiro do começo e cauda do fim não contam
            continue
        out.append(_p(a, "alta" if z - a >= 2 * pausa_max_s else "media", "trecho_mudo", f"silêncio de {z - a:.2f} s (limite {pausa_max_s:.1f} s)",
                      "encurtar a pausa ou cobrir com fala/trilha"))
    m = re.search(r"Integrated loudness:\s*I:\s*(-?[\d.]+) LUFS", log)
    tp = re.search(r"True peak:\s*Peak:\s*(-?[\d.]+|-inf) dBFS", log)
    if m:
        med["lufs"] = float(m.group(1))
        if abs(med["lufs"] - ALVO_LUFS) > LUFS_TOL:
            out.append(_p(0, "alta" if abs(med["lufs"] - ALVO_LUFS) > 4 else "media", "volume", f"volume em {med['lufs']:.1f} LUFS (alvo {ALVO_LUFS:.0f})",
                          "rodar o acabamento de áudio (finalizar_audio) no final"))
    if tp and tp.group(1) != "-inf":
        med["pico_db"] = float(tp.group(1))
        if med["pico_db"] > PICO_MAX_DB:
            out.append(_p(0, "media", "audio", f"pico em {med['pico_db']:.1f} dBTP (máximo {PICO_MAX_DB:.0f}): risco de estourar no celular",
                          "rodar finalizar_audio ou baixar o trecho do pico"))
    return out, med


def emendas_da_edl(edl_json):
    """Instantes das emendas no vídeo cortado: soma das durações dos trechos mantidos."""
    if not edl_json:
        return []
    manter = ler_json(edl_json).get("manter") or []
    t, out = 0.0, []
    for s in manter[:-1]:
        t += float(s["fim"]) - float(s["inicio"]); out.append(round(t, 3))
    return out


def conferir_emendas_nivel(env, emendas, lim):
    """Clique (pico curto acima do entorno) e salto de nível da voz em cada emenda. env = bordas.envelope do vídeo final."""
    from .bordas import QUADRO_S
    db = env["db"]; off = env.get("off", 0.0); n = len(db); w = int(LADO_S / QUADRO_S); wn = int(NIVEL_LADO_S / QUADRO_S)
    out = []
    for t in emendas:
        i = int(round((t - off) / QUADRO_S))
        if i - w < 0 or i + w >= n:
            continue
        perto = db[max(0, i - 2): i + 3]
        antes, depois = db[i - w: i - 4], db[i + 5: i + w]
        entorno = np.concatenate([antes, depois])
        if perto.max() - np.percentile(entorno, 75) > CLIQUE_DB and perto.max() > lim - 6:
            out.append(_p(t, "media", "audio", "estalo ou pedaço de som solto na emenda (pico curto que não é fala)", "puxar a borda 20–40 ms para o lado quieto ou suavizar a emenda"))
            continue
        # nível pela mediana da voz em 1 s de cada lado: em 250 ms a própria fala (fim de palavra × ataque da seguinte) já varia 9 dB
        va, vd = db[max(0, i - wn): i - 4], db[i + 5: i + wn]
        va, vd = va[va > lim], vd[vd > lim]
        if len(va) >= 8 and len(vd) >= 8:
            dif = float(np.median(vd) - np.median(va))
            if abs(dif) > SALTO_DB:
                out.append(_p(t, "media" if abs(dif) >= 9 else "baixa", "audio", f"voz {'sobe' if dif > 0 else 'cai'} {abs(dif):.0f} dB na emenda (takes com volume diferente)",
                              "igualar o volume dos dois trechos ou trocar o take"))
    return out


def palavras_repetidas(palavras_json):
    """'o o', 'pra pra', 'o seu o seu': a mesma palavra (ou par) dita duas vezes em seguida no vídeo cortado."""
    if not palavras_json:
        return []
    ps = ler_json(palavras_json).get("palavras") or []
    tok = [normalizar(p.get("palavra", "")).strip(" .,!?…") for p in ps]
    out, i = [], 0
    while i < len(tok) - 1:
        if tok[i] and tok[i] == tok[i + 1] and tok[i] not in NATURAIS:
            out.append(_p(ps[i]["inicio"], "media", "take_repetido", f"\"{tok[i]} {tok[i]}\" dito duas vezes",
                          "ouvir: se for refação, cortar a primeira; se for ênfase, deixar")); i += 1; continue
        if i < len(tok) - 3 and tok[i] and tok[i:i + 2] == tok[i + 2:i + 4]:
            par = " ".join(tok[i:i + 2])
            out.append(_p(ps[i]["inicio"], "media", "take_repetido", f"\"{par} {par}\" dito duas vezes",
                          "ouvir: se for refação, cortar a primeira")); i += 4; continue
        i += 1
    return out


def conferir_tecnico(video, edl_json=None, palavras_json=None, formato="reels", saida_json=None):
    """Mede o vídeo final. edl_json = EDL do corte (para achar as emendas), palavras_json = palavras do vídeo CORTADO.
    formato: reels | aula | longo (muda o limite de imagem parada e de pausa muda)."""
    from . import bordas
    v = caminho(video)
    parada_max, pausa_max = LIMITES.get(formato, LIMITES["reels"])
    dv, da, dur, fps = _duracoes(v)
    problemas = []
    log_v = _ffmpeg_log(["-i", str(v), "-an", "-vf",
                         f"scale=320:-2,blackdetect=d={PRETO_MIN_S}:pix_th=0.10,freezedetect=n=0.003:d={parada_max},select='gt(scene,0.35)',showinfo"])
    pv, cenas = ler_video(log_v, parada_max, fps)
    problemas += pv
    medidas = {"duracao_s": round(dur, 2), "fps": round(fps, 2), "mudancas_de_cena": len(cenas)}
    if da is not None:
        log_a = _ffmpeg_log(["-i", str(v), "-vn", "-af", f"silencedetect=n=-45dB:d={pausa_max},ebur128=peak=true"])
        pa, med = ler_audio(log_a, pausa_max, dur)
        problemas += pa; medidas.update(med)
    else:
        problemas.append(_p(0, "alta", "audio", "o vídeo não tem áudio", "conferir a montagem (faixa de áudio perdida)"))
    if dv and da and abs(dv - da) > DESSINCRONIA_S:
        problemas.append(_p(min(dv, da), "media", "audio", f"vídeo com {dv:.2f} s e áudio com {da:.2f} s", "conferir sincronia no fim; cortar a sobra"))
    emendas = emendas_da_edl(edl_json)
    if emendas and da is not None:
        env = bordas.envelope(v)
        if env is not None:
            problemas += conferir_emendas_nivel(env, emendas, bordas.limiares(env)["limiar_db"])
    medidas["emendas_conferidas"] = len(emendas)
    problemas += palavras_repetidas(palavras_json)
    problemas.sort(key=lambda p: ({"alta": 0, "media": 1, "baixa": 2}[p["gravidade"]], p["instante_s"]))
    res = {"video": str(v), "formato": formato, "ok": not any(p["gravidade"] in ("alta", "media") for p in problemas), "problemas": problemas, "medidas": medidas}
    if saida_json:
        res["tecnico_json"] = salvar_json(saida_json, res)
    return res
