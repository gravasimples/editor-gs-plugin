"""Folha de contato (10/11/2026): quadros por mudança de cena (ffmpeg `select=gt(scene,N)`; PySceneDetect se estiver instalado), sem quadros quase
iguais, até `max_quadros`, numa grade 4×4 (ou menor) com o instante gravado em cada quadro. Para o Claude "ver" o vídeo sem vídeo nativo."""
import math, re, subprocess, tempfile
from pathlib import Path
from .util import FFMPEG, caminho, caminho_saida, info_midia, rodar, ErroFerramenta

RAIZ = Path(__file__).resolve().parents[3]
LARGURA_CELULA = 480
DIFERENCA_IGUAL = 10.0  # média da diferença absoluta (0–255) em 16×16 cinza abaixo da qual dois quadros são "o mesmo"


def _mmss(s):
    s = max(0.0, float(s)); m = int(s // 60); r = s - m * 60
    return f"{m}:{r:04.1f}".replace(".", ",")


def cenas_ffmpeg(video, limiar=0.3, min_intervalo_s=0.5):
    """Instantes de mudança de cena pelo filtro scene do ffmpeg (compara a luma de quadros vizinhos; troca só de cor com o mesmo brilho não conta)."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(video), "-vf", f"select='gt(scene,{limiar})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    ts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    out, ult = [], -10.0
    for t in ts:
        if t - ult >= min_intervalo_s:
            out.append(round(t, 3)); ult = t
    return out


def cenas_scenedetect(video, limiar=0.3):
    """PySceneDetect quando importável (ContentDetector; limiar 0–1 vira 0–100). Devolve None se não estiver instalado."""
    try:
        from scenedetect import detect, ContentDetector  # noqa: F401
    except Exception:  # noqa: BLE001
        return None
    cenas = detect(str(video), ContentDetector(threshold=max(1.0, float(limiar) * 100)))
    return [round(ini.get_seconds(), 3) for ini, _ in cenas[1:]]


def _miniatura(arq):
    import numpy as np
    from PIL import Image
    with Image.open(arq) as im:  # fecha o handle (no Windows o arquivo aberto trava a limpeza da pasta temporária)
        return np.asarray(im.convert("L").resize((16, 16)), dtype=np.float32)


def _deduplicar(quadros, limiar=DIFERENCA_IGUAL):
    """Tira o quadro que é quase igual ao último que ficou (hash por diferença de pixels reduzidos). Devolve (mantidos, n_descartados)."""
    import numpy as np
    mantidos, ult = [], None
    for q in quadros:
        h = _miniatura(q["arquivo"])
        if ult is not None and float(np.abs(h - ult).mean()) < limiar:
            continue
        mantidos.append(q); ult = h
    return mantidos, len(quadros) - len(mantidos)


def _espacar(lista, n):
    """Escolhe n itens espaçados por igual (sempre o primeiro e o último)."""
    if len(lista) <= n:
        return lista
    if n == 1:
        return [lista[0]]
    idx = sorted({round(i * (len(lista) - 1) / (n - 1)) for i in range(n)})
    return [lista[i] for i in idx]


def folha_contato(video, saida_png, max_quadros=16, por_cena=True, limiar_cena=0.3, inicio_s=None, fim_s=None):
    """Monta a folha de contato e devolve os instantes escolhidos. por_cena=False amostra o vídeo por igual. inicio_s/fim_s limitam o trecho olhado."""
    from PIL import Image, ImageDraw, ImageFont
    v = caminho(video); info = info_midia(v); dur = info["duracao_s"]
    if not dur or not info["largura"]:
        raise ErroFerramenta("o arquivo não tem vídeo ou duração")
    n_max = max(1, min(int(max_quadros), 64))
    a = max(0.0, float(inicio_s or 0.0)); z = min(dur, float(fim_s)) if fim_s is not None else dur
    if z <= a:
        raise ErroFerramenta(f"trecho inválido: fim_s ({z}) deve ser maior que inicio_s ({a})")
    origem = "amostra uniforme"; n_cenas = 0; detector = None
    instantes = []
    if por_cena:
        cenas = cenas_scenedetect(v, limiar_cena)
        detector = "scenedetect" if cenas is not None else "ffmpeg"
        if cenas is None:
            cenas = cenas_ffmpeg(v, limiar_cena)
        cenas = [t for t in cenas if a <= t < z]
        n_cenas = len(cenas)
        instantes = [a] + [t + 0.04 for t in cenas if t + 0.04 < z]  # logo depois do corte, já no plano novo
        origem = f"mudanças de cena ({detector})"
        if len(instantes) < min(4, n_max):  # vídeo quase sem cortes: completa com amostras por igual
            passo = (z - a) / min(4, n_max)
            instantes = sorted(set(instantes) | {round(a + i * passo, 3) for i in range(min(4, n_max))}); origem += " + amostra uniforme"
    else:
        passo = (z - a) / n_max
        instantes = [round(a + i * passo, 3) for i in range(n_max)]
    instantes = [t for t in instantes if t < dur]
    instantes = _espacar(instantes, n_max * 3)  # muitas cenas: afina antes de extrair (teto de 3× o pedido)
    out = caminho_saida(saida_png)
    with tempfile.TemporaryDirectory(prefix="gs-folha-") as td:
        quadros = []
        for i, t in enumerate(instantes):
            arq = Path(td) / f"q{i:03d}.jpg"
            rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-ss", f"{t:.3f}", "-i", v, "-frames:v", "1", "-vf", f"scale={LARGURA_CELULA}:-2", "-q:v", "3", arq])
            if arq.exists():
                quadros.append({"instante_s": round(t, 3), "arquivo": arq})
        if not quadros:
            raise ErroFerramenta("não consegui extrair nenhum quadro")
        quadros, descartados = _deduplicar(quadros)
        quadros = _espacar(quadros, n_max)
        n = len(quadros); cols = min(4, math.ceil(math.sqrt(n))); linhas = math.ceil(n / cols)
        with Image.open(quadros[0]["arquivo"]) as im0:
            cw, ch = im0.size
        margem = 6; W = cols * (cw + margem) + margem; H = linhas * (ch + margem) + margem
        folha = Image.new("RGB", (W, H), "#000921"); d = ImageDraw.Draw(folha)
        try:
            fonte = ImageFont.truetype(str(RAIZ / "fontes" / "Inter-Bold.ttf"), max(16, cw // 18))
        except OSError:
            fonte = ImageFont.load_default()
        escolhidos = []
        for i, q in enumerate(quadros):
            c, l = i % cols, i // cols
            x = margem + c * (cw + margem); y = margem + l * (ch + margem)
            with Image.open(q["arquivo"]) as src:
                im = src.convert("RGB")
            if im.size != (cw, ch):
                im = im.resize((cw, ch))
            folha.paste(im, (x, y))
            rot = _mmss(q["instante_s"]); tw = d.textlength(rot, font=fonte); th = fonte.size
            d.rectangle([x + 6, y + 6, x + 6 + tw + 12, y + 6 + th + 8], fill="#000921")
            d.text((x + 12, y + 9), rot, font=fonte, fill="#F79615")
            escolhidos.append({"instante_s": q["instante_s"], "mmss": rot, "coluna": c + 1, "linha": l + 1})
        folha.save(out)
    return {"folha": str(out), "largura": W, "altura": H, "grade": f"{cols}x{linhas}", "n": n, "quadros": escolhidos, "cenas_detectadas": n_cenas,
            "origem": origem, "descartados_iguais": descartados, "trecho": {"inicio_s": a, "fim_s": round(z, 3)}, "duracao_s": dur,
            "dica": "leia a imagem: cada quadro traz o instante (m:ss,d); para ver um ponto específico use extrair_quadros ou folha_contato com inicio_s/fim_s"}
