"""Reenquadramento seguindo o rosto (MediaPipe; fallback Haar do OpenCV)."""
import os, subprocess, tempfile
from pathlib import Path
import numpy as np
from .util import FFMPEG, caminho, caminho_saida, rodar, info_midia, ErroFerramenta, preparar_mediapipe

RAIZ = Path(__file__).resolve().parents[3]
MODELO = RAIZ / "modelos" / "blaze_face_short_range.tflite"
ALVOS = {("9x16", "720p"): (720, 1280), ("9x16", "1080p"): (1080, 1920), ("16x9", "720p"): (1280, 720), ("16x9", "1080p"): (1920, 1080), ("1x1", "720p"): (720, 720), ("1x1", "1080p"): (1080, 1080)}


def _quadros(video, fps_amostra, largura_amostra=480):
    """Gera (t, frame RGB numpy) a cada 1/fps_amostra s, reduzido para detecção."""
    info = info_midia(video); w, h = info["largura"], info["altura"]
    esc = largura_amostra / w; W, H = largura_amostra, int(round(h * esc / 2) * 2)
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", str(video), "-vf", f"fps={fps_amostra},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = W * H * 3; i = 0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield i / fps_amostra, np.frombuffer(buf, dtype=np.uint8).reshape(H, W, 3), esc
        i += 1
    p.stdout.close(); p.wait()


def _detector():
    try:
        preparar_mediapipe()
        import mediapipe as mp
        from mediapipe.tasks.python import vision, BaseOptions
        det = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(base_options=BaseOptions(model_asset_path=str(MODELO)), min_detection_confidence=0.5))
        def f(rgb):
            r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
            if not r.detections:
                return None
            b = max(r.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height).bounding_box
            return (b.origin_x + b.width / 2, b.origin_y + b.height / 2, b.width, b.height)
        return f, "mediapipe"
    except Exception:
        import cv2
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if casc.empty():  # OpenCV 5 (wheel) não traz os cascades: sem detector, o reenquadre cai no centro
            return (lambda rgb: None), "nenhum"
        def f(rgb):
            g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            faces = casc.detectMultiScale(g, 1.2, 4, minSize=(40, 40))
            if len(faces) == 0:
                return None
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            return (x + w / 2, y + h / 2, w, h)
        return f, "haar"


def rastrear_rosto(video, fps_amostra=4):
    """Lista de (t, cx, cy) no tamanho original; None quando não achou."""
    det, motor = _detector(); pontos = []
    for t, rgb, esc in _quadros(caminho(video), fps_amostra):
        r = det(rgb)
        pontos.append((t, r[0] / esc, r[1] / esc) if r else (t, None, None))
    return pontos, motor


def reenquadrar(video, saida_video, formato="9x16", resolucao="1080p", fps_amostra=4, suavizacao_s=1.2, margem_topo=0.42, crf=20, fps=30):
    """Recorta seguindo o rosto ao mudar de orientação (ex.: 16:9 → 9:16). O centro do recorte é a média móvel da posição do rosto; sem rosto, mantém o último."""
    v = caminho(video); info = info_midia(v); W0, H0 = info["largura"], info["altura"]
    if (formato, resolucao) not in ALVOS:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    W, H = ALVOS[(formato, resolucao)]; alvo = W / H
    # janela de recorte no original com a proporção alvo
    if W0 / H0 > alvo:
        ch = H0; cw = int(round(H0 * alvo / 2) * 2)
    else:
        cw = W0; ch = int(round(W0 / alvo / 2) * 2)
    pontos, motor = rastrear_rosto(v, fps_amostra)
    achados = sum(1 for _, x, _ in pontos if x is not None)
    if achados == 0:
        raise ErroFerramenta("Nenhum rosto encontrado: use montar com enquadramento centro ou desfocado.")
    return _recortar_por_pontos(v, saida_video, pontos, formato, resolucao, extra={"motor": motor, "amostras": len(pontos), "rosto_em": achados, "modo": "rosto"},
                                fps_amostra=fps_amostra, suavizacao_s=suavizacao_s, margem_topo=margem_topo, crf=crf, fps=fps)


def _recortar_por_pontos(v, saida_video, pontos, formato, resolucao, extra=None, fps_amostra=4, suavizacao_s=1.2, margem_topo=0.42, crf=20, fps=30):
    """Recorta o vídeo seguindo uma série de (t, cx, cy) (None = sem rosto naquele instante): preenche buracos, suaviza e aplica crop dinâmico."""
    info = info_midia(v); W0, H0 = info["largura"], info["altura"]
    if (formato, resolucao) not in ALVOS:
        raise ErroFerramenta(f"Formato/resolução não suportado: {formato} {resolucao}")
    W, H = ALVOS[(formato, resolucao)]; alvo = W / H
    if W0 / H0 > alvo:
        ch = H0; cw = int(round(H0 * alvo / 2) * 2)
    else:
        cw = W0; ch = int(round(W0 / alvo / 2) * 2)
    ult = (W0 / 2, H0 / 2); serie = []
    for t, x, y in pontos:
        if x is not None:
            ult = (x, y)
        serie.append((t, ult[0], ult[1]))
    k = max(1, int(round(suavizacao_s * fps_amostra)))
    xs = np.array([p[1] for p in serie]); ys = np.array([p[2] for p in serie])
    kern = np.ones(k) / k
    xs = np.convolve(np.pad(xs, (k // 2, k - 1 - k // 2), mode="edge"), kern, mode="valid"); ys = np.convolve(np.pad(ys, (k // 2, k - 1 - k // 2), mode="edge"), kern, mode="valid")
    cmds = []
    for (t, _, _), cx, cy in zip(serie, xs, ys):
        x = int(min(max(0, cx - cw / 2), W0 - cw)); y = int(min(max(0, cy - ch * margem_topo), H0 - ch))
        cmds.append(f"{t:.3f} crop x {x}, crop y {y};")
    with tempfile.NamedTemporaryFile("w", suffix=".cmd", delete=False) as f:
        f.write("\n".join(cmds) + "\n"); cmd_path = f.name
    out = caminho_saida(saida_video)
    vf = f"sendcmd=f='{cmd_path}',crop={cw}:{ch}:{int(W0/2-cw/2)}:{int(H0/2-ch/2)},scale={W}:{H}"
    cmd = [FFMPEG, "-y", "-hide_banner", "-nostats", "-i", v, "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    cmd += (["-c:a", "aac", "-b:a", "160k"] if info["tem_audio"] else ["-an"])
    rodar(cmd + [out]); os.unlink(cmd_path)
    o = info_midia(out)
    return {"video": str(out), "largura": o["largura"], "altura": o["altura"], "duracao_s": o["duracao_s"], "janela": [cw, ch], **(extra or {})}


MODELO_LM = RAIZ / "modelos" / "face_landmarker.task"
LABIOS = (13, 14)  # pontos do lábio superior/inferior no FaceLandmarker (478 pontos)
OLHOS = (33, 263)


def _landmarker(max_rostos=4):
    preparar_mediapipe()
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    if not MODELO_LM.exists():
        raise ErroFerramenta("modelos/face_landmarker.task não encontrado")
    lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MODELO_LM)), num_faces=max_rostos, running_mode=vision.RunningMode.IMAGE))
    def f(rgb):
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
        h, w = rgb.shape[:2]; out = []
        for pts in r.face_landmarks:
            xs = [q.x * w for q in pts]; ys = [q.y * h for q in pts]
            boca = abs(pts[LABIOS[0]].y - pts[LABIOS[1]].y) * h; olhos = abs(pts[OLHOS[0]].x - pts[OLHOS[1]].x) * w or 1.0
            out.append({"cx": (min(xs) + max(xs)) / 2, "cy": (min(ys) + max(ys)) / 2, "w": max(xs) - min(xs), "h": max(ys) - min(ys), "boca": boca / olhos})
        return out
    return f


def rastrear_rostos(video, fps_amostra=4, max_rostos=4):
    """Para cada instante amostrado, a lista de rostos (cx, cy, w, h no tamanho original e abertura da boca relativa).
    Rostos são associados entre quadros pela posição (mesma 'faixa' = mesmo id)."""
    det = _landmarker(max_rostos); faixas = []  # cada faixa: {"id", "pontos": [(t, cx, cy, w, h, boca)]}
    for t, rgb, esc in _quadros(caminho(video), fps_amostra):
        for r in det(rgb):
            cx, cy, w, h = r["cx"] / esc, r["cy"] / esc, r["w"] / esc, r["h"] / esc
            melhor = None
            for fx in faixas:
                ut = fx["pontos"][-1]
                if t - ut[0] <= 2.0 and abs(ut[1] - cx) < max(w, ut[3]) * 1.2 and abs(ut[2] - cy) < max(h, ut[4]) * 1.2:
                    melhor = fx; break
            if melhor is None:
                melhor = {"id": len(faixas), "pontos": []}; faixas.append(melhor)
            melhor["pontos"].append((t, cx, cy, w, h, r["boca"]))
    return faixas


def falante_ativo(faixas, janela_s=1.0, duracao_s=None):
    """Quem está falando em cada janela: o rosto cuja abertura de boca mais varia (movimento labial). Devolve [(t_ini, t_fim, id_faixa)]."""
    if not faixas:
        return []
    fim = duracao_s or max(p[0] for fx in faixas for p in fx["pontos"])
    saida, t = [], 0.0
    atual = max(faixas, key=lambda fx: len(fx["pontos"]))["id"]
    while t < fim:
        melhor, melhor_var = None, -1.0
        for fx in faixas:
            bs = [p[5] for p in fx["pontos"] if t <= p[0] < t + janela_s]
            if len(bs) >= 2:
                var = float(np.std(bs))
                if var > melhor_var:
                    melhor, melhor_var = fx["id"], var
        if melhor is not None and melhor_var > 0.012:
            atual = melhor
        saida.append((round(t, 3), round(min(t + janela_s, fim), 3), atual)); t += janela_s
    # junta janelas iguais
    junto = []
    for a, b, i in saida:
        if junto and junto[-1][2] == i:
            junto[-1] = (junto[-1][0], b, i)
        else:
            junto.append((a, b, i))
    return junto


def reenquadrar_falante(video, saida_video, formato="9x16", resolucao="1080p", fps_amostra=4, min_troca_s=1.5):
    """Reenquadra seguindo quem fala (vários rostos). Se só há um rosto, equivale ao modo rosto. Devolve quantas trocas de falante houve."""
    faixas = rastrear_rostos(video, fps_amostra)
    if not faixas:
        raise ErroFerramenta("Nenhum rosto encontrado para reenquadrar.")
    info = info_midia(caminho(video)); trechos = falante_ativo(faixas, 1.0, info["duracao_s"])
    # trechos muito curtos herdam o anterior (evita pingue-pongue)
    est = []
    for a, b, i in trechos:
        if est and b - a < min_troca_s:
            est[-1] = (est[-1][0], b, est[-1][2])
        else:
            est.append((a, b, i))
    por_id = {fx["id"]: fx["pontos"] for fx in faixas}
    pontos = []
    t = 0.0
    while t <= info["duracao_s"]:
        i = next((i for a, b, i in est if a <= t < b), est[-1][2])
        ps = por_id[i]; p = min(ps, key=lambda q: abs(q[0] - t))
        pontos.append((t, p[1], p[2])); t += 1.0 / fps_amostra
    return _recortar_por_pontos(video, saida_video, pontos, formato, resolucao, extra={"rostos": len(faixas), "trocas": max(0, len(est) - 1), "modo": "falante"})


def reenquadrar_dividido(video, saida_video, formato="9x16", resolucao="1080p", fps_amostra=2):
    """Dois rostos (call, podcast): tela dividida em cima/embaixo no 9:16, cada metade centrada num rosto (posição média, câmera parada)."""
    faixas = sorted(rastrear_rostos(video, fps_amostra), key=lambda fx: -len(fx["pontos"]))[:2]
    if len(faixas) < 2:
        raise ErroFerramenta("Preciso de dois rostos para a tela dividida; achei %d." % len(faixas))
    v = caminho(video); info = info_midia(v); W, H = ALVOS[(formato, resolucao)]
    faixas.sort(key=lambda fx: np.mean([p[1] for p in fx["pontos"]]))  # esquerda em cima
    out = caminho_saida(saida_video); partes = []
    for k, fx in enumerate(faixas):
        cx = float(np.mean([p[1] for p in fx["pontos"]])); cy = float(np.mean([p[2] for p in fx["pontos"]]))
        alvo_w, alvo_h = W, H // 2
        esc = max(alvo_w / info["largura"], alvo_h / info["altura"]) * 1.0
        cw, ch = int(alvo_w / esc), int(alvo_h / esc)
        x = int(min(max(0, cx - cw / 2), info["largura"] - cw)); y = int(min(max(0, cy - ch / 2), info["altura"] - ch))
        partes.append(f"[0:v]crop={cw}:{ch}:{x}:{y},scale={alvo_w}:{alvo_h}[p{k}]")
    filtro = ";".join(partes) + ";[p0][p1]vstack=inputs=2[v]"
    rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-i", v, "-filter_complex", filtro, "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    return {"video": str(out), "largura": W, "altura": H, "modo": "dividido", "rostos": 2}
