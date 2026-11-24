"""Cortes que não se notam (14/11/2026, item 1 da ordem autorizada pelo Raphael em 13/11).

Números reimplementados da análise das skills (docs/maquina/ANALISE-SKILLS-2026-11-13.md), sem copiar código:
- limiar de silêncio pela própria gravação: ruído = p10 e fala = p90 da energia em janelas de 0,5 s; silêncio abaixo de ruído + 6 dB
  (preso entre fala − 30 e fala − 12 dB); fala menos de 8 dB acima do ruído = não encurta pausa e avisa;
- borda pela voz e não pela palavra do Whisper: fim = última voz + cauda (consoante fraca, até 180 ms) + 80 ms; começo 70 ms antes da voz;
  em fala corrida (sem silêncio perto) a borda vai para os 10 ms mais quietos até 100 ms da fronteira;
- pausa por energia (normal/dinâmico/bem dinâmico/aula), sem cortar ganho menor que 0,2 s; trecho mantido com menos de 0,4 s volta a
  encostar no vizinho; densidade (mediana do trecho) no resumo.
Tudo em segundos no relógio do vídeo (util.inicio_audio_s)."""
import statistics
import subprocess
import numpy as np
from .util import FFMPEG, caminho, inicio_audio_s, normalizar

QUADRO_S = 0.01
CAUDA_MAX_S = 0.18
FOLGA_FIM_S = 0.08
FOLGA_INICIO_S = 0.07
JANELA_QUIETA_S = 0.10
GANHO_MIN_S = 0.2
TRECHO_MIN_S = 0.4
# respiro (15/11/2026, retorno do Raphael no Laboratório: pausa de 0,5 s no 0:05 do obvio02): inspiração e ar de sala ficam acima do
# limiar de silêncio (−19 a −26 dB com limiar −26,5) e o corte tratava como voz. Voz forte = até 6 dB abaixo do nível da fala.
RESPIRO_DB = 6.0
ANTES_DA_VOZ_S = 0.15    # consoante + ar que ficam antes da primeira voz forte quando o trecho começa num respiro
RESPIRO_FIM_S = 0.12     # folga depois que a voz cai para respiro (fricativa final)
# modo: (pausa até X fica inteira, alvo do silêncio extra em pausa até 1 s, alvo acima de 1 s)
PAUSAS = {"normal": (0.35, 0.15, 0.25), "dinamico": (0.25, 0.10, 0.20), "bem_dinamico": (0.20, 0.07, 0.15), "aula": (1.5, 0.6, 0.6)}
_CACHE = {}


def envelope(arquivo):
    """Energia em dB a cada 10 ms, com o deslocamento do áudio no arquivo. None quando não há áudio legível."""
    import os
    c = caminho(arquivo)
    try:
        chave = (str(c), os.path.getmtime(c))
    except OSError:
        return None
    if chave in _CACHE:
        return _CACHE[chave]
    sr = 16000
    try:
        pcm = subprocess.run([FFMPEG, "-v", "error", "-i", str(c), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                             capture_output=True, timeout=600).stdout
    except Exception:  # noqa
        return None
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    n = int(sr * QUADRO_S)
    if len(a) < n * 100:
        return None
    q = a[: len(a) // n * n].reshape(-1, n)
    env = {"db": 20 * np.log10(np.sqrt((q ** 2).mean(axis=1)) + 1e-9), "off": inicio_audio_s(c)}
    _CACHE.clear(); _CACHE[chave] = env
    return env


def limiares(env):
    db = env["db"]; w = int(0.5 / QUADRO_S)
    pot = 10 ** (db[: len(db) // w * w] / 10)
    jdb = 10 * np.log10(pot.reshape(-1, w).mean(axis=1) + 1e-12)
    ruido, fala = float(np.percentile(jdb, 10)), float(np.percentile(jdb, 90))
    limiar = min(max(ruido + 6, fala - 30), fala - 12)
    contraste = fala - ruido
    return {"ruido_db": round(ruido, 1), "fala_db": round(fala, 1), "limiar_db": round(limiar, 1), "contraste_db": round(contraste, 1),
            "aviso": None if contraste >= 8 else f"a fala está só {contraste:.0f} dB acima do ruído: pausas medidas no áudio não foram encurtadas"}


def _i(env, t):
    return int(round((t - env["off"]) / QUADRO_S))


def _t(env, i):
    return env["off"] + i * QUADRO_S


def silencios(env, lim, min_s):
    mudo = env["db"] < lim["limiar_db"]
    out, ini = [], None
    for i, m in enumerate(np.append(mudo, False)):
        if m and ini is None:
            ini = i
        elif not m and ini is not None:
            if (i - ini) * QUADRO_S >= min_s:
                out.append((round(_t(env, ini), 3), round(_t(env, i), 3)))
            ini = None
    return out


def _cauda(env, lim, t_voz_fim):
    """Segundos de consoante fraca/decaimento depois da última voz (acima do ruído + 3 dB), até 180 ms."""
    db = env["db"]; i = _i(env, t_voz_fim); k = 0
    while k < CAUDA_MAX_S / QUADRO_S and 0 <= i + k < len(db) and db[i + k] > lim["ruido_db"] + 3:
        k += 1
    return k * QUADRO_S


def _mais_quieto(env, a, b):
    db = env["db"]; i, j = max(0, _i(env, a)), min(len(db), _i(env, b) + 1)
    if j - i < 1:
        return None
    return round(_t(env, i + int(np.argmin(db[i:j]))) + QUADRO_S / 2, 3)


def _mudo_desde(env, lim, a, b, min_s=0.06):
    """Primeiro instante em [a, b] onde começa um silêncio de pelo menos min_s (ou None)."""
    db = env["db"]; i, j = max(0, _i(env, a)), min(len(db), _i(env, b)); n = int(min_s / QUADRO_S)
    k = i
    while k < j:
        if db[k] < lim["limiar_db"] and np.all(db[k:k + n] < lim["limiar_db"]):
            return _t(env, k)
        k += 1
    return None


def _voz_desde(env, lim, a, b, min_s=0.04):
    """Último instante em [a, b] em que a voz volta depois de silêncio (começo de fala), ou None."""
    db = env["db"]; i, j = max(0, _i(env, a)), min(len(db), _i(env, b)); n = int(min_s / QUADRO_S)
    for k in range(j, i, -1):
        if db[k - 1] < lim["limiar_db"] and k + n <= len(db) and np.all(db[k:k + n] >= lim["limiar_db"]):
            return _t(env, k)
    return None


def _forte(env, lim):
    return env["db"] >= max(lim["limiar_db"], lim["fala_db"] - RESPIRO_DB)


def _voz_forte_desde(env, lim, a, b, min_s=0.03):
    """Primeiro instante em [a, b] com voz forte por min_s, ou None."""
    f = _forte(env, lim); i, j = max(0, _i(env, a)), min(len(f), _i(env, b)); n = int(min_s / QUADRO_S)
    for k in range(i, j):
        if f[k:k + n].all():
            return _t(env, k)
    return None


def respiros(env, lim, palavras, min_s):
    """Trechos sem voz forte (silêncio, inspiração, ar de sala) de pelo menos min_s e sem palavra no miolo."""
    f = np.append(_forte(env, lim), True); out, ini = [], None
    meios = [(float(p["inicio"]) + float(p["fim"])) / 2 for p in palavras or []]
    for i, forte in enumerate(f):
        if not forte and ini is None:
            ini = i
        elif forte and ini is not None:
            a, z = _t(env, ini), _t(env, i)
            if z - a >= min_s and not any(a + 0.1 < m < z - 0.1 for m in meios):
                out.append((round(a, 3), round(z, 3)))
            ini = None
    return out


def ajustar_bordas(manter, palavras, env, lim):
    """Leva cada borda de trecho para a voz. Devolve (trechos, contagem por tipo de borda)."""
    ini_p = sorted(float(p["inicio"]) for p in palavras); fim_p = sorted(float(p["fim"]) for p in palavras)
    cont = {"fim_na_voz": 0, "inicio_na_voz": 0, "fala_corrida": 0}
    novos = []
    for x, y in manter:
        dentro = [p for p in palavras if x <= (float(p["inicio"]) + float(p["fim"])) / 2 <= y]
        if not dentro:
            novos.append([x, y]); continue
        w_ini, w_fim = float(dentro[0]["inicio"]), float(dentro[-1]["fim"])
        prox = next((t for t in ini_p if t > w_fim + 0.02), None)   # próxima palavra (fica ou sai)
        ant = next((t for t in reversed(fim_p) if t < w_ini - 0.02), None)
        teto = (prox - 0.03) if prox is not None else y + 0.5
        piso = (ant + 0.03) if ant is not None else max(0.0, x - 0.5)
        # fim
        m = _mudo_desde(env, lim, w_fim - 0.12, min(teto, w_fim + 0.45))
        if m is not None:
            ny = min(teto, m + _cauda(env, lim, m) + FOLGA_FIM_S); cont["fim_na_voz"] += 1
        else:
            q = _mais_quieto(env, w_fim - 0.04, min(teto, w_fim + JANELA_QUIETA_S))
            ny = q if q is not None else y; cont["fala_corrida"] += 1
        # começo
        v = _voz_desde(env, lim, max(piso, w_ini - 0.35), w_ini + 0.06)
        if v is not None:
            nx = max(piso, v - FOLGA_INICIO_S); cont["inicio_na_voz"] += 1
        else:
            q = _mais_quieto(env, max(piso, w_ini - JANELA_QUIETA_S), w_ini + 0.04)
            nx = q if q is not None else x; cont["fala_corrida"] += 1
        ny = max(ny, w_fim)  # nunca antes do fim da última palavra que fica
        nx = min(nx, w_ini)
        # começo num respiro: o Whisper põe a palavra dentro da inspiração; a borda vai para perto da primeira voz forte
        vf = _voz_forte_desde(env, lim, nx, min(ny, max(w_ini, nx) + 0.6))
        if vf is not None and vf - ANTES_DA_VOZ_S - nx >= 0.08:
            nx = vf - ANTES_DA_VOZ_S; cont["respiro_no_inicio"] = cont.get("respiro_no_inicio", 0) + 1
        novos.append([round(max(0.0, nx), 3), round(ny, 3)])
    novos.sort(); juntos = []
    for x, y in novos:
        if juntos and x - juntos[-1][1] <= 0.05:
            juntos[-1][1] = max(juntos[-1][1], y)
        else:
            juntos.append([x, y])
    return juntos, cont


def _tirar(manter, tirar):
    novos, cortado = [], 0.0
    for x, y in manter:
        pedacos = [(x, y)]
        for a, z in tirar:
            prox = []
            for u, w in pedacos:
                if z <= u or a >= w:
                    prox.append((u, w)); continue
                if a > u: prox.append((u, a))
                if z < w: prox.append((z, w))
                cortado += min(z, w) - max(a, u)
            pedacos = prox
        novos += [[round(u, 3), round(w, 3)] for u, w in pedacos if w - u >= 0.12]
    return novos, round(cortado, 2)


def encurtar_pausas(manter, env, lim, modo="normal", fica_ate_s=None, palavras=None):
    """Tira o miolo das pausas de dentro dos trechos mantidos pela tabela do modo. Devolve (trechos, segundos tirados, n pausas).
    Com palavras, a pausa cheia de respiro (sem palavra no miolo) também encurta."""
    fica, alvo_curto, alvo_longo = PAUSAS.get(modo, PAUSAS["normal"])
    if fica_ate_s is not None:
        fica = fica_ate_s
    tirar = []
    for s, e in silencios(env, lim, fica):
        alvo = alvo_curto if e - s <= 1.0 else alvo_longo
        fim_voz = s + _cauda(env, lim, s) + FOLGA_FIM_S
        ini_voz = e - FOLGA_INICIO_S
        if (ini_voz - fim_voz) - alvo < GANHO_MIN_S:
            continue
        tirar.append((fim_voz + alvo / 2, ini_voz - alvo / 2))
    if palavras is not None:
        for s, e in respiros(env, lim, palavras, fica):
            alvo = alvo_curto if e - s <= 1.0 else alvo_longo
            fim_voz, ini_voz = s + RESPIRO_FIM_S, e - ANTES_DA_VOZ_S
            if (ini_voz - fim_voz) - alvo >= GANHO_MIN_S:
                tirar.append((fim_voz + alvo / 2, ini_voz - alvo / 2))
        tirar.sort(); uniao = []
        for a, z in tirar:
            if uniao and a <= uniao[-1][1]:
                uniao[-1] = (uniao[-1][0], max(uniao[-1][1], z))
            else:
                uniao.append((a, z))
        tirar = uniao
    novos, cortado = _tirar(manter, tirar)
    return novos, cortado, len(tirar)


# --- fim no quadro calmo (15/11/2026; regra do edit-reel, MIT): depois da última palavra, parar no quadro mais parado, antes da mão ir à câmera
FIM_CALMO_DE_S, FIM_CALMO_ATE_S = 0.24, 0.52   # janela depois do fim da última palavra
FIM_CALMO_FPS = 20
MAO_FATOR, MAO_MIN = 3.0, 6.0                  # movimento na metade de baixo 3x a base (e acima de 6 em 0–255) = a mão vindo


def _movimento_baixo(video, t0, dur_s, fps=FIM_CALMO_FPS, w=96, h=170):
    """[(t, movimento)] da metade de baixo do quadro (onde a mão entra para parar a gravação), diferença média entre quadros seguidos."""
    r = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{max(0.0, t0):.3f}", "-t", f"{dur_s:.3f}", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    n = len(r.stdout) // (w * h)
    if n < 3:
        return []
    q = np.frombuffer(r.stdout[:n * w * h], np.uint8).reshape(n, h, w)[:, h // 2:, :].astype(np.float32)
    return [(round(max(0.0, t0) + k / fps, 3), float(np.mean(np.abs(q[k] - q[k - 1])))) for k in range(1, n)]


def fim_calmo(video, fim_atual, fim_ultima_palavra, duracao):
    """Novo fim do vídeo: o quadro mais parado em [última palavra + 0,24 s, + 0,52 s], antes de o movimento de baixo disparar (mão indo à câmera)
    e nunca antes do fim atual (que já protege a cauda da voz). Devolve (fim, info); sem vídeo legível ou sem espaço, fica o fim atual."""
    de, ate = fim_ultima_palavra + FIM_CALMO_DE_S, min(fim_ultima_palavra + FIM_CALMO_ATE_S, duracao - 0.05)
    if ate <= max(de, fim_atual) + 0.02:
        return fim_atual, {"motivo": "sem espaço depois da fala"}
    try:
        mov = _movimento_baixo(caminho(video), fim_ultima_palavra - 0.2, (ate - fim_ultima_palavra) + 0.5)
    except Exception:  # noqa
        mov = []
    if not mov:
        return fim_atual, {"motivo": "sem quadros"}
    base = statistics.median(m for t, m in mov if t <= fim_ultima_palavra + 0.15) if any(t <= fim_ultima_palavra + 0.15 for t, _ in mov) else min(m for _, m in mov)
    mao = next((t for t, m in mov if t > fim_ultima_palavra and m > max(MAO_MIN, base * MAO_FATOR)), None)
    teto = min(ate, mao - 0.1) if mao else ate
    janela = [(t, m) for t, m in mov if max(de, fim_atual) <= t <= teto]
    if not janela:
        return fim_atual, {"motivo": "mão antes da janela calma" if mao else "sem quadro na janela", "mao_s": mao}
    t, m = min(janela, key=lambda x: x[1])
    return round(t, 3), {"fim_antes": round(fim_atual, 3), "fim": round(t, 3), "movimento": round(m, 2), "base": round(base, 2), "mao_s": mao}


def juntar_curtos(manter, minimo_s=TRECHO_MIN_S, vao_max_s=0.35):
    """Trecho mantido muito curto pisca na tela: volta a encostar no vizinho mais perto quando o vão é pequeno (a pausa fica)."""
    m = [list(s) for s in manter]; juntou = 0
    k = 0
    while k < len(m):
        x, y = m[k]
        if y - x < minimo_s and len(m) > 1:
            vao_ant = x - m[k - 1][1] if k > 0 else None
            vao_pos = m[k + 1][0] - y if k + 1 < len(m) else None
            opc = [(v, lado) for v, lado in ((vao_ant, -1), (vao_pos, 1)) if v is not None and v <= vao_max_s]
            if opc:
                _, lado = min(opc)
                if lado < 0:
                    m[k - 1][1] = y; del m[k]; k -= 1
                else:
                    m[k + 1][0] = x; del m[k]
                juntou += 1; continue
        k += 1
    return m, juntou


def densidade(manter, modo):
    if not manter:
        return None
    med = round(statistics.median(y - x for x, y in manter), 2)
    leitura = "solto (poucas emendas)" if med > 2.0 else "picotado (emendas demais; confira se a fala respira)" if med < 0.7 else "ok"
    if modo == "aula" and med > 2.0:
        leitura = "ok (aula)"
    return {"mediana_trecho_s": med, "n_trechos": len(manter), "leitura": leitura}


def subida_de_energia(env, t, ate_s=0.15, min_db=3.0):
    """Instante da maior subida de energia em [t, t + ate_s] (o Whisper marca a palavra antes do ataque); sem subida clara, t.
    15/11/2026, item 3: a palavra de impacto (pop, punch, grafismo enfático) cai no ataque da voz, até 150 ms depois do Whisper."""
    db = env["db"]; i, j = max(1, _i(env, t)), min(len(db), _i(env, t + ate_s) + 1)
    if j - i < 2:
        return t
    d = np.diff(db[i - 1:j])
    k = int(np.argmax(d))
    return round(_t(env, i + k), 3) if d[k] >= min_db else t


def alinhar_na_energia(itens, env, campo="inicio", ate_s=0.15):
    """Copia dos itens com `campo` levado para a subida de energia (só para frente, até ate_s)."""
    if env is None:
        return [dict(x) for x in itens or []]
    out = []
    for x in itens or []:
        y = dict(x); t0 = float(y[campo]); t1 = subida_de_energia(env, t0, ate_s)
        y[campo] = round(t1, 2)
        if "fim" in y and float(y["fim"]) <= y[campo]:
            y["fim"] = round(y[campo] + (float(x["fim"]) - t0), 2)
        out.append(y)
    return out


# ---------- conferência de cada emenda pelo áudio ----------

def _parecida(a, b):
    import difflib
    a, b = normalizar(a), normalizar(b)
    if not a or not b:
        return False
    eq = {"pra": "para", "pro": "para o", "ta": "esta", "to": "estou", "ce": "voce", "cê": "voce"}
    a, b = eq.get(a, a), eq.get(b, b)
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.7 or (len(a) >= 4 and (a.startswith(b) or b.startswith(a)))


def _achou(esperadas, ouvidas):
    """Todas as esperadas aparecem, na ordem, nas ouvidas."""
    j = 0
    for w in esperadas:
        while j < len(ouvidas) and not _parecida(w, ouvidas[j]):
            j += 1
        if j == len(ouvidas):
            return False
        j += 1
    return True


def _ouvir_emenda(arquivo, y, x, lado_s, transcrever):
    """Monta o áudio [y − lado, y] + [x, x + lado] do original e transcreve. Devolve a lista de palavras ouvidas."""
    import os, tempfile
    fd, wav = tempfile.mkstemp(suffix=".wav"); os.close(fd)
    try:
        fc = (f"[0:a]atrim=start={max(0.0, y - lado_s):.3f}:end={y:.3f},asetpts=PTS-STARTPTS[a0];"
              f"[0:a]atrim=start={x:.3f}:end={x + lado_s:.3f},asetpts=PTS-STARTPTS[a1];[a0][a1]concat=n=2:v=0:a=1[a]")
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(arquivo), "-filter_complex", fc, "-map", "[a]", "-ac", "1", "-ar", "16000", wav],
                       check=True, timeout=120)
        return transcrever(wav)
    finally:
        os.unlink(wav)


_MODELO = {}


def _transcrever_curto(wav):
    from faster_whisper import WhisperModel
    from .transcricao import escolher_device
    if "m" not in _MODELO:
        dev, ct = escolher_device()
        try:
            _MODELO["m"] = WhisperModel("small", device=dev, compute_type=ct)
            list(_MODELO["m"].transcribe(wav, language="pt")[0])  # a falha de CUDA só aparece ao consumir
        except Exception:  # noqa
            _MODELO["m"] = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = _MODELO["m"].transcribe(wav, language="pt", vad_filter=False, condition_on_previous_text=False, beam_size=3)
    return [w for s in segs for w in s.text.split()]


def verificar_emendas_audio(arquivo, manter, palavras, n_palavras=2, lado_s=1.2, transcrever=None, max_emendas=80):
    """Para cada emenda, ouve o áudio emendado e exige as n palavras antes e as n depois. Se faltar, testa bordas vizinhas
    (fim +40/+80 ms, começo −40/−80 ms) e fica com a primeira que passa. Devolve (trechos, relatório)."""
    transcrever = transcrever or _transcrever_curto
    m = [list(s) for s in manter]
    def pals(a, z):
        return [p["palavra"] for p in palavras if a <= (float(p["inicio"]) + float(p["fim"])) / 2 <= z]
    rel = []
    for k in range(min(len(m) - 1, max_emendas)):
        (a, y), (x, z) = m[k], m[k + 1]
        antes, depois = pals(a, y)[-n_palavras:], pals(x, z)[:n_palavras]
        esperadas = antes + depois
        if not esperadas:
            continue
        item = {"emenda": k + 1, "origem_s": [round(y, 2), round(x, 2)], "esperado": " ".join(antes) + " | " + " ".join(depois)}
        tentativas = [(0.0, 0.0), (0.04, 0.0), (0.0, -0.04), (0.04, -0.04), (0.08, -0.08)]
        for dy, dx in tentativas:
            ny, nx = y + dy, x + dx
            if dy and k + 1 < len(m) and ny >= nx - 0.02:
                continue
            try:
                ouvidas = _ouvir_emenda(arquivo, ny, nx, lado_s, transcrever)
            except Exception as e:  # noqa
                item["erro"] = str(e)[:120]; break
            if _achou(esperadas, ouvidas):
                item["ok"] = True; item["ajuste_ms"] = [round(dy * 1000), round(dx * 1000)] if (dy or dx) else None
                m[k][1], m[k + 1][0] = round(ny, 3), round(nx, 3)
                break
            item["ouvido"] = " ".join(ouvidas)[:120]
        else:
            item["ok"] = False
        rel.append(item)
    falhas = [r for r in rel if r.get("ok") is False]
    return m, {"n_emendas": len(rel), "ok": sum(1 for r in rel if r.get("ok")), "ajustadas": sum(1 for r in rel if r.get("ajuste_ms")),
               "conferir_de_ouvido": [{"emenda": r["emenda"], "origem_s": r["origem_s"], "esperado": r["esperado"], "ouvido": r.get("ouvido", "")}
                                      for r in falhas], "erros": [r for r in rel if "erro" in r][:5]}
