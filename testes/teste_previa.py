"""Prévia 720p (10/11/2026): `montar(previa=True)` e `montar_remotion(previa=True)` gravam `<saida>_previa.mp4` em 720p e devolvem previa/resolucao/tempo_s.
Vídeo sintético de 2 s. O Remotion pula (SKIP) se não estiver disponível. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_previa.py"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import montagem, acabamento
from editor_video.util import FFMPEG, info_midia, ErroFerramenta, caminho_previa
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory(prefix="gs-teste-previa-", ignore_cleanup_errors=True) as tmp:
    pasta = Path(tmp); os.chdir(pasta)
    v = pasta / "bruto.mp4"
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30:d=2",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(v)], check=True)
    check(caminho_previa(pasta / "saida" / "final_9x16.mp4").name == "final_9x16_previa.mp4", "caminho_previa: sufixo _previa")
    # montar
    m = montagem.montar(v, pasta / "saida" / "final_9x16.mp4", formato="9x16", previa=True)
    check(m["previa"] is True and m["video"].endswith("final_9x16_previa.mp4"), f"montar(previa): arquivo {Path(m['video']).name}")
    i = info_midia(m["video"])
    check(i["largura"] == 720 and i["altura"] == 1280 and m["resolucao"] == "720x1280", f"ffprobe: {i['largura']}x{i['altura']} (resolucao={m['resolucao']})")
    check(i["fps"] == 30 and abs(i["duracao_s"] - 2.0) < 0.2 and i["tem_audio"], f"fps mantido ({i['fps']}), duração {i['duracao_s']} s, áudio")
    check(isinstance(m["tempo_s"], float) and m["tempo_s"] >= 0, f"tempo_s = {m['tempo_s']}")
    check(not (pasta / "saida" / "final_9x16.mp4").exists(), "o arquivo final não é tocado pela prévia")
    m2 = montagem.montar(v, pasta / "saida" / "final_9x16.mp4", formato="9x16", resolucao="720p")
    check("previa" not in m2 and "tempo_s" not in m2, "sem previa, o resultado não ganha chaves novas")
    # pelo servidor (com audio_final)
    s = servidor.montar(str(v), str(pasta / "saida" / "final_16x9.mp4"), formato="16x9", previa=True)
    check("erro" not in s and s["previa"] and s["largura"] == 1280 and s["altura"] == 720 and Path(s["video"]).name == "final_16x9_previa.mp4", f"servidor.montar(previa): {s.get('resolucao')} ({s.get('tempo_s')} s)")
    # montar_remotion
    estilo = json.load(open(RAIZ / "estilos" / "padrao.json", encoding="utf-8"))
    try:
        rm = acabamento.montar_remotion(v, pasta / "saida" / "remotion.mp4", formato="9x16", estilo=estilo, frase_impacto="Teste da prévia", tela_final=False, previa=True)
        ir = info_midia(rm["video"])
        check(rm["previa"] is True and Path(rm["video"]).name == "remotion_previa.mp4" and ir["largura"] == 720 and ir["altura"] == 1280, f"montar_remotion(previa): {Path(rm['video']).name} {ir['largura']}x{ir['altura']}")
        check(rm["resolucao"] == "720x1280" and rm["tempo_s"] > 0 and rm["frase_impacto"] is True, f"resolucao={rm['resolucao']}, tempo_s={rm['tempo_s']}, resto do resultado intacto")
    except ErroFerramenta as e:
        print("SKIP montar_remotion(previa):", str(e)[:120].replace("\n", " "))
    import inspect
    check(inspect.signature(servidor.montar_remotion).parameters["previa"].default is False, "servidor.montar_remotion expõe previa=False")
os.chdir(RAIZ)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
