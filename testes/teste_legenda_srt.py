"""Testes isolados de legenda_de_srt (ASS no estilo da marca a partir de um SRT traduzido). Tudo em pasta temporária; nunca toca workspace/."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import legenda, montagem
from editor_video.util import ErroFerramenta

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

SRT = """1
00:00:00,200 --> 00:00:01,400
Turn on *Studio Mode* before the class

2
00:00:01,500 --> 00:00:02,600
Scenes
and Sources stay in place

3
00:00:02,650 --> 00:00:02,900


4
00:00:02,950 --> 00:00:03,000
OK
"""

with tempfile.TemporaryDirectory(prefix="editor-gs-srt-", ignore_cleanup_errors=True) as tmp:
    pasta = Path(tmp); os.chdir(pasta)
    estilo = json.loads((RAIZ / "estilos" / "padrao.json").read_text(encoding="utf-8"))
    srt = pasta / "legenda-en.srt"; srt.write_text(SRT, encoding="utf-8")

    r = legenda.legenda_de_srt(srt, pasta / "legenda-en.ass", estilo, formato="9x16")
    ass = (pasta / "legenda-en.ass").read_text(encoding="utf-8")
    dial = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    check(r["n_blocos"] == 3 and len(dial) == 3, f"bloco vazio fica de fora: 3 eventos ({r['n_blocos']})")
    check(r["karaoke"] is False and "\\k" not in ass and "PlayResX: 1080" in ass and "PlayResY: 1920" in ass, "sem karaokê e resolução 9x16")
    check("Style: Legenda,Inter ExtraBold,72," in ass, "estilo padrão (Inter ExtraBold 72) no cabeçalho")
    check(dial[0].startswith("Dialogue: 0,0:00:00.20,0:00:01.40,Legenda,"), f"tempos do SRT preservados ({dial[0][:45]})")
    t0 = dial[0].split(",,0,0,0,,", 1)[1]
    check("\\N" in t0 and all(len(re.sub(r"\{[^}]*\}", "", x)) <= 22 for x in t0.split("\\N")), f"bloco longo quebrado em 2 linhas de até 22 caracteres ({t0})")
    check("{\\c&H001596F7}Studio Mode{\\c&H00FFFFFF}" in t0 and r["destaques"] == 1, "destaque *…* vira laranja e volta ao branco")
    check("*" not in t0, "asteriscos não vazam para a legenda")
    t1 = dial[1].split(",,0,0,0,,", 1)[1]
    check("Scenes and Sources" in t1.replace("\\N", " "), "quebra de linha do SRT é refeita pelo tamanho")
    check(r["blocos_longos"] == 0 and r["max_chars"] == 22 and r["duracao_s"] == 3.0, "sem blocos longos; max_chars 22; duração do último bloco")

    r2 = legenda.legenda_de_srt(srt, pasta / "legenda-en-16x9.ass", estilo, formato="16x9")
    a2 = (pasta / "legenda-en-16x9.ass").read_text(encoding="utf-8")
    check(r2["max_chars"] == 38 and "\\N" not in a2.splitlines()[-3] and "PlayResX: 1920" in a2, "16x9: 38 caracteres por linha, bloco 1 cabe numa linha")

    longo = pasta / "longo.srt"; longo.write_text("1\n00:00:00,000 --> 00:00:03,000\nthis sentence is long enough to need more than two lines of twenty two characters\n", encoding="utf-8")
    r3 = legenda.legenda_de_srt(longo, pasta / "longo.ass", estilo, formato="9x16")
    check(r3["blocos_longos"] == 1 and r3["n_blocos"] == 1, "bloco que não cabe em 2 linhas é contado em blocos_longos")

    est2 = json.loads(json.dumps(estilo)); est2["legenda"]["maiusculas"] = True; est2["legenda"]["animacao"] = "pop"
    legenda.legenda_de_srt(srt, pasta / "maius.ass", est2, formato="9x16", max_chars=40)
    a4 = (pasta / "maius.ass").read_text(encoding="utf-8"); d4 = [l for l in a4.splitlines() if l.startswith("Dialogue:")][0]
    check("STUDIO MODE" in d4 and "\\t(0,110,\\fscx118" in d4, "maiúsculas e animação pop do estilo aplicadas")
    check("\\N" not in d4.split(",,0,0,0,,", 1)[1], "max_chars=40 mantém o bloco 1 numa linha")

    try:
        legenda.legenda_de_srt(pasta / "nao-existe.srt", pasta / "x.ass", estilo); check(False, "SRT inexistente dá erro")
    except ErroFerramenta:
        check(True, "SRT inexistente dá erro")
    vazio = pasta / "vazio.srt"; vazio.write_text("1\n00:00:00,000 --> 00:00:01,000\n   \n", encoding="utf-8")
    try:
        legenda.legenda_de_srt(vazio, pasta / "x.ass", estilo); check(False, "SRT sem texto dá erro")
    except ErroFerramenta as e:
        check("sem blocos" in str(e), "SRT sem texto dá erro")
    (pasta / "entrada").mkdir()
    try:
        legenda.legenda_de_srt(srt, pasta / "entrada" / "x.ass", estilo); check(False, "não grava em entrada/")
    except ErroFerramenta:
        check(True, "não grava em entrada/")

    # o ASS é aceito pelo ffmpeg/libass numa montagem curta
    v = pasta / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:d=3.2", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                    "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(v)], check=True)
    try:
        m = montagem.montar(v, pasta / "final_9x16_en.mp4", formato="9x16", legenda_ass=pasta / "legenda-en.ass", resolucao="720p")
        check((pasta / "final_9x16_en.mp4").stat().st_size > 10_000, f"montar com a legenda ASS queimada ({m.get('largura')}x{m.get('altura')})")
    except Exception as e:
        check(False, f"montar com a legenda ASS: {e}")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
