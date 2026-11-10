"""HyperFrames (HeyGen, Apache-2.0) como motor ALTERNATIVO de grafismos/overlays — teste integrado de 10/11/2026, não é o padrão.
HTML + GSAP com `data-*` de tempo → WebM VP9 com alpha (yuva420p) pelo CLI `hyperframes render --format webm` (Chrome do sistema ou o que
`HYPERFRAMES_BROWSER_PATH` apontar) → `sobrepor` cola no vídeo com ffmpeg respeitando o alpha, áudio intacto.
Instalação é local e separada (`scripts/instalar-hyperframes.cmd` ou `.sh` → `hyperframes/node_modules/`); sem ela todas as funções
devolvem ErroFerramenta com o comando de instalação. Blocos da marca em `hyperframes/blocos/*.html` com os marcadores
{{LARGURA}}, {{ALTURA}}, {{DURACAO}}, {{FPS}} e {{DADOS}} (JSON). Documentação: docs/HYPERFRAMES.md."""
import json, os, re, shutil, subprocess, sys, time, uuid
from pathlib import Path

from .util import FFMPEG, FFPROBE, ErroFerramenta, caminho, caminho_saida, info_midia, rodar

try:
    from servico import plataforma
except Exception:  # noqa: BLE001
    plataforma = None

RAIZ = Path(__file__).resolve().parents[3]
HF_DIR = RAIZ / "hyperframes"
BLOCOS = HF_DIR / "blocos"
RENDER_DIR = HF_DIR / "_render"  # projetos temporários de render (fora do git)
WINDOWS = sys.platform == "win32"
CLI = HF_DIR / "node_modules" / ".bin" / ("hyperframes.cmd" if WINDOWS else "hyperframes")
GSAP = HF_DIR / "node_modules" / "gsap" / "dist" / "gsap.min.js"
FONTES = RAIZ / "fontes"
COMANDO_INSTALAR = r"scripts\instalar-hyperframes.cmd" if WINDOWS else "scripts/instalar-hyperframes.sh"
MARCADORES = ("{{LARGURA}}", "{{ALTURA}}", "{{DURACAO}}", "{{FPS}}", "{{DADOS}}")


def instalado() -> bool:
    return CLI.exists() and GSAP.exists()


def _exigir_cli():
    if not instalado():
        raise ErroFerramenta(f"HyperFrames não está instalado (falta {CLI.parent.parent.name}/ em {HF_DIR}). "
                             f"Instale uma vez com `{COMANDO_INSTALAR}` (npm install local, ~100 MB, usa o Chrome do sistema) e tente de novo.")


def _ambiente() -> dict:
    env = plataforma.preparar_path() if plataforma else dict(os.environ)
    ff = Path(FFMPEG).parent
    if ff.is_dir() and str(ff) not in env.get("PATH", ""):
        env["PATH"] = f"{ff}{os.pathsep}{env.get('PATH', '')}"
    env.setdefault("HYPERFRAMES_RENDER_LOCK", "off")  # renders do Editor já rodam um por vez; sem o lock o CLI não espera outro usuário
    env.setdefault("HYPERFRAMES_NO_TELEMETRY", "1")  # o CLI manda telemetria de uso por padrão (`hyperframes telemetry status`); também respeita DO_NOT_TRACK
    return env


def listar_blocos() -> list:
    """Blocos disponíveis em hyperframes/blocos/ (nome sem .html) com a descrição da primeira linha de comentário."""
    out = []
    for p in sorted(BLOCOS.glob("*.html")):
        m = re.search(r"<!--\s*(.*?)\s*-->", p.read_text(encoding="utf-8"), re.S)
        out.append({"bloco": p.stem, "descricao": (m.group(1).splitlines()[0].strip() if m else "")})
    return out


def html_do_bloco(bloco: str, dados: dict) -> str:
    """HTML de um bloco da marca com {{DADOS}} já substituído pelo JSON (os outros marcadores ficam para renderizar_overlay)."""
    p = BLOCOS / f"{bloco}.html"
    if not p.exists():
        raise ErroFerramenta(f"Bloco HyperFrames não encontrado: {bloco}. Disponíveis: {', '.join(b['bloco'] for b in listar_blocos()) or 'nenhum'}")
    return p.read_text(encoding="utf-8").replace("{{DADOS}}", json.dumps(dados or {}, ensure_ascii=False))


def _preencher(html: str, largura: int, altura: int, fps: int, duracao_s: float) -> str:
    """Marcadores → valores; e garante no elemento raiz (data-composition-id) os atributos oficiais do HyperFrames:
    data-width/data-height (tamanho do canvas), data-duration (duração total) e data-fps."""
    html = (html.replace("{{LARGURA}}", str(largura)).replace("{{ALTURA}}", str(altura))
                .replace("{{DURACAO}}", f"{duracao_s:g}").replace("{{FPS}}", str(fps)).replace("{{DADOS}}", "{}"))
    m = re.search(r"<[a-zA-Z][^>]*\bdata-composition-id=", html)
    if not m:
        raise ErroFerramenta("HTML sem elemento raiz com data-composition-id (exigido pelo HyperFrames).")
    ini = m.start(); fim = html.index(">", ini)
    tag = html[ini:fim]
    for attr, val in (("data-width", largura), ("data-height", altura), ("data-duration", f"{duracao_s:g}"), ("data-fps", fps), ("data-start", 0)):
        if re.search(rf"\b{attr}=", tag):
            tag = re.sub(rf'\b{attr}="[^"]*"', f'{attr}="{val}"', tag)
        else:
            tag += f' {attr}="{val}"'
    return html[:ini] + tag + html[fim:]


def _tem_alpha(webm) -> bool:
    """ffprobe com o decodificador libvpx-vp9 (o nativo ignora o canal alpha e diz yuv420p)."""
    r = subprocess.run([FFPROBE, "-v", "error", "-c:v", "libvpx-vp9", "-show_entries", "stream=pix_fmt", "-of", "csv=p=0", str(webm)],
                       capture_output=True, text=True, timeout=60)
    return "yuva420p" in r.stdout


def _png_para_webm(pasta: Path, saida: Path, fps: int):
    """Reserva: sequência RGBA (--format png-sequence) → WebM VP9 yuva420p pelo ffmpeg."""
    pngs = sorted(pasta.rglob("*.png"))
    if not pngs:
        raise ErroFerramenta(f"HyperFrames não escreveu PNGs em {pasta}")
    lista = pasta / "lista.txt"
    lista.write_text("".join(f"file '{p.as_posix()}'\nduration {1 / fps:.6f}\n" for p in pngs), encoding="utf-8")
    rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-r", str(fps), "-i", lista,
           "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "20", "-row-mt", "1", saida])


def renderizar_overlay(html, saida_webm, largura: int = 1080, altura: int = 1920, fps: int = 30, duracao_s: float = 3.0,
                       timeout: int = 1800, workers: int = 0, manter_projeto: bool = False) -> dict:
    """Composição HyperFrames (string HTML ou caminho .html) → WebM VP9 com alpha em `saida_webm`.
    Duração, fps e tamanho entram do jeito oficial: data-duration/data-fps/data-width/data-height no elemento raiz (+ `--fps`).
    O projeto temporário em hyperframes/_render/<id>/ recebe gsap.min.js e as fontes Inter do repo para render sem internet.
    Se o WebM vier sem alpha, refaz por `--format png-sequence` → ffmpeg (yuva420p). Devolve webm, tempo_s, alpha, tamanho_mb…"""
    _exigir_cli()
    if isinstance(html, (str, Path)) and len(str(html)) < 400 and str(html).lower().endswith(".html") and Path(html).exists():
        html = Path(html).read_text(encoding="utf-8")
    if not isinstance(html, str) or "<" not in html:
        raise ErroFerramenta("renderizar_overlay espera uma string HTML ou o caminho de um .html.")
    largura, altura, fps = int(largura), int(altura), int(fps)
    duracao_s = float(duracao_s)
    if largura <= 0 or altura <= 0 or fps <= 0 or duracao_s <= 0:
        raise ErroFerramenta("largura, altura, fps e duracao_s precisam ser positivos.")
    out = caminho_saida(saida_webm)
    if out.suffix.lower() != ".webm":
        raise ErroFerramenta("A saída do overlay precisa ser .webm (VP9 com alpha).")
    proj = RENDER_DIR / uuid.uuid4().hex[:10]
    proj.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        (proj / "index.html").write_text(_preencher(html, largura, altura, fps, duracao_s), encoding="utf-8")
        shutil.copy2(GSAP, proj / "gsap.min.js")
        for f in FONTES.glob("*.ttf"):
            shutil.copy2(f, proj / f.name)
        cmd = [str(CLI), "render", str(proj), "-c", "index.html", "-o", str(out), "--format", "webm", "--fps", str(fps), "--quiet", "--no-wait"]
        if workers:
            cmd += ["--workers", str(int(workers))]
        r = subprocess.run(cmd, cwd=str(proj), capture_output=True, text=True, encoding="utf-8", errors="replace", env=_ambiente(), timeout=timeout)
        if r.returncode != 0 or not out.exists():
            raise ErroFerramenta(f"hyperframes render falhou: {(r.stderr or r.stdout).strip()[-900:]}")
        origem = "webm"
        if not _tem_alpha(out):  # reserva: PNG RGBA → WebM pelo ffmpeg
            seq = proj / "seq"
            r2 = subprocess.run([str(CLI), "render", str(proj), "-c", "index.html", "-o", str(seq), "--format", "png-sequence", "--fps", str(fps), "--quiet", "--no-wait"],
                                cwd=str(proj), capture_output=True, text=True, encoding="utf-8", errors="replace", env=_ambiente(), timeout=timeout)
            if r2.returncode != 0:
                raise ErroFerramenta(f"hyperframes render (png-sequence) falhou: {(r2.stderr or r2.stdout).strip()[-900:]}")
            _png_para_webm(seq, out, fps); origem = "png-sequence+ffmpeg"
    finally:
        if not manter_projeto:
            shutil.rmtree(proj, ignore_errors=True)
    m = info_midia(out)
    return {"webm": str(out), "tempo_s": round(time.time() - t0, 1), "alpha": _tem_alpha(out), "origem": origem,
            "duracao_s": m["duracao_s"], "largura": m["largura"], "altura": m["altura"], "fps": m["fps"], "tamanho_mb": m["tamanho_mb"],
            "projeto": str(proj) if manter_projeto else None}


def sobrepor(video, overlay_webm, saida, inicio_s: float = 0.0, crf: int = 18) -> dict:
    """Cola o overlay (WebM com alpha) sobre o vídeo a partir de `inicio_s`, respeitando a transparência; áudio do vídeo copiado sem recodificar.
    Overlay de tamanho diferente é redimensionado ao do vídeo. A duração final é a do vídeo (o overlay some quando acaba)."""
    v = caminho(video); ov = caminho(overlay_webm); out = caminho_saida(saida)
    if out.suffix.lower() not in (".mp4", ".mov", ".m4v"):
        raise ErroFerramenta("A saída de sobrepor precisa ser .mp4/.mov.")
    iv = info_midia(v); io_ = info_midia(ov)
    inicio_s = max(0.0, float(inicio_s))
    if inicio_s >= iv["duracao_s"]:
        raise ErroFerramenta(f"inicio_s ({inicio_s}) está depois do fim do vídeo ({iv['duracao_s']} s).")
    cadeia = "[1:v]format=yuva420p"
    if (io_["largura"], io_["altura"]) != (iv["largura"], iv["altura"]):
        cadeia += f",scale={iv['largura']}:{iv['altura']}"
    cadeia += f",setpts=PTS-STARTPTS+{inicio_s:.3f}/TB[ov];[0:v][ov]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]"
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", v, "-c:v", "libvpx-vp9", "-i", ov, "-filter_complex", cadeia,
           "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-c:a", "copy", "-movflags", "+faststart", out]
    rodar(cmd)
    m = info_midia(out)
    return {"video": str(out), "overlay": str(ov), "inicio_s": inicio_s, "duracao_s": m["duracao_s"], "tem_audio": m["tem_audio"],
            "largura": m["largura"], "altura": m["altura"], "overlay_redimensionado": (io_["largura"], io_["altura"]) != (iv["largura"], iv["altura"])}


def grafismo_no_video(video, bloco: str, dados: dict, saida, inicio_s: float = 0.0, duracao_s: float = 0.0, fps: int = 0) -> dict:
    """Caminho completo da ferramenta MCP: bloco da marca + dados → overlay WebM em _trabalho/ → vídeo com o grafismo em `saida`."""
    _exigir_cli()
    v = caminho(video); iv = info_midia(v); out = caminho_saida(saida)
    inicio_s = max(0.0, float(inicio_s))
    if inicio_s >= iv["duracao_s"]:
        raise ErroFerramenta(f"inicio_s ({inicio_s}) está depois do fim do vídeo ({iv['duracao_s']} s).")
    dur = float(duracao_s) if duracao_s and duracao_s > 0 else round(iv["duracao_s"] - inicio_s, 3)
    dur = min(dur, round(iv["duracao_s"] - inicio_s, 3))
    fps_r = int(fps) if fps else int(round(iv["fps"] or 30))
    trabalho = out.parent / "_trabalho"; trabalho.mkdir(parents=True, exist_ok=True)
    ov = trabalho / f"{out.stem}_hyperframes_{bloco}.webm"
    r_ov = renderizar_overlay(html_do_bloco(bloco, dados), ov, iv["largura"], iv["altura"], fps_r, dur)
    r_sb = sobrepor(v, ov, out, inicio_s)
    return {"video": r_sb["video"], "bloco": bloco, "inicio_s": inicio_s, "duracao_s": dur, "overlay": r_ov, "motor": "hyperframes",
            "tempo_s": r_ov["tempo_s"], "tem_audio": r_sb["tem_audio"], "duracao_final_s": r_sb["duracao_s"]}
