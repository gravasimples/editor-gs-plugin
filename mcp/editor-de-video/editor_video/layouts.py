"""Fase C (07/11/2026): layouts no jeito do Máquina (docs/maquina/ANALISE-2026-11-06.md, itens 13–17 e 21).
O vídeo passa por blocos de layout ao longo do tempo, trocados por uma cortina laranja; o Remotion desenha (remotion/src/Layout.tsx).
- layout = "painel" (o vídeo todo) | "painel@0; tutorial@6.5; cheio@14" | JSON [{modo, inicio}] em tempos do vídeo cortado. Modos em MODOS.
- tela = gravação de tela (OBS) para tutorial/tela/aula; com edl_json, recebe os mesmos cortes do rosto quando cobre a gravação toda.
- focos = câmera virtual na tela: [{inicio, fim?, x, y, zoom?, caixa?: [x, y, w, h], palavra?}] com x/y/caixa de 0 a 1 na tela; "auto" acha onde a
  tela muda pouco e localizado (menu abrindo, clique) e aproxima ali. caixa = contorno laranja no item.
- passos = barra fixa "1 EXPOSIÇÃO · 2 ISO · 3 BRANCO" com o passo atual aceso: "Exposição@3; ISO@8" ou JSON [{texto, inicio|palavra}].
- rosto recortado (aula): recortar_rosto() tira o fundo do rosto com o MediaPipe (selfie multiclass, Apache 2.0) e grava um .webm com transparência."""
import json, re, subprocess
from pathlib import Path
import numpy as np
from .util import FFMPEG, ErroFerramenta, caminho, caminho_saida, info_midia, preparar_mediapipe

RAIZ = Path(__file__).resolve().parents[3]
MODELO_SEG = RAIZ / "modelos" / "selfie_segmenter.tflite"              # leve (~0,02 s por quadro): padrão
MODELO_SEG_ALTA = RAIZ / "modelos" / "selfie_multiclass_256x256.tflite"  # cabelo melhor, ~12× mais lento

MODOS = {
    "cheio": "o vídeo do rosto ocupa o quadro (padrão)",
    "painel": "painel marinho no terço de cima (manchete, logos e cartões entram nele) e o rosto nos 2/3 de baixo",
    "moldura": "o rosto numa moldura arredondada com borda laranja sobre fundo marinho (personagem, CTA, depoimento)",
    "tutorial": "tela em cima com câmera virtual seguindo os focos, rosto embaixo, linha laranja no meio (legenda 'centro' fica na linha)",
    "tela": "só a gravação de tela (câmera virtual) com a voz por baixo",
    "aula": "tela inteira com o rosto recortado (sem fundo) no canto; sem recorte, o rosto vai numa bolha",
    "composto": "vídeo vertical já composto (tela em cima, rosto embaixo): no 16:9 a tela vai à esquerda e o rosto à direita; trecho só de rosto mantém o rosto na coluna da direita e a esquerda vira painel marinho (grafismos); no 9:16 fica como está",
}
PRECISA_TELA = {"tutorial", "tela", "aula"}
CORTINA_S = 0.5
MIN_BLOCO_S = 1.5


def _lista_texto(texto):
    """'a@1; b@2.5' → [(a, 1.0), (b, 2.5)]; aceita também JSON."""
    texto = str(texto or "").strip()
    if not texto:
        return []
    if texto.startswith("["):
        return json.loads(texto)
    out = []
    for parte in re.split(r"[;\n]", texto):
        parte = parte.strip()
        if not parte:
            continue
        if "@" in parte:
            nome, t = parte.rsplit("@", 1)
            out.append({"_nome": nome.strip(), "inicio": float(t.replace(",", "."))})
        else:
            out.append({"_nome": parte, "inicio": 0.0})
    return out


def blocos_de(layout, duracao_s, tem_tela=False, tem_recorte=False):
    """Normaliza o layout em blocos contíguos [{modo, inicio, fim}] cobrindo 0..duracao_s. Devolve (blocos, avisos)."""
    avisos = []
    if isinstance(layout, (list, dict)):
        brutos = layout.get("blocos", []) if isinstance(layout, dict) else layout
    else:
        brutos = _lista_texto(layout)
    itens = []
    for b in brutos:
        modo = str(b.get("modo") or b.get("_nome") or "").strip().lower()
        if modo not in MODOS:
            raise ErroFerramenta(f"layout: modo '{modo}' não existe. Use: {', '.join(MODOS)}")
        if modo in PRECISA_TELA and not tem_tela:
            avisos.append(f"{modo}@{b.get('inicio', 0)}: precisa da gravação de tela (tela=); ficou 'cheio'")
            modo = "cheio"
        itens.append({"modo": modo, "inicio": max(0.0, min(float(b.get("inicio", 0) or 0), duracao_s))})
    if not itens:
        return [], avisos
    itens.sort(key=lambda b: b["inicio"])
    itens[0]["inicio"] = 0.0
    blocos = []
    for b in itens:
        if blocos and b["modo"] == blocos[-1]["modo"]:
            continue
        if blocos and b["inicio"] - blocos[-1]["inicio"] < MIN_BLOCO_S:
            avisos.append(f"{blocos[-1]['modo']}@{blocos[-1]['inicio']}: bloco com menos de {MIN_BLOCO_S} s, trocado por {b['modo']}")
            blocos[-1]["modo"] = b["modo"]
            if len(blocos) > 1 and blocos[-2]["modo"] == b["modo"]:
                blocos.pop()
            continue
        blocos.append(dict(b))
    for i, b in enumerate(blocos):
        b["fim"] = round(blocos[i + 1]["inicio"] if i + 1 < len(blocos) else duracao_s, 3)
        b["inicio"] = round(b["inicio"], 3)
    if any(b["modo"] == "aula" for b in blocos) and not tem_recorte:
        avisos.append("aula sem rosto recortado: o rosto vai numa bolha (rosto_recortado=true tira o fundo)")
    return blocos, avisos


def cortinas_de(blocos):
    """Instantes das trocas de bloco (a cortina cobre a troca: metade antes, metade depois)."""
    return [b["inicio"] for b in blocos[1:]]


def _palavras(pal):
    from .grafismos import palavras_planas
    return palavras_planas(pal or {})


def passos_de(passos, pal=None, duracao_s=None):
    """[{texto, inicio}] ordenados; aceita 'Exposição@3; ISO@8', JSON com inicio ou palavra (ancora na fala)."""
    from .grafismos import ancorar
    ws = _palavras(pal)
    out, avisos = [], []
    for p in _lista_texto(passos) if isinstance(passos, str) else (passos or []):
        texto = str(p.get("texto") or p.get("_nome") or "").strip()
        if not texto:
            continue
        ini = p.get("inicio")
        if p.get("palavra") and ws:
            t = ancorar(p["palavra"], ws, float(ini) if ini is not None else None)
            if t is None:
                avisos.append(f"passo '{texto}': palavra '{p['palavra']}' não foi dita perto de {ini}")
            else:
                ini = t
        if ini is None:
            avisos.append(f"passo '{texto}' sem início: ignorado"); continue
        out.append({"texto": texto[:22], "inicio": round(max(0.0, float(ini)), 3)})
    out.sort(key=lambda p: p["inicio"])
    if len(out) > 5:
        avisos.append(f"{len(out)} passos: a barra mostra até 5 (os 5 primeiros)"); out = out[:5]
    if duracao_s:
        out = [p for p in out if p["inicio"] < duracao_s]
    return out, avisos


def focos_de(focos, pal=None, duracao_s=None):
    """Focos da câmera virtual normalizados: [{inicio, fim, x, y, zoom, caixa?}] (x, y, caixa de 0 a 1 na tela)."""
    from .grafismos import ancorar
    if isinstance(focos, str):
        focos = json.loads(focos) if focos.strip() else []
    ws = _palavras(pal)
    out, avisos = [], []
    for f in focos or []:
        ini = f.get("inicio")
        if f.get("palavra") and ws:
            t = ancorar(f["palavra"], ws, float(ini) if ini is not None else None)
            ini = t if t is not None else ini
        if ini is None:
            avisos.append("foco sem início: ignorado"); continue
        x, y = float(f.get("x", 0.5)), float(f.get("y", 0.5))
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ErroFerramenta("focos: x e y vão de 0 a 1 (fração da largura e da altura da tela)")
        ini = float(ini); fim = float(f.get("fim", ini + 2.5))
        item = {"inicio": round(ini, 3), "fim": round(max(ini + 0.8, fim), 3), "x": round(x, 4), "y": round(y, 4), "zoom": round(max(1.0, min(3.0, float(f.get("zoom", 1.9)))), 3)}
        if f.get("caixa"):
            cx = [float(v) for v in f["caixa"]]
            if len(cx) != 4 or not all(0 <= v <= 1 for v in cx):
                raise ErroFerramenta("focos: caixa = [x, y, largura, altura] de 0 a 1")
            item["caixa"] = [round(v, 4) for v in cx]
        out.append(item)
    out.sort(key=lambda f: f["inicio"])
    for a, b in zip(out, out[1:]):  # um foco termina quando o próximo começa
        if a["fim"] > b["inicio"]:
            a["fim"] = b["inicio"]
    if duracao_s:
        out = [f for f in out if f["inicio"] < duracao_s]
        for f in out:
            f["fim"] = min(f["fim"], round(duracao_s, 3))
    return out, avisos


def focos_auto(video_tela, fps_amostra=4, largura=320, min_area=0.003, max_area=0.22, segura_s=2.6, intervalo_min_s=2.2, zoom_max=2.2, vivo_frac=0.25, limite_s=None):
    """Câmera virtual sem pedido: compara quadros seguidos da gravação de tela e, quando a mudança é localizada (menu abrindo, janela de
    propriedades, clique que muda um painel), aproxima ali por ~2,6 s. Mudança grande (troca de cena, rolagem) volta ao quadro inteiro;
    só o cursor andando (mudança minúscula) não conta, nem região que muda o tempo todo (webcam na prévia do OBS, vídeo tocando).
    É aproximação: o agente pode passar focos à mão."""
    import cv2
    v = caminho(video_tela); info = info_midia(v)
    H = int(round(info["altura"] * largura / info["largura"] / 2) * 2)
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", str(v)] + (["-t", f"{limite_s:.2f}"] if limite_s else []) + \
          ["-vf", f"fps={fps_amostra},scale={largura}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = largura * H; ant = None; i = 0; mascaras = []
    kernel = np.ones((3, 3), np.uint8)
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        g = np.frombuffer(buf, dtype=np.uint8).reshape(H, largura)
        if ant is not None:
            _, m = cv2.threshold(cv2.absdiff(g, ant), 28, 1, cv2.THRESH_BINARY)
            mascaras.append((i / fps_amostra, np.packbits(cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel))))
        ant = g; i += 1
    p.stdout.close(); p.wait()
    if not mascaras:
        return [], {"amostras": i, "mudancas": 0, "focos": 0, "regiao_viva": 0.0}
    freq = np.zeros(n, np.float32)
    for _, pk in mascaras:
        freq += np.unpackbits(pk)[:n]
    vivo = (freq / len(mascaras)) > vivo_frac
    vivo = cv2.dilate(vivo.reshape(H, largura).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool).ravel()
    mudancas = []
    for t, pk in mascaras:
        m = np.unpackbits(pk)[:n].astype(bool) & ~vivo
        area = float(np.count_nonzero(m)) / n
        if area < min_area:
            continue
        ys, xs = np.divmod(np.nonzero(m)[0], largura)
        x0, x1, y0, y1 = np.percentile(xs, 3), np.percentile(xs, 97), np.percentile(ys, 3), np.percentile(ys, 97)
        w, h = (x1 - x0) / largura, (y1 - y0) / H
        mudancas.append({"t": t, "area": area, "caixa": w * h, "x": (x0 + x1) / 2 / largura, "y": (y0 + y1) / 2 / H, "w": w, "h": h})
    focos = []; ultimo = -99.0
    for m in mudancas:
        if m["area"] > max_area or m["caixa"] > 0.45:  # mudança grande: volta ao quadro inteiro
            if focos and focos[-1]["fim"] > m["t"]:
                focos[-1]["fim"] = round(max(focos[-1]["inicio"] + 0.8, m["t"]), 3)
            continue
        if m["t"] - ultimo < intervalo_min_s:
            continue
        zoom = max(1.4, min(zoom_max, 0.55 / max(m["w"], m["h"], 0.12)))
        if focos and focos[-1]["fim"] > m["t"] - 0.15:
            focos[-1]["fim"] = round(m["t"] - 0.15, 3)
        focos.append({"inicio": round(max(0.0, m["t"] - 0.15), 3), "fim": round(m["t"] + segura_s, 3), "x": round(m["x"], 4), "y": round(m["y"], 4), "zoom": round(zoom, 2)})
        ultimo = m["t"]
    focos = [f for f in focos if f["fim"] - f["inicio"] >= 0.8]
    return focos, {"amostras": i, "mudancas": len(mudancas), "focos": len(focos), "regiao_viva": round(float(vivo.mean()), 3)}


def posicao_rosto(video, fps_amostra=1.0):
    """Onde o rosto costuma ficar no vídeo (mediana das detecções), de 0 a 1: {x, y, achados}. None sem rosto ou sem detector.
    As caixas de rosto dos layouts enquadram por aqui (vídeo com a tela em cima e o rosto embaixo não perde o rosto no corte)."""
    from . import rosto as _rosto
    try:
        pontos, motor = _rosto.rastrear_rosto(video, fps_amostra=fps_amostra)
    except Exception:
        return None
    ok = [(x, y) for _, x, y in pontos if x is not None]
    if motor == "nenhum" or len(ok) < max(2, len(pontos) * 0.2):
        return None
    it = info_midia(caminho(video))
    xs, ys = np.array([a for a, _ in ok]), np.array([b for _, b in ok])
    return {"x": round(float(np.median(xs)) / it["largura"], 3), "y": round(float(np.median(ys)) / it["altura"], 3), "achados": len(ok), "amostras": len(pontos)}


def rastrear_rosto_caixas(video, fps_amostra=1.0):
    """Para cada instante amostrado, o maior rosto como frações do quadro: [(t, cx, cy, w, h)] (None nos campos quando não achou)."""
    from . import rosto as _rosto
    det, motor = _rosto._detector()
    if motor == "nenhum":
        return [], motor
    it = info_midia(caminho(video)); W0, H0 = it["largura"], it["altura"]
    out = []
    for t, rgb, esc in _rosto._quadros(caminho(video), fps_amostra):
        r = det(rgb)
        out.append((t, r[0] / esc / W0, r[1] / esc / H0, r[2] / esc / W0, r[3] / esc / H0) if r else (t, None, None, None, None))
    return out, motor


def _trechos_de(flags, passo_s, duracao_s, min_s=1.0):
    """Lista de bool por amostra → [{inicio, fim, composto}] contíguos; trecho menor que min_s é absorvido pelo anterior."""
    tr = []
    for i, f in enumerate(flags):
        t = round(i * passo_s, 3)
        if tr and tr[-1]["composto"] == f:
            tr[-1]["fim"] = round(t + passo_s, 3); continue
        tr.append({"inicio": t, "fim": round(t + passo_s, 3), "composto": bool(f)})
    # absorve trechos curtos (menos de min_s) no anterior, depois funde vizinhos iguais
    fund = []
    for x in tr:
        if fund and x["fim"] - x["inicio"] < min_s:
            fund[-1]["fim"] = x["fim"]; continue
        fund.append(dict(x))
    out = []
    for x in fund:
        if out and out[-1]["composto"] == x["composto"]:
            out[-1]["fim"] = x["fim"]
        else:
            out.append(x)
    if out:
        out[0]["inicio"] = 0.0; out[-1]["fim"] = round(duracao_s, 3)
    return out


def detectar_composto(video, fps_amostra=2.0, largura=180, fps_rosto=1.0, limiar_borda=10.0, min_trecho_s=1.5):
    """Vídeo vertical "composto" (gravação do OBS com a tela em cima e a câmera do Thiago embaixo, como a série "O óbvio precisa ser dito"):
    acha a linha divisória e, ao longo do tempo, quais trechos estão compostos e quais mostram só o rosto. É o que o 16:9 precisa para pôr
    a tela à esquerda e o rosto à direita em vez do vertical no meio com fundo desfocado.
    Como: o maior rosto por segundo (MediaPipe) diz se o rosto está na metade de baixo (composto) ou no meio (só rosto); nas amostras compostas,
    a mediana do perfil de bordas horizontais acha a linha mais baixa e forte acima do rosto (o fim da janela do OBS); amostra sem rosto usa
    a força da borda nessa linha. Devolve None quando o vídeo não é vertical, não tem rosto ou nunca está composto.
    {divisor, trechos: [{inicio, fim, composto}], rosto_baixo: {x, y}, rosto_cima: {x, y}|None, compostos_s, amostras, motor}."""
    v = caminho(video); info = info_midia(v)
    if not info["largura"] or info["largura"] >= info["altura"]:
        return None
    H = int(round(info["altura"] * largura / info["largura"] / 2) * 2)
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", str(v), "-vf", f"fps={fps_amostra},scale={largura}:{H}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = largura * H; perfis = []
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        g = np.frombuffer(buf, dtype=np.uint8).reshape(H, largura).astype(np.float32)
        perfis.append(np.abs(np.diff(g, axis=0)).mean(axis=1))
    p.stdout.close(); p.wait()
    if not perfis:
        return None
    rostos, motor = rastrear_rosto_caixas(v, fps_rosto)
    if not rostos or not any(r[1] is not None for r in rostos):
        return None
    passo = 1.0 / fps_amostra
    # rosto por amostra (o mais perto no tempo), em frações
    def rosto_em(t):
        melhor = min(rostos, key=lambda r: abs(r[0] - t))
        return melhor if abs(melhor[0] - t) <= 1.0 / fps_rosto and melhor[1] is not None else None
    amostras = [rosto_em(i * passo) for i in range(len(perfis))]
    baixo = [i for i, r in enumerate(amostras) if r and r[2] > 0.6]
    cima = [i for i, r in enumerate(amostras) if r and r[2] <= 0.5]
    if not baixo:
        return None
    topo_rosto = float(np.median([amostras[i][2] - amostras[i][4] / 2 for i in baixo]))  # borda de cima do rosto nas amostras compostas
    med = np.median(np.stack([perfis[i] for i in baixo]), axis=0)
    y0, y1 = int(0.28 * H), int(min(0.74, max(0.3, topo_rosto - 0.04)) * H)
    if y1 <= y0:
        return None
    limiar = max(limiar_borda, 0.6 * float(med[y0:y1].max()))  # relativo à borda mais forte da janela: prateleira/estante do cenário (fraca) não vira divisor
    fortes = [y for y in range(y0, y1) if med[y] >= limiar]
    if fortes:
        yd = max(fortes)                                   # a linha forte mais baixa acima do rosto: o fim da janela do OBS
    else:
        yd = y0 + int(np.argmax(med[y0:y1]))
        if med[yd] < limiar_borda * 0.6:
            return None
    divisor = round((yd + 1) / H, 3); forca = float(med[yd])
    flags = []
    for i, r in enumerate(amostras):
        if r:
            flags.append(r[2] > divisor + 0.08)
        else:                                              # sem rosto na amostra: a borda na linha decide
            flags.append(float(perfis[i][max(0, yd - 2):yd + 3].max()) >= 0.6 * forca)
    if len(flags) >= 5:  # mediana em janela de 5 amostras (2,5 s): um rosto perdido numa amostra não troca o layout
        fl = np.array(flags, dtype=np.int8); k = 2
        flags = [bool(np.median(fl[max(0, i - k):i + k + 1]) >= 0.5) for i in range(len(fl))]
    trechos = _trechos_de(flags, passo, info["duracao_s"], min_s=min_trecho_s)
    comp_s = round(sum(t["fim"] - t["inicio"] for t in trechos if t["composto"]), 2)
    if comp_s <= 0:
        return None
    def mediana(idx):
        if not idx:
            return None
        return {"x": round(float(np.median([amostras[i][1] for i in idx])), 3), "y": round(float(np.median([amostras[i][2] for i in idx])), 3)}
    return {"divisor": divisor, "trechos": trechos, "rosto_baixo": mediana(baixo), "rosto_cima": mediana(cima), "compostos_s": comp_s,
            "amostras": len(perfis), "forca_borda": round(forca, 1), "motor": motor}


def recortar_rosto(video, saida_webm, altura_max=720, suavizar=0.55, qualidade="normal", limite_s=None):
    """Tira o fundo do vídeo do rosto e grava .webm VP9 com transparência, no máximo altura_max px de altura (o rosto aparece pequeno no canto).
    qualidade "normal" = selfie segmenter (rápido); "alta" = selfie multiclass (cabelo e roupa melhores, ~12× mais lento).
    suavizar = média temporal da máscara (menos tremido)."""
    import cv2
    preparar_mediapipe()
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    modelo = MODELO_SEG_ALTA if qualidade == "alta" else MODELO_SEG
    if not modelo.exists():
        raise ErroFerramenta(f"modelos/{modelo.name} não encontrado")
    v = caminho(video); info = info_midia(v)
    esc = min(1.0, altura_max / info["altura"])
    W = int(round(info["largura"] * esc / 2) * 2); H = int(round(info["altura"] * esc / 2) * 2)
    fps = info.get("fps") or 30
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(modelo), delegate=BaseOptions.Delegate.CPU),
                                                                                  output_confidence_masks=True, output_category_mask=False))
    out = caminho_saida(saida_webm)
    ler = subprocess.Popen([FFMPEG, "-hide_banner", "-nostats", "-i", str(v)] + (["-t", f"{limite_s:.2f}"] if limite_s else []) +
                           ["-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    gravar = subprocess.Popen([FFMPEG, "-y", "-hide_banner", "-nostats", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                               "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "32", "-deadline", "realtime", "-cpu-used", "8",
                               "-row-mt", "1", "-auto-alt-ref", "0", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    n = W * H * 3; media = None; quadros = 0
    try:
        while True:
            buf = ler.stdout.read(n)
            if len(buf) < n:
                break
            rgb = np.frombuffer(buf, dtype=np.uint8).reshape(H, W, 3)
            r = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
            m0 = np.array(np.squeeze(r.confidence_masks[0].numpy_view()), dtype=np.float32)  # cópia: a memória da máscara é liberada no próximo segment()
            alfa = 1.0 - m0 if len(r.confidence_masks) > 1 else m0  # multiclass: máscara 0 = fundo; segmenter: máscara única = pessoa
            if alfa.shape != (H, W):
                alfa = cv2.resize(alfa, (W, H), interpolation=cv2.INTER_LINEAR)
            media = alfa if media is None else suavizar * media + (1 - suavizar) * alfa
            a = np.clip((media - 0.35) / 0.3, 0, 1)            # borda firme, sem halo
            a = cv2.GaussianBlur(a, (0, 0), max(1.0, H / 480))  # pena leve
            rgba = np.dstack([rgb, (a * 255).astype(np.uint8)])
            gravar.stdin.write(rgba.tobytes()); quadros += 1
    finally:
        ler.stdout.close(); ler.wait()
        gravar.stdin.close(); err = gravar.stderr.read().decode(errors="ignore"); gravar.wait()
    if gravar.returncode != 0 or not out.exists() or quadros == 0:
        raise ErroFerramenta(f"recorte do rosto falhou: {err[-600:]}")
    return {"video": str(out), "largura": W, "altura": H, "quadros": quadros, "duracao_s": round(quadros / fps, 2)}


def tela_cobre_edl(edl, duracao_tela):
    """A gravação de tela acompanha o bruto do rosto (mesma sessão do OBS) quando vai até o fim do último trecho mantido."""
    manter = (edl or {}).get("manter") or []
    return bool(manter) and duracao_tela >= manter[-1]["fim"] - 1.0
