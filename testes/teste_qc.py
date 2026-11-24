"""Portão técnico do Revisor (14/11/2026): vídeo sintético com defeitos plantados (quadro preto seco, imagem parada, silêncio longo,
estalo e salto de volume em emendas, palavra dita duas vezes) e um vídeo limpo com passagem escura gradual que não pode virar problema.
Rodar: python -X utf8 -I testes/teste_qc.py"""
import json, os, subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-qc-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import qc
from editor_video.util import FFMPEG

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

SR = 48000; DUR = 14.0
rng = np.random.default_rng(3)
def voz(n, db):  # rajadas de 4 Hz, parecidas com sílabas
    t = np.arange(n) / SR
    return rng.normal(0, 10 ** (db / 20), n) * (0.3 + 0.7 * np.sin(2 * np.pi * 4 * t) ** 2)
def salvar_wav(x, p):
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())

# áudio com defeitos: emenda em 2,0 s numa pausa com estalo; emenda em 4,0 s com a voz 12 dB mais alta depois; silêncio de 7,0 a 8,6 s
x = rng.normal(0, 10 ** (-60 / 20), int(SR * DUR))
for a, b, db in [(0.3, 1.8, -24), (2.2, 4.0, -24), (4.0, 7.0, -12), (8.6, 13.5, -12)]:
    i, j = int(a * SR), int(b * SR); x[i:j] = voz(j - i, db)
k = int(2.0 * SR); x[k:k + 96] = 0.9 * np.sign(rng.normal(size=96))
salvar_wav(x, tmp / "a.wav")
# vídeo: imagem que mexe, quadro preto seco em 3,0–3,1 s, imagem parada de 9,0 a 13,5 s
ruim = tmp / "ruim.mp4"
fc = ("[0:v]trim=0:9,setpts=PTS-STARTPTS[a];[0:v]trim=9:9.04,setpts=PTS-STARTPTS,loop=loop=150:size=1:start=0,trim=0:5,setpts=PTS-STARTPTS[b];"
      "[a][b]concat=n=2:v=1:a=0,drawbox=t=fill:c=black:enable='between(t,3.0,3.1)'[v]")
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=320x568:r=30:d={DUR}", "-i", str(tmp / "a.wav"),
                "-filter_complex", fc, "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(ruim)], check=True)
edl = tmp / "edl.json"; edl.write_text(json.dumps({"manter": [{"inicio": 10, "fim": 12}, {"inicio": 20, "fim": 22}, {"inicio": 30, "fim": 40}]}))
check(qc.emendas_da_edl(str(edl)) == [2.0, 4.0], "emendas pela EDL (soma dos trechos)")
pal = tmp / "palavras.json"
ws = "então o o seu o seu vídeo o que que é isso".split()
pal.write_text(json.dumps({"palavras": [{"palavra": " " + w, "inicio": 0.5 + 0.3 * i, "fim": 0.7 + 0.3 * i} for i, w in enumerate(ws)]}, ensure_ascii=False), encoding="utf-8")

r = qc.conferir_tecnico(str(ruim), edl_json=str(edl), palavras_json=str(pal), formato="reels", saida_json=str(tmp / "qc.json"))
tipos = lambda t: [p for p in r["problemas"] if p["tipo"] == t]
achou = lambda t, a, b, txt="": any(a <= p["instante_s"] <= b and txt in p["descricao"] for p in tipos(t))
for p in r["problemas"]: print("   ", p["instante_s"], p["gravidade"], p["tipo"], p["descricao"])
check(not r["ok"], "vídeo com defeitos não sai ok")
check(achou("quadro_preto", 2.9, 3.2), "quadro preto seco na imagem")
check(achou("imagem_parada", 8.8, 9.3), "imagem parada acima de 4 s em Reels")
check(achou("trecho_mudo", 6.9, 7.2), "silêncio longo no meio")
check(achou("audio", 1.9, 2.1, "estalo"), "estalo na emenda de 2 s")
check(achou("audio", 3.9, 4.1, "sobe"), "salto de volume na emenda de 4 s")
rep = [p["descricao"] for p in tipos("take_repetido")]
check(any('"o o"' in d for d in rep) and any('"o seu o seu"' in d for d in rep), "palavra e par ditos duas vezes")
check(not any("que que" in d for d in rep), "\"o que que é\" é fala comum, não refação")
check("lufs" in r["medidas"] and (tmp / "qc.json").is_file(), "medidas de volume e JSON gravado")
check(all(p["origem"] == "medido" and {"instante_s", "gravidade", "tipo", "descricao", "sugestao"} <= set(p) for p in r["problemas"]), "mesmo formato dos problemas do Gemini")

# vídeo limpo: imagem que mexe e escurece aos poucos até o marinho da tela final; fala contínua no alvo
y = voz(int(SR * 8), -14); salvar_wav(y, tmp / "b.wav")
limpo = tmp / "limpo.mp4"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x568:r=30:d=8", "-i", str(tmp / "b.wav"),
                "-filter_complex", "[0:v]split[x][y];[x]trim=0:6,setpts=PTS-STARTPTS,fade=t=out:st=5.5:d=0.5:color=0x000921[p];"
                "[y]trim=6:8,setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.5:color=0x000921[q];[p][q]concat=n=2:v=1:a=0[v];[1:a]loudnorm=I=-16:TP=-1.5[a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", str(limpo)], check=True)
r2 = qc.conferir_tecnico(str(limpo))
for p in r2["problemas"]: print("   ", p["instante_s"], p["gravidade"], p["tipo"], p["descricao"])
check(not any(p["tipo"] == "quadro_preto" for p in r2["problemas"]), "passagem gradual para o marinho não é quadro preto")
check(not any(p["tipo"] in ("trecho_mudo", "imagem_parada") for p in r2["problemas"]), "fala contínua e imagem que mexe: sem mudo e sem parada")

# revisar_video: medido vai ao Gemini e volta junto; Gemini fora do ar não derruba
from editor_video import revisao
from editor_video.util import ErroFerramenta
visto = {}
def gem_falso(v, **kw):
    visto.update(kw); return {"video": str(v), "revisao": {"nota_geral": 7, "problemas": [{"instante_s": 5.0, "gravidade": "alta", "tipo": "continuidade", "descricao": "pula ideia"}]}}
rv = revisao.revisar_video(str(ruim), edl_json=str(edl), palavras_json=str(pal), saida_json=str(tmp / "rev.json"), _gemini=gem_falso)
check("Já medido pelo ffmpeg" in visto.get("prompt_extra", "") and "estalo" in visto["prompt_extra"], "o medido vai ao Gemini como já medido")
orig = {p["origem"] for p in rv["problemas"]}
check(orig == {"medido", "gemini"} and rv["problemas"][0]["gravidade"] == "alta" and (tmp / "rev.json").is_file(), "problemas juntam medido e Gemini, mais grave primeiro")
def gem_fora(v, **kw): raise ErroFerramenta("GEMINI_API_KEY ausente")
rv2 = revisao.revisar_video(str(ruim), edl_json=str(edl), _gemini=gem_fora)
check(rv2["revisao"] is None and "aviso_gemini" in rv2 and rv2["tecnico"]["problemas"], "sem Gemini volta o técnico com aviso")
rv3 = revisao.revisar_video(str(ruim), edl_json=str(edl), inicio_s=1.5, fim_s=2.5, _gemini=gem_fora)
check(all(p["instante_s"] == 0 or 1.0 <= p["instante_s"] <= 3.0 for p in rv3["problemas"]), "segunda rodada num trecho: só o medido daquele trecho")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
