"""Prévia de um item da biblioteca de estilos, feita pelos MESMOS motores da entrega (03/11/2026).
Uso: python previa_estilo.py <tipo> <id> <saida.mp4>   tipo = estilo | legenda | elemento
- legenda: ASS do gerar_legenda queimado na amostra (ffmpeg + libass).
- estilo: legenda do estilo + montar_remotion com o bloco `montagem` do estilo.
- elemento: montar_remotion com uma camada só, xfade (transição) ou montagem.py (formatos).
A amostra fica em estilos/previas/ (6,8 s do Thiago falando para a câmera). Rodar pelo gateway (fila), não à mão."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import acabamento, legenda, montagem  # noqa: E402
from editor_video.util import FFMPEG  # noqa: E402

EST = RAIZ / "estilos"; PREV = EST / "previas"
AMOSTRA = PREV / "amostra.mp4"; PALAVRAS = PREV / "amostra_palavras.json"; TELA = PREV / "tela_obs.mp4"
DUR = 6.8


def ff(*args):
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *map(str, args)], check=True)


def finalizar(src, saida, audio=True):
    """Reduz para 540x960 (ou mantém a proporção) e comprime: a prévia é leve."""
    ff("-i", src, "-vf", "scale='min(540,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p",
       *(["-c:a", "aac", "-b:a", "96k"] if audio else ["-an"]), "-movflags", "+faststart", saida)


def edl(td, cortes):
    pts = [0.0] + list(cortes) + [DUR]
    p = Path(td) / "edl.json"; p.write_text(json.dumps({"manter": [{"inicio": a, "fim": b} for a, b in zip(pts, pts[1:])]})); return str(p)


def palavras_deslocadas(td, atraso):
    d = json.loads(PALAVRAS.read_text(encoding="utf-8"))
    for w in d["palavras"]:
        w["inicio"] += atraso; w["fim"] += atraso
    p = Path(td) / "pal_desloc.json"; p.write_text(json.dumps(d, ensure_ascii=False)); return str(p)


def remotion(td, saida, estilo, args, legenda_ass=None):
    a = dict(args); cortes = a.pop("cortes", None)
    kw = {"zoom": False, "clarao": False, "tela_final": False, "resolucao": "720p", "formato": "9x16"}
    kw.update(a)
    if isinstance(kw.get("palavras_chave"), list):
        kw["palavras_chave"] = json.dumps(kw["palavras_chave"])
    if cortes:
        kw["edl_json"] = edl(td, cortes)
    bruto = Path(td) / "bruto.mp4"
    acabamento.montar_remotion(str(AMOSTRA), str(bruto), palavras_json=str(PALAVRAS), estilo=estilo, legenda_ass=legenda_ass, **kw)
    finalizar(bruto, saida)


def prev_legenda(td, saida, leg):
    ass = Path(td) / "leg.ass"
    legenda.gerar_legenda(str(PALAVRAS), str(ass), {"legenda": leg}, "9x16")
    esc = lambda s: str(s).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    ff("-i", AMOSTRA, "-vf", f"subtitles='{esc(ass)}':fontsdir='{esc(RAIZ / 'fontes')}',scale=540:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
       "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", saida)


def prev_estilo(td, saida, est):
    mont = est.get("montagem", {})
    vinheta = bool(mont.get("vinheta"))
    ass = Path(td) / "leg.ass"
    legenda.gerar_legenda(palavras_deslocadas(td, 1.0) if vinheta else str(PALAVRAS), str(ass), est, "9x16")
    args = {"zoom": bool(mont.get("zoom_por_frase", True)), "clarao": bool(mont.get("clarao_transicao")), "cortes": [2.2, 4.6],
            "tela_final": bool(mont.get("tela_final_cta")), "vinheta": vinheta,
            "frase_impacto": "Depende da sua webcam", "frase_destaque": "webcam"}
    if mont.get("terco_inferior"):
        args.update({"terco_texto": "Thiago Gomes", "terco_sub": "Grava Simples · OBS", "terco_inicio_s": 2.8, "terco_s": 3.5})
    if mont.get("capitulos_obrigatorios"):
        args["capitulos"] = "Webcam@0; Aplicativo@4.4"
    remotion(td, saida, est, args, legenda_ass=str(ass))


def prev_xfade(td, saida, tipo):
    from PIL import Image, ImageDraw, ImageFont
    card = Path(td) / "card.png"; im = Image.new("RGB", (540, 960), "#000921"); d = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(str(RAIZ / "fontes" / "Inter-ExtraBold.ttf"), 64); f2 = ImageFont.truetype(str(RAIZ / "fontes" / "Inter-Regular.ttf"), 30)
    d.rounded_rectangle((40, 330, 500, 630), 20, fill="#0B193D"); d.text((80, 390), "CENA", font=f1, fill="#FFFFFF"); d.text((80, 470), "SEGUINTE", font=f1, fill="#F79615")
    d.text((80, 565), "a próxima parte do vídeo", font=f2, fill="#A7ACBD"); im.save(card)
    ff("-ss", 0.4, "-t", 2.6, "-i", AMOSTRA, "-loop", 1, "-t", 2.6, "-i", card, "-filter_complex",
       f"[0:v]scale=540:960,fps=30,format=yuv420p,setsar=1[a];[1:v]scale=540:960,fps=30,format=yuv420p,setsar=1[b];[a][b]xfade=transition={tipo}:duration=0.8:offset=1.8[v]",
       "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p", "-movflags", "+faststart", saida)


def prev_formato(td, saida, motor):
    bruto = Path(td) / "fmt.mp4"
    if motor == "pip":
        montagem.montar_pip(str(TELA), str(AMOSTRA), str(bruto), resolucao="720p")
    elif motor == "dividido":
        montagem.montar_dividido(str(AMOSTRA), str(TELA), str(bruto), resolucao="720p")
    elif motor == "react":
        montagem.montar_react(str(AMOSTRA), str(TELA), str(bruto), "@gravasimples", "proprio", resolucao="720p")
    elif motor == "carrossel":
        from PIL import Image, ImageDraw, ImageFont
        fb = ImageFont.truetype(str(RAIZ / "fontes" / "Inter-ExtraBold.ttf"), 86); fr = ImageFont.truetype(str(RAIZ / "fontes" / "Inter-Regular.ttf"), 42)
        slides = []
        for i, (t1, t2, apoio) in enumerate([("3 ERROS", "NO OBS", "que deixam sua aula com cara de amadora"), ("1. ÁUDIO", "BAIXO", "suba o ganho antes de gravar"), ("2. LUZ", "DE CHAPA", "use a janela de lado, não atrás")]):
            im = Image.new("RGB", (1080, 1350), "#000921" if i != 1 else "#0B193D"); d = ImageDraw.Draw(im)
            d.text((90, 420), t1, font=fb, fill="#FFFFFF"); d.text((90, 520), t2, font=fb, fill="#F79615"); d.text((90, 660), apoio, font=fr, fill="#A7ACBD")
            d.rounded_rectangle((90, 1180, 330, 1240), 30, fill="#F79615"); d.text((120, 1188), f"{i + 1}/3", font=fr, fill="#000921")
            f = Path(td) / f"s{i}.png"; im.save(f); slides.append(str(f))
        from editor_video import imagem as _img
        _img.animar_carrossel(slides, str(bruto), duracao_slide_s=2.2, transicao_s=0.5, formato="9x16", transicao="smoothleft")
        finalizar(bruto, saida, audio=False); return
    else:
        antes = Path(td) / "antes.mp4"
        ff("-i", AMOSTRA, "-vf", "eq=brightness=-0.16:saturation=0.45:contrast=0.85", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-c:a", "copy", antes)
        montagem.montar_antes_depois(str(antes), str(AMOSTRA), str(bruto), resolucao="720p", rotulo_antes="SEM LUZ", rotulo_depois="COM LUZ")
    finalizar(bruto, saida)


def main(tipo, id_, saida):
    saida = Path(saida); saida.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = saida.with_suffix(".parcial.mp4")
    with tempfile.TemporaryDirectory() as td:
        if tipo == "legenda":
            modelo = json.loads((EST / "legendas" / f"{id_}.json").read_text(encoding="utf-8"))
            if modelo.get("motor") == "remotion":  # 11/11/2026: cinética nasce no Remotion, sem ASS (como na entrega)
                remotion(td, tmp_out, {"legenda": modelo["legenda"]}, {})
            else:
                prev_legenda(td, tmp_out, modelo["legenda"])
        elif tipo == "estilo":
            prev_estilo(td, tmp_out, json.loads((EST / f"{id_}.json").read_text(encoding="utf-8")))
        elif tipo == "elemento":
            item = next(i for i in json.loads((EST / "elementos.json").read_text(encoding="utf-8"))["itens"] if i["id"] == id_)
            m = item["previa"]["motor"]; args = dict(item["previa"]["args"])
            if m == "remotion":
                if isinstance(args.get("broll"), str):
                    args["broll"] = args["broll"].replace("estilos/", str(EST) + "/", 1)
                remotion(td, tmp_out, json.loads((EST / "padrao.json").read_text(encoding="utf-8")), args)
            elif m == "xfade":
                prev_xfade(td, tmp_out, args["tipo"])
            else:
                prev_formato(td, tmp_out, m)
        else:
            raise SystemExit(f"tipo inválido: {tipo}")
    shutil.move(str(tmp_out), str(saida))
    print(json.dumps({"ok": True, "arquivo": str(saida)}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
