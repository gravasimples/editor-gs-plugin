"""Cortes que não se notam (14/11/2026): relógio do áudio, limiar pela gravação, borda pela voz, pausa por modo, trecho curto,
densidade, recomeço que não é recomeço, literal que não apaga fala e conferência da emenda pelo áudio.
Tudo com áudio sintético em pasta temporária. Rodar: python -X utf8 -I testes/teste_bordas.py"""
import json, os, subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-bordas-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import bordas as B, cortes as C
from editor_video.util import FFMPEG, inicio_audio_s

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

SR = 16000
rng = np.random.default_rng(7)
# "fala": rajadas a −10 dBFS; depois de cada rajada, 120 ms de consoante fraca (−34 dBFS); chão de ruído a −55 dBFS
RAJADAS = [(0.5, 1.6), (1.8, 2.9), (3.7, 4.6), (6.1, 7.2), (7.3, 7.55), (7.85, 9.0)]
dur = 10.0
x = rng.normal(0, 10 ** (-55 / 20), int(SR * dur))
for a, b in RAJADAS:
    i, j = int(a * SR), int(b * SR)
    x[i:j] = rng.normal(0, 10 ** (-10 / 20), j - i) * np.sin(np.linspace(0, 40 * np.pi, j - i)) ** 2 * 1.6
    k = int((b + 0.12) * SR); x[j:k] = rng.normal(0, 10 ** (-34 / 20), k - j)
wav = tmp / "fala.wav"
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())

# --- relógio do áudio
mp4_atraso, mp4_ok = tmp / "atraso.mp4", tmp / "ok.mp4"
base = [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=30:d=11"]
subprocess.run(base + ["-itsoffset", "1.5", "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac", str(mp4_atraso)], check=True)
subprocess.run(base + ["-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac", str(mp4_ok)], check=True)
check(1.4 < inicio_audio_s(mp4_atraso) <= 1.5, f"áudio que começa depois do vídeo é medido ({inicio_audio_s(mp4_atraso)} s; o AAC conta as amostras de preparo)")
check(abs(inicio_audio_s(mp4_ok)) < 0.07, "arquivo sem atraso: só o preparo do AAC (no máximo 64 ms)")
env_a = B.envelope(mp4_atraso); sil_a = B.silencios(env_a, B.limiares(env_a), 0.5)
ini_voz = env_a["off"] + int(np.argmax(env_a["db"] > -25)) * B.QUADRO_S
check(abs(ini_voz - 2.0) < 0.03, f"a primeira fala cai em 2,0 s no relógio do vídeo (0,5 s + 1,5 s de atraso): {ini_voz:.3f}")
check(any(abs(s - (1.5 + 4.72)) < 0.1 for s, _ in sil_a), f"silêncio medido no relógio do vídeo (pausa de 4,7 s aparece em ~6,2 s): {sil_a[:4]}")
check(any(abs(s - (1.5 + 4.72)) < 0.1 for s, _ in C._silencios_audio(mp4_atraso, 0.5)), "detector antigo também devolve no relógio do vídeo")

# --- limiar pela gravação
env = B.envelope(wav); lim = B.limiares(env)
check(-60 < lim["ruido_db"] < -45 and lim["fala_db"] > -25, f"ruído e fala medidos na própria gravação: {lim}")
check(lim["ruido_db"] + 5.9 <= lim["limiar_db"] <= lim["fala_db"] - 12, "limiar entre ruído + 6 e fala − 12 dB")
check(lim["aviso"] is None, "fala bem acima do ruído: sem aviso")
plano = np.full(SR * 5, 0.05, dtype=np.float32) + rng.normal(0, 0.03, SR * 5).astype(np.float32)
wav2 = tmp / "chiado.wav"
with wave.open(str(wav2), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((plano * 32767).astype(np.int16).tobytes())
check(B.limiares(B.envelope(wav2))["aviso"] is not None, "fala sem contraste com o ruído vira aviso (não encurta)")

# --- borda pela voz (o Whisper fecha a palavra 60 ms antes e abre 40 ms depois)
pal = []
for k, (a, b) in enumerate(RAJADAS):
    pal.append({"palavra": f"p{k}a", "inicio": a + 0.04, "fim": (a + b) / 2}); pal.append({"palavra": f"p{k}b.", "inicio": (a + b) / 2, "fim": b - 0.06})
manter = [[0.46, 1.6], [3.66, 4.6]]
novos, cont = B.ajustar_bordas(manter, pal, env, lim)
check(novos[0][1] >= 1.6 + 0.12 + 0.05, f"fim não come a consoante final: {novos[0][1]} (voz até 1,72)")
check(novos[0][1] <= 1.6 + 0.12 + 0.18, "fim não arrasta silêncio demais")
check(0.5 - 0.11 <= novos[1][0] - 3.2 <= 0.5 - 0.03 or 3.7 - 0.11 <= novos[1][0] <= 3.7 - 0.03, f"começo ~70 ms antes da voz: {novos[1][0]}")
check(cont["fim_na_voz"] >= 1 and cont["inicio_na_voz"] >= 1, f"bordas achadas na voz: {cont}")
corrida, c2 = B.ajustar_bordas([[6.06, 7.2], [7.25, 7.55]], [w for w in pal if 6 < w["inicio"] < 7.6] + [{"palavra": "x", "inicio": 7.56, "fim": 7.8}], env, lim)
check(all(b <= 7.56 for _, b in corrida), "em fala corrida a borda não invade a palavra seguinte")

# --- pausa pela tabela do modo
m_all = [[0.43, 9.2]]
din, tirado, n = B.encurtar_pausas(m_all, env, lim, "dinamico")
check(n >= 2 and tirado > 1.3, f"pausas longas encurtadas no dinâmico: {n} pausas, {tirado} s")
vao = next((b[0] - a[1] for a, b in zip(din, din[1:]) if 2.9 < a[1] < 3.7), None)
check(vao is not None and 0.2 <= 0.68 - vao <= 0.3, f"pausa de 0,68 s fica com ~0,25 s (80 ms + 100 ms + 70 ms): tirado {vao}")
fica_curta = any(a <= 1.8 <= b for a, b in din) and any(a <= 1.65 <= b for a, b in din)
check(fica_curta or any(a <= 1.7 and b >= 1.85 for a, b in din), "pausa de 0,2 s (1,6 → 1,8) fica inteira")
nor, tirado_n, _ = B.encurtar_pausas(m_all, env, lim, "normal")
aul, tirado_a, _ = B.encurtar_pausas(m_all, env, lim, "aula")
check(tirado_n < tirado and tirado_a < tirado_n, f"normal tira menos que dinâmico e aula menos ainda ({tirado}, {tirado_n}, {tirado_a})")
check(B.encurtar_pausas(m_all, env, lim, "dinamico", fica_ate_s=5.0)[2] == 0, "fica_ate_s alto desliga")

# --- trecho curto e densidade
jc, nj = B.juntar_curtos([[0.0, 2.0], [2.2, 2.45], [3.5, 6.0]])
check(nj == 1 and jc[0] == [0.0, 2.45], f"trecho de 0,25 s encosta no vizinho perto: {jc}")
check(B.juntar_curtos([[0.0, 2.0], [3.0, 3.3], [4.5, 6.0]])[1] == 0, "trecho curto isolado (vão grande) fica como está")
check(B.densidade([[0, 3], [4, 7.5], [8, 11]], "dinamico")["leitura"].startswith("solto"), "mediana > 2 s = solto")
check(B.densidade([[0, 0.5], [1, 1.6], [2, 2.5]], "dinamico")["leitura"].startswith("picotado"), "mediana < 0,7 s = picotado")
check(B.densidade([[0, 1.2], [2, 3.5]], "dinamico")["leitura"] == "ok", "entre 0,7 e 2 s = ok")

# --- respiro (15/11, Laboratório: pausa de 0,5 s no 0:05 do obvio02): inspiração a −22 dB fica acima do limiar e não era pausa
xr = rng.normal(0, 10 ** (-55 / 20), SR * 9)
def pedaco(a, b, db, voz=True):
    i, j = int(a * SR), int(b * SR); r = rng.normal(0, 10 ** (db / 20), j - i)
    xr[i:j] = r * np.sin(np.linspace(0, 20 * np.pi * (b - a), j - i)) ** 2 * 1.6 if voz else r
pedaco(0.5, 1.5, -10); pedaco(1.5, 2.3, -22, False); pedaco(2.3, 3.3, -10)      # respiro de 0,8 s no meio do trecho
pedaco(4.0, 4.6, -22, False); pedaco(4.6, 5.6, -10)                             # trecho que começa numa inspiração
pedaco(6.5, 7.0, -10); pedaco(7.0, 7.8, -20, False); pedaco(7.8, 8.5, -10)      # "é" fraco no meio: não é respiro
wr = tmp / "respiro.wav"
with wave.open(str(wr), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(xr, -1, 1) * 32767).astype(np.int16).tobytes())
er = B.envelope(wr); lr = B.limiares(er)
pr = [{"palavra": "um", "inicio": 0.55, "fim": 1.45}, {"palavra": "dois", "inicio": 2.35, "fim": 3.25}, {"palavra": "dá", "inicio": 4.3, "fim": 5.5},
      {"palavra": "tres", "inicio": 6.5, "fim": 7.0}, {"palavra": "é", "inicio": 7.3, "fim": 7.5}, {"palavra": "quatro", "inicio": 7.8, "fim": 8.5}]
check(not B.silencios(er, lr, 0.25)[1:-1] or all(not (1.6 < a < 2.2) for a, _ in B.silencios(er, lr, 0.25)), "inspiração não é silêncio pelo limiar (o caso do bug)")
sem, t0, _ = B.encurtar_pausas([[0.4, 3.4]], er, lr, "dinamico")
com, t1, _ = B.encurtar_pausas([[0.4, 3.4]], er, lr, "dinamico", palavras=pr)
check(t0 == 0 and len(com) == 2 and 0.25 <= t1 <= 0.5, f"pausa cheia de respiro encurta com as palavras ({t0} → {t1} s)")
check(com[0][1] >= 1.5 + 0.1 and com[-1][0] <= 2.3 - 0.12, f"a voz dos dois lados fica inteira: {com}")
fr, _, _ = B.encurtar_pausas([[6.4, 8.6]], er, lr, "dinamico", palavras=pr)
check(fr == [[6.4, 8.6]], "palavra fraca no miolo segura a pausa (não é respiro)")
ini, cr = B.ajustar_bordas([[3.9, 5.6]], [w for w in pr if w["palavra"] == "dá"], er, lr)
check(4.6 - 0.2 <= ini[0][0] <= 4.6 - 0.1 and cr.get("respiro_no_inicio") == 1, f"começo na inspiração vai para 150 ms antes da voz: {ini[0][0]} ({cr})")

# --- recomeço que não é recomeço (obvio02, 14/11)
def ws(t, passo=0.3):
    return [{"palavra": w, "inicio": round(i * passo, 2), "fim": round(i * passo + 0.25, 2)} for i, w in enumerate(t.split())]
check(C._reinicios(ws("Galera, não é falta de equipamento. É falta de fazer do jeito certo.")) == [], "'não é falta de X. É falta de Y' é frase inteira, nada sai")
check(C._reinicios(ws("para fazer uma live no YouTube. Dá para fazer pelo seu celular e para fazer algo mais")) == [], "'para fazer' repetido em frases diferentes não é recomeço")
check(len(C._reinicios(ws("E com ele a gente transmite a nossa... E com ele a gente faz essa live"))) == 1, "tomada que some em reticência é recomeço")
check(len(C._reinicios(ws("O óbvio precisa ser dito parte 2. O óbvio precisa ser dito parte 2. Você"))) == 1, "frase inteira dita de novo continua sendo refação")

# --- literal não apaga fala e não muda tempo
orig = [{"palavra": w, "inicio": t, "fim": t + 0.3} for w, t in (("tiver", 0.0), ("o", 0.4), ("link.", 0.8), ("Dá", 3.0), ("para", 3.4), ("fazer", 3.8), ("pelo", 4.2), ("seu", 4.6), ("celular", 5.0))]
sil = [(1.2, 2.9)]
lit_errada = lambda arq, a, b: [{"palavra": w, "inicio": a + 0.5 + 0.3 * i, "fim": a + 0.7 + 0.3 * i, "literal": True} for i, w in enumerate("não precisa de um estúdio pra fazer uma live".split())]
n1, i1 = C.refinar_literal(orig, "x.mp4", sil, transcrever=lit_errada)
check(n1 == orig and len(i1["recusadas"]) >= 1 if i1["janelas"] else n1 == orig, f"literal com outra frase é recusada e nada muda: {i1.get('recusadas')}")
estic = [{"palavra": "vou", "inicio": 0.0, "fim": 0.2}, {"palavra": "procurar", "inicio": 0.25, "fim": 2.4}, {"palavra": "o", "inicio": 2.45, "fim": 2.55},
         {"palavra": "branco", "inicio": 2.6, "fim": 3.0}, {"palavra": "fim", "inicio": 6.0, "fim": 6.2}]
def lit_boa(arq, a, b):
    return [{"palavra": w, "inicio": t, "fim": t + 0.2, "literal": True} for w, t in
            (("vou", 0.02), ("procurar", 0.27), ("vou", 1.2), ("procurar", 1.5), ("o", 2.47), ("branco", 2.62))]
n2, i2 = C.refinar_literal(estic, "x.mp4", [(3.1, 5.9)], transcrever=lit_boa)
check(len(n2) == len(estic) + 2 and [w["palavra"] for w in n2][:4] == ["vou", "procurar", "vou", "procurar"], f"literal acrescenta só a repetição: {[w['palavra'] for w in n2]}")
check(all(w in n2 for w in estic), "palavras que as duas têm ficam com o tempo da transcrição normal")

# --- propor_cortes no áudio sintético
pj = tmp / "p.json"
pj.write_text(json.dumps({"arquivo": str(wav), "duracao_s": dur, "palavras": pal, "segmentos": []}), encoding="utf-8")
r = C.propor_cortes(str(pj), str(tmp / "edl.json"), modo="dinamico", remover_repeticoes=False)
edl = json.loads((tmp / "edl.json").read_text(encoding="utf-8"))
check(r["audio"] and r["audio"]["bordas"]["fim_na_voz"] >= 3, f"propor_cortes usa a borda pela voz: {r['audio']}")
check(r["densidade"] and "leitura" in r["densidade"], "densidade no resultado e na EDL")
falta = [b for a, b in RAJADAS if not any(m["inicio"] <= b + 0.1 <= m["fim"] for m in edl["manter"])]
check(not falta, f"nenhuma fala perde o fim (consoante incluída): {falta}")
check(edl["duracao_final_s"] < dur - 2.0, f"pausas longas saíram: {edl['duracao_final_s']} s")

# --- conferência da emenda pelo áudio (transcrição simulada)
chamadas = {"n": 0}
def ouvido(wavp):
    chamadas["n"] += 1
    return ["p0a", "p0b.", "p1a"] if chamadas["n"] == 1 else (["p0a", "p0b.", "p1a", "p1b."] if chamadas["n"] == 2 else ["p1a", "p1b.", "p2a", "p2b."])
m3, rel = B.verificar_emendas_audio(wav, [[0.4, 1.75], [1.85, 2.98], [3.6, 4.8]], pal, transcrever=ouvido)
check(rel["n_emendas"] == 2, "uma conferência por emenda")
check(rel["ajustadas"] == 1 and abs(m3[0][1] - 1.79) < 1e-6 and rel["ok"] == 2, f"emenda que perde palavra ganha borda vizinha: {rel} {m3}")
m4, rel4 = B.verificar_emendas_audio(wav, [[0.4, 1.8], [3.6, 4.8]], pal, transcrever=lambda w: [])
check(rel4["ok"] == 0 and len(rel4["conferir_de_ouvido"]) == 1 and m4 == [[0.4, 1.8], [3.6, 4.8]], "nada ouvido: vai para conferir de ouvido e a EDL não muda")
check(B._achou(["pra", "fazer"], ["para", "fazer", "uma"]) and not B._achou(["tiver", "link"], ["quem", "tiver"]), "comparação tolera 'pra/para' e exige todas na ordem")

# --- fim no quadro calmo (15/11/2026): quadro mais parado em [última palavra + 0,24, + 0,52], antes da mão ir à câmera
orig_mov = B._movimento_baixo
try:
    B._movimento_baixo = lambda v, t0, d, **k: [(round(t0 + i * 0.05, 3), m) for i, m in enumerate([3, 3, 3, 3, 2, 2, 1.5, 1.2, 0.4, 0.9, 1.1, 0.8, 0.7, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])]
    f, inf = B.fim_calmo(__file__, 10.10, 10.0, 20.0)   # quadros desde 9,8: o mais parado da janela 10,24–10,52
    check(10.24 <= f <= 10.52 and inf["fim_antes"] == 10.10, f"fim vai para o quadro calmo da janela: {f} {inf}")
    B._movimento_baixo = lambda v, t0, d, **k: [(round(t0 + i * 0.05, 3), m) for i, m in enumerate([1, 1, 1, 1, 1, 1, 0.9, 0.8, 0.7, 30, 30, 30, 30, 30, 30, 30, 30])]
    f2, inf2 = B.fim_calmo(__file__, 10.10, 10.0, 20.0)   # mão em 10,25: o teto cai antes da janela
    check(f2 == 10.10 and inf2.get("mao_s"), f"mão vindo antes da janela: fica o fim atual ({f2}, {inf2})")
    f3, inf3 = B.fim_calmo(__file__, 10.10, 10.0, 10.2)
    check(f3 == 10.10 and inf3["motivo"] == "sem espaço depois da fala", "bruto acaba logo depois da fala: nada muda")
finally:
    B._movimento_baixo = orig_mov

print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
