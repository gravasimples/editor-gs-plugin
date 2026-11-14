"""HyperFrames como motor alternativo de overlay (10/11/2026). Sem depender do CLI: `sobrepor` com um WebM alpha feito pelo ffmpeg (alpha respeitado,
áudio intacto, duração do vídeo), preenchimento dos marcadores/atributos oficiais, e o erro claro (com o comando de instalação) quando o CLI falta,
no módulo e na ferramenta MCP. Com o CLI instalado em hyperframes/node_modules: render real de 1 s do bloco manchete (alpha yuva420p) e sobreposição.
Rodar: C:\\Users\\rapha\\.venvs\\editor-gs\\Scripts\\python.exe -I -X utf8 testes\\teste_hyperframes.py (na raiz do repo)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import hyperframes as hf
from editor_video.util import FFMPEG, FFPROBE, ErroFerramenta, info_midia
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def pixel_rgb(video, inst, x, y):
    """RGB de um pixel do vídeo no instante dado (ffmpeg → rawvideo 2x2; crop de 1 px falha em yuv420p)."""
    r = subprocess.run([FFMPEG, "-v", "error", "-ss", str(inst), "-i", str(video), "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    return tuple(r.stdout[:3])

def pix_fmt_vp9(webm):
    r = subprocess.run([FFPROBE, "-v", "error", "-c:v", "libvpx-vp9", "-show_entries", "stream=pix_fmt", "-of", "csv=p=0", str(webm)], capture_output=True, text=True)
    return r.stdout.strip()

with tempfile.TemporaryDirectory(prefix="gs-teste-hf-", ignore_cleanup_errors=True) as tmp:
    pasta = Path(tmp); os.chdir(pasta)
    # vídeo base: cinza escuro 320x568, 3 s, com tom de 440 Hz
    base = pasta / "base.mp4"
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x202020:s=320x568:r=25:d=3", "-f", "lavfi", "-i", "sine=f=440:d=3",
                    "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(base)], check=True)
    # overlay alpha pelo ffmpeg: fundo transparente com um quadrado laranja no canto superior esquerdo (0..80 x 0..80), 1 s
    ov = pasta / "ov.webm"
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black@0.0:s=320x568:r=25:d=1,format=rgba",
                    "-vf", "drawbox=x=0:y=0:w=80:h=80:color=0xF79615@1.0:t=fill:replace=1,format=yuva420p", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "20", str(ov)], check=True)
    check(pix_fmt_vp9(ov) == "yuva420p", f"overlay sintético tem alpha ({pix_fmt_vp9(ov)})")
    # sobrepor a partir de 1 s
    r = hf.sobrepor(base, ov, pasta / "_trabalho" / "final.mp4", inicio_s=1.0)
    m = info_midia(r["video"])
    check(abs(m["duracao_s"] - 3.0) < 0.1 and m["tem_audio"] and m["codec_audio"] == "aac", f"mp4 final: {m['duracao_s']} s, áudio {m['codec_audio']} (duração do vídeo, áudio copiado)")
    p_antes = pixel_rgb(r["video"], 0.5, 20, 20); p_dentro = pixel_rgb(r["video"], 1.5, 20, 20); p_fora = pixel_rgb(r["video"], 1.5, 200, 300)
    check(max(p_antes) < 60, f"antes de inicio_s o quadro é só o vídeo {p_antes}")
    check(p_dentro[0] > 200 and 100 < p_dentro[1] < 190 and p_dentro[2] < 80, f"dentro do quadrado laranja do overlay {p_dentro}")
    check(max(p_fora) < 60, f"fora do quadrado o alpha deixa o vídeo passar {p_fora}")
    check(not r["overlay_redimensionado"], "overlay do mesmo tamanho não é redimensionado")
    # overlay de tamanho diferente é redimensionado
    ov2 = pasta / "ov2.webm"
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black@0.0:s=160x284:r=25:d=1,format=rgba",
                    "-vf", "drawbox=x=0:y=0:w=40:h=40:color=0xF79615@1.0:t=fill:replace=1,format=yuva420p", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "20", str(ov2)], check=True)
    r2 = hf.sobrepor(base, ov2, pasta / "_trabalho" / "final2.mp4")
    check(r2["overlay_redimensionado"] and info_midia(r2["video"])["largura"] == 320, "overlay menor é redimensionado ao tamanho do vídeo")
    try:
        hf.sobrepor(base, ov, pasta / "_trabalho" / "x.mp4", inicio_s=9); check(False, "deveria recusar inicio_s depois do fim")
    except ErroFerramenta as e:
        check("depois do fim" in str(e), f"inicio_s depois do fim recusa: {e}")
    # marcadores e atributos oficiais (data-width/height/duration/fps no elemento raiz)
    html = hf.html_do_bloco("manchete", {"kicker": "Áudio", "manchete": "Teste"})
    check("{{DADOS}}" not in html and '"kicker": "Áudio"' in html, "html_do_bloco substitui {{DADOS}} pelo JSON (UTF-8)")
    pre = hf._preencher(html, 720, 1280, 25, 2.5)
    check(all(m not in pre for m in hf.MARCADORES), "todos os marcadores preenchidos")
    raiz = pre[pre.index("data-composition-id"):]; raiz = raiz[:raiz.index(">")]
    check('data-width="720"' in raiz and 'data-height="1280"' in raiz and 'data-duration="2.5"' in raiz and 'data-fps="25"' in raiz, f"atributos oficiais no elemento raiz: {raiz[:160]}")
    pre2 = hf._preencher('<div data-composition-id="x"><p>oi</p></div>', 100, 200, 30, 1)
    check('data-duration="1"' in pre2 and 'data-width="100"' in pre2, "HTML sem os atributos ganha data-width/height/duration/fps")
    try:
        hf._preencher("<div>sem raiz</div>", 1, 1, 1, 1); check(False, "deveria recusar HTML sem data-composition-id")
    except ErroFerramenta as e:
        check("data-composition-id" in str(e), "HTML sem data-composition-id recusa")
    blocos = [b["bloco"] for b in hf.listar_blocos()]
    check("manchete" in blocos and "legenda-cinetica" in blocos, f"blocos da marca listados: {blocos}")
    try:
        hf.html_do_bloco("nao-existe", {}); check(False, "bloco inexistente deveria falhar")
    except ErroFerramenta as e:
        check("Disponíveis" in str(e), "bloco inexistente lista os disponíveis")
    # CLI ausente: erro claro com o comando de instalação, no módulo e na ferramenta MCP (sem travar)
    cli_real, gsap_real = hf.CLI, hf.GSAP
    hf.CLI = pasta / "nao-existe" / "hyperframes.cmd"
    try:
        check(not hf.instalado(), "instalado() é False sem o CLI")
        try:
            hf.renderizar_overlay("<div data-composition-id='a'></div>", pasta / "_trabalho" / "x.webm"); check(False, "deveria falhar sem CLI")
        except ErroFerramenta as e:
            check("instalar-hyperframes" in str(e) and "não está instalado" in str(e), f"erro claro sem CLI: {str(e)[:120]}")
        s = servidor.grafismo_hyperframes(str(base), "manchete", json.dumps({"manchete": "x"}), str(pasta / "_trabalho" / "g.mp4"))
        check("erro" in s and "instalar-hyperframes" in s["erro"], f"servidor.grafismo_hyperframes devolve erro com o comando: {s}")
        s2 = servidor.grafismo_hyperframes(str(base), "manchete", "{isso não é json", str(pasta / "_trabalho" / "g.mp4"))
        check("erro" in s2, f"dados_json inválido vira erro: {s2}")
    finally:
        hf.CLI, hf.GSAP = cli_real, gsap_real
    # JSON inválido também com CLI presente, antes de renderizar
    s3 = servidor.grafismo_hyperframes(str(base), "manchete", "{isso não é json", str(pasta / "_trabalho" / "g.mp4"))
    check("erro" in s3 and "dados_json" in s3["erro"], f"dados_json inválido: {s3.get('erro', '')[:80]}")
    s4 = servidor.grafismo_hyperframes(str(base), "manchete", "{}", str(pasta / "entrada" / "g.mp4"))
    check("erro" in s4 and "entrada" in s4["erro"], "recusa gravar em entrada/")
    # com o CLI instalado: render real de 1 s (pequeno) + sobreposição pela ferramenta
    if hf.instalado():
        r = hf.renderizar_overlay(hf.html_do_bloco("manchete", {"kicker": "OBS", "manchete": "Grava em dois formatos", "destaque": "dois formatos"}),
                                  pasta / "_trabalho" / "m.webm", 320, 568, 25, 1.0)
        check(Path(r["webm"]).exists() and r["alpha"] and pix_fmt_vp9(r["webm"]) == "yuva420p", f"render real 1 s: alpha {r['alpha']} ({r['origem']}), {r['tempo_s']} s")
        check(abs(r["duracao_s"] - 1.0) < 0.05 and (r["largura"], r["altura"]) == (320, 568) and r["fps"] == 25.0, f"duração/tamanho/fps do WebM: {r['duracao_s']} s {r['largura']}x{r['altura']} {r['fps']} fps")
        # no fim do overlay (0,9 s) a manchete está na tela: há pixel marinho na faixa de baixo; o topo continua transparente
        rgba = subprocess.run([FFMPEG, "-v", "error", "-c:v", "libvpx-vp9", "-ss", "0.6", "-i", r["webm"], "-frames:v", "1", "-vf", "crop=2:2:10:10", "-f", "rawvideo", "-pix_fmt", "rgba", "-"], capture_output=True).stdout
        check(len(rgba) >= 4 and rgba[3] == 0, f"canto superior do overlay é transparente (alpha={rgba[3] if len(rgba) >= 4 else '?'})")
        s = servidor.grafismo_hyperframes(str(base), "legenda-cinetica", json.dumps({"palavras": [{"palavra": "olha", "inicio": 0.0, "fim": 0.3}, {"palavra": "só", "inicio": 0.35, "fim": 0.6}]}),
                                          str(pasta / "_trabalho" / "leg.mp4"), inicio_s=0.5, duracao_s=1.0)
        check("erro" not in s and s["motor"] == "hyperframes" and abs(s["duracao_final_s"] - 3.0) < 0.1 and s["tem_audio"], f"servidor.grafismo_hyperframes: {json.dumps({k: v for k, v in s.items() if k != 'overlay'}, ensure_ascii=False)[:200]}")
        # em 0,7 s do vídeo (0,2 s do overlay) a linha "olha só" está na tela: faixa de baixo tem a caixa marinho (azul > vermelho) ou texto branco/laranja
        faixa = [pixel_rgb(s["video"], 0.7, x, y) for x in (120, 160, 200) for y in range(440, 480, 8)]
        check(any((p[2] > p[0] and p[2] > 20) or max(p) > 150 for p in faixa), f"legenda cinética aparece no vídeo final em 0,7 s (amostras: {faixa[:4]}…)")
    else:
        print(f"SKIP render real: HyperFrames não instalado ({hf.COMANDO_INSTALAR})")
os.chdir(RAIZ)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
