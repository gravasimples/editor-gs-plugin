"""Cortes de vídeo longo, extração de trecho, trilha e exportação para editores."""
import re, subprocess
from pathlib import Path
from .util import FFMPEG, caminho, caminho_saida, ler_json, salvar_json, rodar, info_midia, normalizar, ErroFerramenta

GANCHOS = ["erro", "nunca", "sempre", "segredo", "simples", "barato", "caro", "gratis", "gratuito", "dica", "truque", "como", "porque", "ninguem", "todo mundo",
           "cuidado", "para de", "pare de", "melhor", "pior", "obvio", "real", "verdade", "mentira", "diferenca", "problema", "solucao", "em 1 minuto", "em um minuto"]


EMOCAO = ["incrivel", "absurdo", "chocante", "nunca vi", "pior", "melhor", "medo", "vergonha", "errei", "aprendi", "mudou", "acredita", "serio", "pasme", "cuidado", "atencao", "finalmente", "graca", "de graca", "perdi", "ganhei"]
PARADAS = set("a o e de da do das dos em um uma que não nao com para por mais se na no os as eu ele ela isso esse essa aqui ali la lá ja já tá ta então entao mas ou como quando onde muito bem pra pro vai vou ser é e tem tinha foi ter dele dela nos nós você voce vocês voces gente tudo nada só so ainda também tambem até ate".split())


def _frases(palavras, segmentos):
    """Fronteiras de frase: fim de segmento do Whisper ou palavra terminada em . ! ? seguida de pausa > 0,25 s."""
    fins = set()
    for s in segmentos or []:
        fins.add(round(float(s.get("fim", 0)), 3))
    for i, w in enumerate(palavras):
        t = w.get("palavra", "").strip()
        if t and t[-1] in ".!?" and (i + 1 >= len(palavras) or palavras[i + 1]["inicio"] - w["fim"] > 0.25):
            fins.add(round(w["fim"], 3))
    return sorted(fins)


def _ajustar_a_frase(ini, fim, fins, palavras, tol=4.0):
    """Puxa o início para logo depois do fim de frase anterior e o fim para o fim de frase mais próximo (até tol s)."""
    ant = [f for f in fins if f <= ini + 0.05 and ini - f <= tol]
    if ant:
        f = max(ant); prox = [w["inicio"] for w in palavras if w["inicio"] >= f - 0.01]
        if prox:
            ini = max(0.0, min(prox) - 0.15)
    dep = [f for f in fins if fim - tol <= f <= fim + tol]
    if dep:
        fim = min(dep, key=lambda f: abs(f - fim)) + 0.25
    return round(ini, 3), round(fim, 3)


def _topicos(blocos, janela=3, limiar=0.18):
    """Segmentação por coesão lexical (estilo TextTiling): marca uma mudança de assunto quando a sobreposição de vocabulário
    entre a janela anterior e a seguinte cai abaixo do limiar. Devolve índices de bloco onde começa um tópico novo."""
    def bolsa(bs):
        c = {}
        for b in bs:
            for w in b:
                t = normalizar(w["palavra"]).strip(".,!?;:")
                if len(t) > 3 and t not in PARADAS:
                    c[t] = c.get(t, 0) + 1
        return c
    inicios = [0]
    janela = max(1, min(janela, len(blocos) // 2))
    for i in range(janela, len(blocos) - janela + 1):
        a, b = bolsa(blocos[i - janela:i]), bolsa(blocos[i:i + janela])
        if not a or not b:
            continue
        inter = sum(min(a[k], b[k]) for k in a if k in b); uni = (sum(a.values()) * sum(b.values())) ** 0.5
        if uni and inter / uni < limiar:
            if i - inicios[-1] >= 2:
                inicios.append(i)
    return inicios


def propor_cortes_longos(palavras_json, saida_json, n=5, min_s=20.0, max_s=75.0, pausa_bloco_s=1.2):
    """Agrupa a fala em blocos (pausa > pausa_bloco_s), junta blocos vizinhos até caber em [min_s, max_s] e pontua cada candidato.
    Pontuação: densidade de fala, palavras-gancho na abertura, presença de número, pergunta. O Editor escolhe e descreve o gancho."""
    d = ler_json(palavras_json); palavras = d["palavras"]; segmentos = d.get("segmentos", [])
    if not palavras:
        raise ErroFerramenta("Transcrição sem palavras.")
    blocos, atual = [], [palavras[0]]
    for p in palavras[1:]:
        if p["inicio"] - atual[-1]["fim"] > pausa_bloco_s:
            blocos.append(atual); atual = [p]
        else:
            atual.append(p)
    blocos.append(atual)
    fins = _frases(palavras, segmentos); topicos = set(_topicos(blocos))
    cands = []
    for i in range(len(blocos)):
        ws = []
        for j in range(i, len(blocos)):
            ws = ws + blocos[j]
            dur = ws[-1]["fim"] - ws[0]["inicio"]
            if dur > max_s:
                break
            if dur >= min_s:
                ini, fim = _ajustar_a_frase(ws[0]["inicio"], ws[-1]["fim"], fins, palavras)
                texto = " ".join(w["palavra"] for w in ws); abertura = normalizar(" ".join(w["palavra"] for w in ws[:12])); texto_n = normalizar(texto)
                fala = sum(w["fim"] - w["inicio"] for w in ws)
                det = {"densidade": round(min(1.0, fala / dur) * 2.0, 2),
                       "gancho": round(min(2.4, sum(1 for g in GANCHOS if g in abertura) * 0.8), 2),
                       "numero": 0.6 if re.search(r"\d|R\$|reais|por cento|%", texto) else 0.0,
                       "pergunta": 0.5 if "?" in texto[:160] else 0.0,
                       "emocao": round(min(1.0, sum(1 for e in EMOCAO if e in texto_n) * 0.5), 2),
                       "duracao": 0.4 if 30 <= dur <= 60 else 0.0,
                       "completude": (0.5 if any(abs(f - (fim - 0.25)) < 0.3 for f in fins) else 0.0) + (0.3 if i in topicos else 0.0),
                       "topico_novo": 0.3 if i in topicos else 0.0}
                pont = round(sum(det.values()), 2)
                cands.append({"inicio": ini, "fim": fim, "duracao": round(fim - ini, 2), "pontuacao": pont, "pontuacao_detalhe": det,
                              "abertura": " ".join(w["palavra"] for w in ws[:14]), "texto": texto, "comeca_topico": i in topicos,
                              "termina_em_frase": any(abs(f - (fim - 0.25)) < 0.3 for f in fins)})
    # remove sobreposição: ordena por pontuação, aceita se não cruza mais de 30% com um já aceito
    cands.sort(key=lambda c: -c["pontuacao"]); escolhidos = []
    for c in cands:
        ok = True
        for e in escolhidos:
            inter = max(0.0, min(c["fim"], e["fim"]) - max(c["inicio"], e["inicio"]))
            if inter > 0.3 * min(c["duracao"], e["duracao"]):
                ok = False; break
        if ok:
            escolhidos.append(c)
        if len(escolhidos) >= n:
            break
    escolhidos.sort(key=lambda c: c["inicio"])
    out = salvar_json(saida_json, {"origem": d.get("arquivo"), "duracao_s": d.get("duracao_s"), "parametros": {"n": n, "min_s": min_s, "max_s": max_s},
                                   "n_blocos": len(blocos), "n_topicos": len(topicos), "fins_de_frase": fins, "candidatos": escolhidos})
    return {"candidatos_json": out, "n_blocos": len(blocos), "n_topicos": len(topicos),
            "candidatos": [{k: c[k] for k in ("inicio", "fim", "duracao", "pontuacao", "pontuacao_detalhe", "abertura", "comeca_topico", "termina_em_frase")} for c in escolhidos]}


def detectar_cenas(video, limiar=0.4, min_intervalo_s=1.0):
    """Mudanças de plano (cortes de câmera, troca de tela) pelo detector de cena do ffmpeg. Útil para não cortar no meio de um plano
    e para saber se o vídeo alterna rosto e tela. Devolve instantes em segundos."""
    v = caminho(video)
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", v, "-vf", f"select='gt(scene,{limiar})',showinfo", "-an", "-f", "null", "-"], capture_output=True, text=True)
    ts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    cenas, ult = [], -10.0
    for t in ts:
        if t - ult >= min_intervalo_s:
            cenas.append(round(t, 3)); ult = t
    return {"video": v, "n_cenas": len(cenas), "cenas": cenas, "limiar": limiar}


def extrair_trecho(video, inicio_s, fim_s, saida_video, saida_palavras=None, palavras_json=None):
    """Recorta [inicio_s, fim_s] com recodificação (corte exato) e, se houver palavras_json, grava as palavras do trecho com tempo rebaseado."""
    v = caminho(video); out = caminho_saida(saida_video)
    a, z = float(inicio_s), float(fim_s)
    if z <= a:
        raise ErroFerramenta("fim_s deve ser maior que inicio_s")
    rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-ss", str(a), "-to", str(z), "-i", v, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    res = {"video": str(out), "duracao_s": info_midia(out)["duracao_s"], "inicio_s": a, "fim_s": z}
    if palavras_json and saida_palavras:
        d = ler_json(palavras_json)
        ws = [{**p, "inicio": round(p["inicio"] - a, 3), "fim": round(p["fim"] - a, 3)} for p in d["palavras"] if a <= p["inicio"] <= z]
        segs = [{**s, "inicio": round(max(s["inicio"], a) - a, 3), "fim": round(min(s["fim"], z) - a, 3)} for s in d.get("segmentos", []) if s["fim"] > a and s["inicio"] < z]
        res["palavras_json"] = salvar_json(saida_palavras, {**d, "arquivo": str(out), "duracao_s": res["duracao_s"], "palavras": ws, "segmentos": segs,
                                                            "n_palavras": len(ws), "n_segmentos": len(segs), "origem_trecho": [a, z]})
    return res


def adicionar_trilha(video, trilha, saida_video, volume_db=-18.0, ducking=True, fade_s=1.5):
    """Mistura uma trilha por baixo da voz. ducking abaixa a trilha quando há fala (sidechain). A trilha é cortada/looped para a duração do vídeo."""
    v = caminho(video); t = caminho(trilha); out = caminho_saida(saida_video); info = info_midia(v)
    if not info["tem_audio"]:
        raise ErroFerramenta("O vídeo não tem voz para misturar.")
    dur = info["duracao_s"]
    f = (f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{dur},asetpts=PTS-STARTPTS,volume={volume_db}dB,afade=t=in:d={fade_s},afade=t=out:st={max(0, dur - fade_s)}:d={fade_s}[m];")
    if ducking:
        f += "[0:a]asplit=2[voz][sc];[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=40:release=600:makeup=1[md];[voz][md]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
    else:
        f += "[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]"
    rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", v, "-i", t, "-filter_complex", f, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", out])
    return {"video": str(out), "trilha": str(t), "volume_db": volume_db, "ducking": ducking, "duracao_s": info_midia(out)["duracao_s"]}


def _tc(seg, fps):
    f = int(round(seg * fps)); h = f // (3600 * fps); m = (f // (60 * fps)) % 60; s = (f // fps) % 60; fr = f % fps
    return f"{h:02d}:{m:02d}:{s:02d}:{fr:02d}"


def exportar_edl_cmx(edl_json, saida_edl, fps=30, titulo="EDITOR GS", nome_fonte=None):
    """EDL CMX3600 (Premiere, DaVinci, FCP) com os trechos mantidos, em ordem, vídeo+áudio. O editor importa e religa ao arquivo original."""
    edl = ler_json(edl_json); out = caminho_saida(saida_edl)
    fonte = nome_fonte or Path(edl.get("origem") or "ORIGINAL").name
    reel = re.sub(r"[^A-Za-z0-9]", "", Path(fonte).stem.upper())[:8] or "AX"
    linhas = [f"TITLE: {titulo}", "FCM: NON-DROP FRAME", ""]
    rec = 0.0
    for i, m in enumerate(edl["manter"], 1):
        dur = m["fim"] - m["inicio"]
        linhas.append(f"{i:03d}  {reel:<8} AA/V  C        {_tc(m['inicio'], fps)} {_tc(m['fim'], fps)} {_tc(rec, fps)} {_tc(rec + dur, fps)}")
        linhas.append(f"* FROM CLIP NAME: {fonte}")
        rec += dur
    out.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return {"edl": str(out), "n_eventos": len(edl["manter"]), "fps": fps, "duracao_s": round(rec, 3), "fonte": fonte}
