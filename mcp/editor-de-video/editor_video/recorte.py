"""Produto recortado sem fundo (15/11/2026, visto em 4 Criativos do Máquina: webcam, celular, mochila, bastão de LED entrando com pop
e borda branca). Tira o fundo de uma foto ou de um quadro do vídeo e grava PNG com transparência, pronto para o grafismo `recorte`.
Modelo: ISNet general-use (Apache-2.0, o mesmo do rembg), rodando no onnxruntime da CPU. Baixado uma vez para EditorGS/modelos
(178 MB); nada sai da máquina. Recorta o objeto principal do quadro: numa cena com a pessoa em destaque, sai a pessoa (vira figurinha);
para um produto, use a foto do produto ou um quadro em que ele domina a imagem."""
import os, subprocess, tempfile, urllib.request
from pathlib import Path
from .util import FFMPEG, ErroFerramenta, caminho, caminho_saida

MODELO_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"
MODELO_SHA256_INICIO = "60920e99c45464f2"
LADO = 1024
CORTE_FUNDO, CORTE_OBJETO = 0.15, 0.55  # máscara abaixo = fundo, acima = objeto inteiro; no meio, borda suave
_sessao = None


def pasta_modelos() -> Path:
    base = Path(os.environ["EDITOR_GS_HOME"]) if os.environ.get("EDITOR_GS_HOME") else Path.home() / "EditorGS"
    return base / "modelos"


def _modelo() -> Path:
    p = pasta_modelos() / "isnet-general-use.onnx"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".parcial")
        try:
            urllib.request.urlretrieve(MODELO_URL, tmp)
        except OSError as e:
            raise ErroFerramenta(f"não consegui baixar o modelo de recorte ({e}); baixe {MODELO_URL} para {p}")
        import hashlib
        h = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if not h.startswith(MODELO_SHA256_INICIO):
            tmp.unlink(missing_ok=True); raise ErroFerramenta("o modelo de recorte baixado não confere (hash); tente de novo")
        tmp.replace(p)
    return p


def _rodar(img):
    """img PIL RGB → máscara PIL L (0–255) no tamanho original."""
    global _sessao
    import numpy as np, onnxruntime as ort
    from PIL import Image
    if _sessao is None:
        _sessao = ort.InferenceSession(str(_modelo()), providers=["CPUExecutionProvider"])
    x = np.asarray(img.resize((LADO, LADO), Image.LANCZOS), dtype=np.float32) / 255.0
    x = (x - 0.5) / 1.0
    x = x.transpose(2, 0, 1)[None]
    pred = _sessao.run(None, {_sessao.get_inputs()[0].name: x})[0][:, 0, :, :]
    mi, ma = float(pred.min()), float(pred.max())
    pred = (pred - mi) / max(ma - mi, 1e-6)
    # a saída do ISNet é macia: sem curva, partes do objeto ficam meio transparentes (medido nas fotos de Equipamentos do Drive)
    pred = ((pred - CORTE_FUNDO) / (CORTE_OBJETO - CORTE_FUNDO)).clip(0, 1)
    return Image.fromarray((pred[0] * 255).clip(0, 255).astype("uint8"), "L").resize(img.size, Image.LANCZOS)


def recortar(origem, saida_png, instante_s=None, margem=0.04):
    """Recorta o objeto principal de `origem` (imagem, ou vídeo + `instante_s`) e grava PNG RGBA aparado no objeto (com `margem`).
    Devolve arquivo, tamanho e quanto da imagem o objeto ocupa (cobertura muito baixa ou alta = recorte duvidoso, avisa)."""
    from PIL import Image
    ent = caminho(origem); out = caminho_saida(saida_png)
    if out.suffix.lower() != ".png":
        raise ErroFerramenta("a saída do recorte precisa ser .png (transparência)")
    with tempfile.TemporaryDirectory() as td:
        if ent.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm", ".m4v"):
            if instante_s is None:
                raise ErroFerramenta("para recortar de um vídeo, diga o `instante_s` do quadro em que o objeto aparece inteiro")
            q = Path(td) / "q.png"
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", str(float(instante_s)), "-i", str(ent), "-frames:v", "1", str(q)], check=True)
            ent = q
        img = Image.open(ent).convert("RGB")
        mask = _rodar(img)
    avisos = []
    caixa = mask.point(lambda v: 255 if v > 40 else 0).getbbox()
    if not caixa:
        raise ErroFerramenta("não achei objeto para recortar nessa imagem")
    cobertura = sum(1 for v in mask.getdata() if v > 128) / (img.size[0] * img.size[1])
    if cobertura < 0.02:
        avisos.append("o objeto ocupa menos de 2% da imagem: confira se recortou a coisa certa ou use uma foto mais fechada")
    if cobertura > 0.85:
        avisos.append("o recorte ficou com quase a imagem toda: o fundo pode não ter saído (foto com fundo parecido com o objeto?)")
    rgba = img.copy(); rgba.putalpha(mask)
    w, h = img.size; m = int(max(w, h) * margem)
    x0, y0, x1, y1 = caixa
    rgba = rgba.crop((max(0, x0 - m), max(0, y0 - m), min(w, x1 + m), min(h, y1 + m)))
    rgba.save(out)
    return {"arquivo": str(out), "largura": rgba.size[0], "altura": rgba.size[1], "cobertura": round(cobertura, 3), "avisos": avisos}
