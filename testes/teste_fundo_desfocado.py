"""Fundo desfocado pronto (11/11/2026): vídeo deitado → 9:16 gera o fundo pelo ffmpeg em tamanho mínimo, em vez de o navegador
decodificar o vídeo inteiro uma segunda vez por quadro. Isolado: vídeo sintético numa pasta temporária.
Rodar: ~/.venvs/editor-gs/bin/python -X utf8 -I testes/teste_fundo_desfocado.py"""
import sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import acabamento as a  # noqa: E402
from editor_video.util import FFMPEG, info_midia, rodar  # noqa: E402

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="fundo-teste-"))
src = tmp / "deitado.mp4"
rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=3",
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(src)])
f = a.fundo_desfocado(src, tmp / "fundo.mp4", 1080, 1920)
i = info_midia(f) if f else {}
check(f is not None and f.exists(), "fundo gerado")
check((i.get("largura"), i.get("altura")) == (180, 320), f"fundo em 1/6 do 9:16 ({i.get('largura')}x{i.get('altura')})")
check(abs(float(i.get("duracao_s") or 0) - 3.0) < 0.15, f"mesma duração do vídeo ({i.get('duracao_s')})")
f2 = a.fundo_desfocado(src, tmp / "fundo_16x9.mp4", 1920, 1080)
check(f2 is not None and (info_midia(f2)["largura"], info_midia(f2)["altura"]) == (320, 180), "deitado também serve (vertical → 16:9)")
check(a.fundo_desfocado(tmp / "nao_existe.mp4", tmp / "x.mp4", 1080, 1920) is None, "ffmpeg falhou → None (Montagem volta ao filtro CSS)")
check("video_fundo" in (RAIZ / "remotion" / "src" / "Montagem.tsx").read_text(encoding="utf-8"), "Montagem usa video_fundo quando vem nas props")
print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
