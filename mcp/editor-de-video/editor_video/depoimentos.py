"""Carrossel semanal de depoimentos (prints de alunos) no padrão do designer da Grava Simples.

Este post NÃO segue o manual marinho/laranja: o padrão vigente (29/10/2026) é o do designer: fundo preto com brilho,
título "QUEM GRAVA SIMPLES / APROVA!", três prints por tela como cartões 3D inclinados com sombra, selo
"DEPOIMENTO REAL DO ALUNO", rodapé "Arraste para o lado" e última tela com o CTA "Comenta DESCOMPLICA" e o logo do OBS.

Molde fixo em estilos/depoimentos-semanais/ (1080×1350, tirado das telas 02 a 05 do post aprovado):
  fundo.png         tela de prints com rodapé longo
  fundo-ultimo.png  última tela de prints (rodapé "Arraste para o lado")
  tela-cta.png      tela final, usada tal qual
  modelo-original/  as telas do designer, só para conferência

A ferramenta recebe os prints em ordem de leitura, corta se pedido, monta os cartões 3D nas vagas de cada tela,
evita que um cartão cubra o print de outro (encolhe e avisa), e gera os PNGs finais, o PPTX com camadas
(fundo + cada cartão) e o PDF achatado. As camadas e as posições ficam em saida/_trabalho/depoimentos/.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .util import caminho, caminho_saida, ErroFerramenta

RAIZ = Path(__file__).resolve().parents[3]
W, H = 1080, 1350
FAIXA = (300, 1010)  # y livre para os cartões: entre o título e o selo "DEPOIMENTO REAL DO ALUNO"
MAX_PRINTS = 12
MOLDE_PADRAO = RAIZ / "estilos" / "depoimentos-semanais"
EXT_IMG = (".jpg", ".jpeg", ".png", ".webp")

# Vagas por tela (centro, caixa máxima, rotação em graus, perspectiva), medidas do post aprovado em 29/10/2026.
# Ordem de leitura dentro da tela: cima → baixo.
VAGAS_3 = [
    [dict(c=(320, 420), box=(560, 260), ang=-5, yaw=0.06), dict(c=(800, 640), box=(480, 440), ang=4, yaw=-0.06), dict(c=(330, 900), box=(560, 260), ang=3, yaw=-0.05)],
    [dict(c=(340, 475), box=(600, 330), ang=-4, yaw=0.05), dict(c=(830, 720), box=(440, 460), ang=5, yaw=-0.06), dict(c=(345, 910), box=(600, 260), ang=-3, yaw=0.05)],
    [dict(c=(830, 470), box=(450, 320), ang=5, yaw=-0.06), dict(c=(290, 640), box=(500, 450), ang=-4, yaw=0.05), dict(c=(790, 940), box=(480, 320), ang=-3, yaw=0.05)],
]
VAGAS_2 = [dict(c=(540, 490), box=(720, 320), ang=-3, yaw=0.04), dict(c=(540, 850), box=(720, 320), ang=3, yaw=-0.04)]
VAGAS_1 = [dict(c=(540, 655), box=(760, 620), ang=-2, yaw=0.03)]
PAD_CANVAS = 400  # margem do canvas global para cartões que saem um pouco da tela


def _molde(molde_dir):
    d = Path(molde_dir) if molde_dir else MOLDE_PADRAO
    arqs = {k: d / f"{k}.png" for k in ("fundo", "fundo-ultimo", "tela-cta")}
    faltam = [p.name for p in arqs.values() if not p.exists()]
    if faltam:
        raise ErroFerramenta(f"Molde incompleto em {d}: faltam {', '.join(faltam)}")
    for p in arqs.values():
        if Image.open(p).size != (W, H):
            raise ErroFerramenta(f"{p.name} do molde não está em {W}×{H}")
    return d, arqs


def _normalizar_prints(prints_json):
    """Aceita: caminho de JSON ([{"arquivo","nome"?,"corte"?}] ou {"prints": [...]}), pasta com imagens, uma imagem, ou a lista direta."""
    dados = prints_json
    if isinstance(prints_json, str):
        p = Path(caminho(prints_json))
        if p.is_dir():
            dados = sorted(str(x) for x in p.iterdir() if x.suffix.lower() in EXT_IMG and not x.name.startswith("."))
        elif p.suffix.lower() == ".json":
            dados = json.loads(p.read_text(encoding="utf-8"))
        else:
            dados = [str(p)]
    if isinstance(dados, dict):
        dados = dados.get("prints", [])
    out = []
    for i, it in enumerate(dados or []):
        if isinstance(it, str):
            it = {"arquivo": it}
        arq = it.get("arquivo") or it.get("print")
        if not arq:
            raise ErroFerramenta(f"Print {i + 1} sem 'arquivo'.")
        corte = it.get("corte")
        if corte is not None and (len(corte) != 4 or corte[2] <= corte[0] or corte[3] <= corte[1]):
            raise ErroFerramenta(f"Corte inválido no print {i + 1}: use [x0, y0, x1, y1].")
        out.append({"arquivo": str(caminho(arq)), "nome": str(it.get("nome") or Path(arq).stem), "corte": [int(v) for v in corte] if corte else None})
    if not out:
        raise ErroFerramenta("Carrossel de depoimentos precisa de pelo menos 1 print.")
    if len(out) > MAX_PRINTS:
        raise ErroFerramenta(f"No máximo {MAX_PRINTS} prints ({MAX_PRINTS // 3} telas); divida em dois posts.")
    return out


def _abrir(sp):
    im = ImageOps.exif_transpose(Image.open(sp["arquivo"])).convert("RGB")
    if sp["corte"]:
        x0, y0, x1, y1 = sp["corte"]
        im = im.crop((max(0, x0), max(0, y0), min(im.width, x1), min(im.height, y1)))
    if im.width < 40 or im.height < 20:
        raise ErroFerramenta(f"Print {sp['nome']} ficou pequeno demais depois do corte ({im.width}×{im.height}).")
    return im


def _cor_fundo(im):
    a = np.asarray(im)
    cantos = np.concatenate([a[:3, :3].reshape(-1, 3), a[:3, -3:].reshape(-1, 3), a[-3:, :3].reshape(-1, 3), a[-3:, -3:].reshape(-1, 3)])
    return tuple(int(v) for v in np.median(cantos, axis=0))


def _cartao(im, w, centro, ang, yaw):
    """Print como cartão 3D: fundo da própria cor, cantos arredondados, espessura lateral, perspectiva, rotação e sombra.
    Devolve (imagem RGBA recortada, (x, y) do canto superior esquerdo no canvas 1080×1350, info da face, (máscara do print, máscara do cartão))."""
    fundo = _cor_fundo(im); claro = sum(fundo) / 3 > 128
    esc = w / im.width
    im = im.resize((w, max(1, round(im.height * esc))), Image.LANCZOS)
    pad, raio, esp, m = 22, 26, 14, 70
    fw, fh = im.width + 2 * pad, im.height + 2 * pad
    CW, CH = fw + esp + 2 * m, fh + esp + 2 * m
    cam = Image.new("RGBA", (CW, CH), (0, 0, 0, 0)); d = ImageDraw.Draw(cam)
    lado = (206, 210, 218) if claro else (70, 72, 78); escuro = (150, 154, 162) if claro else (34, 35, 39)
    for k in range(esp, 0, -1):
        t = k / esp; cor = tuple(round(lado[i] * (1 - t) + escuro[i] * t) for i in range(3))
        ox, oy = m + round(k * 0.55), m + k
        d.rounded_rectangle((ox, oy, ox + fw - 1, oy + fh - 1), radius=raio, fill=cor + (255,))
    d.rounded_rectangle((m - 1, m - 1, m + fw, m + fh), radius=raio + 1, fill=(235, 237, 242, 255) if claro else (92, 94, 100, 255))
    face = Image.new("RGBA", (fw, fh), fundo + (255,)); face.paste(im, (pad, pad))
    fm = Image.new("L", (fw, fh), 0); ImageDraw.Draw(fm).rounded_rectangle((0, 0, fw - 1, fh - 1), radius=raio, fill=255)
    cam.paste(face, (m, m), fm)
    a = np.ascontiguousarray(np.asarray(cam))
    src = np.float32([[0, 0], [CW, 0], [CW, CH], [0, CH]])
    dl, dr = (0, yaw * CH) if yaw > 0 else (-yaw * CH, 0)
    dst = np.float32([[0, dl], [CW, dr], [CW, CH - dr], [0, CH - dl]])
    M = np.vstack([cv2.getRotationMatrix2D((CW / 2, CH / 2), ang, 1.0), [0, 0, 1]]) @ cv2.getPerspectiveTransform(src, dst)
    pre = cv2.cvtColor(a, cv2.COLOR_RGBA2mRGBA)
    war = cv2.cvtColor(cv2.warpPerspective(pre, M, (CW, CH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)), cv2.COLOR_mRGBA2RGBA)
    card = Image.fromarray(war)
    mk = np.zeros((CH, CW), np.uint8); mk[m + pad:m + pad + im.height, m + pad:m + pad + im.width] = 255
    mk = cv2.warpPerspective(mk, M, (CW, CH), flags=cv2.INTER_NEAREST)
    alpha = card.split()[3]
    sh = Image.new("RGBA", card.size, (0, 0, 0, 0)); sh.putalpha(alpha.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.6)))
    sombra = Image.new("RGBA", card.size, (0, 0, 0, 0)); sombra.paste(sh, (10, 20))
    out = Image.alpha_composite(sombra, card); bb = out.getbbox(); out = out.crop(bb)
    cx, cy = centro
    x = round(cx - (CW / 2 - bb[0])); y = round(cy - (CH / 2 - bb[1]))
    fb = card.getbbox()
    info = dict(face_top=round(cy - (CH / 2 - fb[1])), face_bot=round(cy - (CH / 2 - fb[3])), face_l=round(cx - (CW / 2 - fb[0])), face_r=round(cx - (CW / 2 - fb[2])), escala=round(esc, 3))
    pm = mk[bb[1]:bb[3], bb[0]:bb[2]] > 0
    am = np.asarray(card)[bb[1]:bb[3], bb[0]:bb[2], 3] > 100
    return out, (x, y), info, (pm, am)


def _global(mask, x, y):
    g = np.zeros((H + 2 * PAD_CANVAS, W + 2 * PAD_CANVAS), bool)
    y0, x0 = y + PAD_CANVAS, x + PAD_CANVAS
    h, w = mask.shape
    ys, xs = slice(max(0, y0), min(g.shape[0], y0 + h)), slice(max(0, x0), min(g.shape[1], x0 + w))
    g[ys, xs] = mask[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
    return g


def _vagas(n):
    return VAGAS_1 if n == 1 else VAGAS_2 if n == 2 else None


def _dispor(tela_prints, vagas, idx_tela, avisos):
    itens, mascaras = [], []
    for sp, vaga in zip(tela_prints, vagas):
        im = _abrir(sp)
        fator, sob, dy_total = 1.0, 0, 0
        for _ in range(12):
            bw, bh = vaga["box"]; esc = min(bw / im.width, bh / im.height) * fator
            w = max(120, round(im.width * esc))
            card, (x, y), info, (pm, am) = _cartao(im, w, vaga["c"], vaga["ang"], vaga["yaw"])
            if info["face_bot"] - info["face_top"] > FAIXA[1] - FAIXA[0]:
                fator *= 0.9; continue
            dy = FAIXA[0] - info["face_top"] if info["face_top"] < FAIXA[0] else FAIXA[1] - info["face_bot"] if info["face_bot"] > FAIXA[1] else 0
            dx = -info["face_l"] if info["face_l"] < 0 else W - info["face_r"] if info["face_r"] > W else 0
            x += dx; y += dy; dy_total = dy
            for k, v in (("face_top", dy), ("face_bot", dy), ("face_l", dx), ("face_r", dx)):
                info[k] += v
            ga = _global(am, x, y)
            sob = max((int((ga & m).sum()) for _, m in mascaras), default=0)
            if sob == 0:
                break
            fator *= 0.93
        if sob:
            avisos.append(f"tela {idx_tela}: o cartão de {sp['nome']} cobre {sob} px do print anterior; mude a ordem ou feche o corte")
        if info["escala"] < 0.45:
            avisos.append(f"tela {idx_tela}: {sp['nome']} saiu em {info['escala']:.2f}× (pequeno no celular); considere cortar só o balão")
        elif info["escala"] > 1.5:
            avisos.append(f"tela {idx_tela}: {sp['nome']} ampliado {info['escala']:.2f}× (pode ficar suave)")
        mascaras.append((sp["nome"], _global(pm, x, y)))
        itens.append(dict(nome=sp["nome"], arquivo=sp["arquivo"], corte=sp["corte"], x=x, y=y, w=card.width, h=card.height, deslocado_y=dy_total, **info, _card=card))
    return itens


def gerar_carrossel_depoimentos(prints_json, saida_dir, molde_dir="", nome_base="final_tela", pptx=True, pdf=True):
    """Monta o carrossel semanal de depoimentos no molde fixo. prints_json: JSON/pasta/lista com os prints em ordem de leitura
    (até 12; `corte` opcional [x0, y0, x1, y1]; `nome` opcional). Gera `<nome_base>-NN.png` (última = tela CTA do molde),
    `carrossel.pptx` (fundo + cada cartão como camada) e `carrossel.pdf`; camadas e posições em `_trabalho/depoimentos/`."""
    molde, arqs = _molde(molde_dir)
    prints = _normalizar_prints(prints_json)
    out_dir = Path(caminho_saida(str(Path(saida_dir) / "x"))).parent; out_dir.mkdir(parents=True, exist_ok=True)
    trab = out_dir / "_trabalho" / "depoimentos"; trab.mkdir(parents=True, exist_ok=True)
    grupos = [prints[i:i + 3] for i in range(0, len(prints), 3)]
    avisos, telas, meta = [], [], []
    for i, grupo in enumerate(grupos, 1):
        ultimo = i == len(grupos)
        fundo_nome = "fundo-ultimo" if ultimo else "fundo"
        vagas = _vagas(len(grupo)) or VAGAS_3[(i - 1) % len(VAGAS_3)]
        itens = _dispor(grupo, vagas, i, avisos)
        img = Image.open(arqs[fundo_nome]).convert("RGBA")
        camadas = []
        for j, it in enumerate(itens, 1):
            card = it.pop("_card")
            nome = f"tela-{i:02d}-cartao-{j}.png"; card.save(trab / nome)
            img.alpha_composite(card, dest=(max(0, it["x"]), max(0, it["y"])), source=(max(0, -it["x"]), max(0, -it["y"])))
            camadas.append({**it, "camada": str(trab / nome)})
        p = out_dir / f"{nome_base}-{i:02d}.png"; img.convert("RGB").save(p, optimize=True); telas.append(str(p))
        meta.append(dict(tela=i, fundo=str(arqs[fundo_nome]), cartoes=camadas))
    n_cta = len(grupos) + 1
    p_cta = out_dir / f"{nome_base}-{n_cta:02d}.png"; Image.open(arqs["tela-cta"]).convert("RGB").save(p_cta, optimize=True); telas.append(str(p_cta))
    meta.append(dict(tela=n_cta, fundo=str(arqs["tela-cta"]), cartoes=[]))
    (trab / "telas.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    res = {"telas": telas, "n_telas": len(telas), "n_prints": len(prints), "molde": str(molde), "camadas": str(trab), "posicoes": str(trab / "telas.json"), "avisos": avisos,
           "prints": [{k: v for k, v in c.items() if k in ("nome", "arquivo", "corte", "escala", "deslocado_y")} | {"tela": t["tela"]} for t in meta for c in t["cartoes"]],
           "formato": f"{W}x{H}", "padrao": "designer (preto/brilho), não o manual marinho/laranja"}
    if pptx:
        res["pptx"] = _pptx(meta, out_dir / "carrossel.pptx")
    if pdf:
        pags = [Image.open(t).convert("RGB") for t in telas]
        pags[0].save(out_dir / "carrossel.pdf", save_all=True, append_images=pags[1:], resolution=72); res["pdf"] = str(out_dir / "carrossel.pdf")
    return res


def _pptx(meta, saida):
    from pptx import Presentation
    from pptx.util import Emu
    PX = 9525
    prs = Presentation(); prs.slide_width, prs.slide_height = Emu(W * PX), Emu(H * PX)
    for tela in meta:
        sl = prs.slides.add_slide(prs.slide_layouts[6])
        sl.shapes.add_picture(tela["fundo"], 0, 0, Emu(W * PX), Emu(H * PX)).name = "Fundo"
        for c in tela["cartoes"]:
            sl.shapes.add_picture(c["camada"], Emu(c["x"] * PX), Emu(c["y"] * PX), Emu(c["w"] * PX), Emu(c["h"] * PX)).name = f"Depoimento {c['nome']}"
    prs.save(saida); return str(saida)
