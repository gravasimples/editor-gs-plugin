"""Fase A (07/11/2026): áudio final no volume de rede social (−16 LUFS, pico −1,5 dBTP), 1080p como padrão e seção "Takes que melhorariam".
Tudo em pasta temporária. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_audio_final.py"""
import inspect, json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import util
import servidor
from servico import textos

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-audio-"))

def video(nome, amp=0.02, audio=True, dur=6):
    out = tmp / nome
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=30:d={dur}"]
    if audio:  # voz falsa: tom com volume oscilando (fala varia), bem baixo
        cmd += ["-f", "lavfi", "-i", f"aevalsrc='{amp}*sin(2*PI*220*t)*(0.4+0.6*abs(sin(2*PI*0.7*t)))':s=48000:d={dur}", "-shortest", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, check=True); return out

baixo = video("baixo.mp4")
r = util.finalizar_audio(baixo)
check(r["feito"] and abs(r["depois"]["lufs"] - util.ALVO_LUFS) <= 1.0 and r["depois"]["true_peak"] <= -1.0, f"volume baixo vai para −16 LUFS com pico ≤ −1 dBTP ({r})")
check(util.info_midia(baixo)["codec_video"] == "h264" and abs(util.info_midia(baixo)["duracao_s"] - 6) < 0.3, "vídeo copiado, mesma duração")
check(not list(tmp.glob("*.audio-tmp*")), "não deixa arquivo temporário")
r2 = util.finalizar_audio(baixo)
check(r2["feito"] is False and r2["motivo"] == "já no alvo", "segunda passada não reprocessa (já no alvo)")
alto = video("alto.mp4", amp=0.98)
r3 = util.finalizar_audio(alto)
check(r3["feito"] and r3["depois"]["true_peak"] <= -1.0, f"áudio estourado volta para pico seguro ({r3.get('antes')} → {r3.get('depois')})")
mudo = video("mudo.mp4", audio=False)
check(util.finalizar_audio(mudo) == {"feito": False, "motivo": "sem áudio"}, "vídeo sem áudio passa direto")

# _final no servidor: só em entrega sem erro, desligável, falha vira aviso
v = video("entrega.mp4")
res = servidor._final({"video": str(v)}, str(v))
check(res["audio_final"]["feito"] is True, "_final normaliza a entrega e devolve audio_final")
check(servidor._final({"erro": "x"}, str(v)) == {"erro": "x"}, "_final não mexe em resultado com erro")
os.environ["EDITOR_GS_AUDIO_FINAL"] = "0"
v2 = video("entrega2.mp4")
check("audio_final" not in servidor._final({"video": str(v2)}, str(v2)), "EDITOR_GS_AUDIO_FINAL=0 desliga")
os.environ.pop("EDITOR_GS_AUDIO_FINAL")
check("audio_final" not in servidor._final({"capa": "x.png"}, str(tmp / "nao-existe.mp4")), "sem arquivo de vídeo: não faz nada")
orig = servidor.finalizar_audio
servidor.finalizar_audio = lambda p: (_ for _ in ()).throw(RuntimeError("ffmpeg sumiu"))
res = servidor._final({"video": str(v2)}, str(v2))
check(res["audio_final"]["feito"] is False and "ffmpeg sumiu" in res["audio_final"]["aviso"], "falha na normalização vira aviso, entrega segue")
servidor.finalizar_audio = orig
fonte = inspect.getsource(servidor)
for nome in ("montagem.montar,", "acabamento.montar_remotion,", "montagem.montar_dividido,", "montagem.montar_pip,", "montagem.montar_react,",
             "montagem.montar_antes_depois,", "imagem.animar_carrossel,", "voz.montar_locucao,", "voz.dublar,", "longos.adicionar_trilha,"):
    check(f"_final(_ok({nome}" in fonte, f"entrega final passa pelo áudio: {nome.rstrip(',')}")

# 1080p como padrão
for fn in (servidor.montar, servidor.montar_remotion, servidor.montar_dividido, servidor.montar_locucao, servidor.dublar, servidor.reenquadrar):
    check(inspect.signature(fn).parameters["resolucao"].default == "1080p", f"{fn.__name__} sai em 1080p por padrão")
est = [json.loads(p.read_text(encoding="utf-8")) for p in (RAIZ / "estilos").glob("*.json") if p.name != "elementos.json"]
check(all(e.get("saida", {}).get("resolucao", "1080p") == "1080p" for e in est), "estilos da casa em 1080p")
check(inspect.signature(servidor.propor_cortes).parameters["min_pausa_s"].default == 0.3, "corte inteligente tira pausas acima de 0,3 s")

# textos: seção nova
check(textos.chave_de("Takes que melhorariam") == "takes" and textos.ROTULOS["takes"] == "Takes que melhorariam", "seção Takes que melhorariam reconhecida")
check(textos.chave_de("Para gravar") == "gravar" and textos.chave_de("Pendências") == "pendencias", "seções antigas continuam iguais")
ag = (RAIZ / "workspace" / "AGENTS.md").read_text(encoding="utf-8")
check("**Corte:**" in ag and "**Som:**" in ag and "audio_final" in ag and "## Takes que melhorariam" in ag, "AGENTS.md pede o resumo em Corte / Na tela / Estilo / Som e os takes")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
