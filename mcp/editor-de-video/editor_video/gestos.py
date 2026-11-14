"""Gestos e olhar do Thiago (10/11/2026): MediaPipe Gesture Recognizer + Face Landmarker viram gatilhos de grafismo e de cutaway.
- detectar_gestos(video, saida_json): amostra o vídeo a `fps_amostra` quadros/s, reconhece a mão (Thumb_Up, Thumb_Down, Victory, Pointing_Up,
  Open_Palm, Closed_Fist, ILoveYou) e a pose da cabeça (virada para a esquerda/direita da tela ou olhando para a câmera, pelo yaw estimado
  do nariz entre as bochechas), agrupa em eventos com início/fim/confiança e descarta os que duram menos de `min_dur_s`.
- O plano de grafismos aceita `gesto` no lugar de `palavra` (grafismos.normalizar) e `planejar_grafismos(gestos_json=)` sugere no rascunho:
  polegar para cima → checklist; apontar para cima → kicker; cabeça virada → sugestão de cutaway (texto; nada automático na montagem).
- Modelos .task: EDITOR_GS_MODELOS, depois modelos/ do repo, depois ~/EditorGS/modelos/ (baixados do storage oficial do Google na primeira vez;
  sem rede, erro claro com a URL para baixar à mão). Licença dos modelos: Apache 2.0 (MediaPipe)."""
import json, os, subprocess, sys, urllib.request
from pathlib import Path
import numpy as np
from .util import FFMPEG, ErroFerramenta, caminho, caminho_saida, info_midia, preparar_mediapipe

RAIZ = Path(__file__).resolve().parents[3]
URLS = {
    "gesture_recognizer.task": "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task",
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
}
GESTOS = {"Thumb_Up": "polegar_cima", "Thumb_Down": "polegar_baixo", "Victory": "vitoria", "Pointing_Up": "apontar_cima",
          "Open_Palm": "mao_aberta", "Closed_Fist": "punho", "ILoveYou": "amo_voce"}
CABECA = ("virada_esquerda", "virada_direita", "olhando_camera")
TIPOS = tuple(GESTOS.values()) + CABECA
NARIZ, BOCHECHA_ESQ, BOCHECHA_DIR = 1, 234, 454  # índices do FaceLandmarker (478 pontos); 234 fica à esquerda da imagem, 454 à direita
_REC = {}


def pastas_modelos():
    """Onde procurar os .task, em ordem."""
    out = []
    if os.environ.get("EDITOR_GS_MODELOS"):
        out.append(Path(os.environ["EDITOR_GS_MODELOS"]).expanduser())
    out.append(RAIZ / "modelos")
    home = os.environ.get("EDITOR_GS_HOME") or str(Path.home() / "EditorGS")
    out.append(Path(home).expanduser() / "modelos")
    return out


def caminho_modelo(nome, baixar=True):
    """Caminho do modelo `nome`; baixa do storage oficial do Google para a pasta de dados (~/EditorGS/modelos ou modelos/ do repo) quando falta.
    Sem rede ou com baixar=False, ErroFerramenta explicando onde salvar o arquivo."""
    for p in pastas_modelos():
        if (p / nome).exists() and (p / nome).stat().st_size > 1000:
            return p / nome
    url = URLS.get(nome)
    destino = pastas_modelos()[-1] if (Path(os.environ.get("EDITOR_GS_HOME") or (Path.home() / "EditorGS"))).is_dir() else RAIZ / "modelos"
    if os.environ.get("EDITOR_GS_MODELOS"):
        destino = Path(os.environ["EDITOR_GS_MODELOS"]).expanduser()
    if not baixar or not url:
        raise ErroFerramenta(f"modelo {nome} não encontrado: baixe {url or '(sem URL)'} e salve em {destino / nome}")
    try:
        destino.mkdir(parents=True, exist_ok=True); tmp = destino / (nome + ".parte")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "EditorGS"}), timeout=120) as r, open(tmp, "wb") as f:
            f.write(r.read())
        tmp.replace(destino / nome)
    except Exception as e:  # noqa: BLE001
        raise ErroFerramenta(f"não consegui baixar {nome} ({type(e).__name__}: {e}); sem rede, baixe {url} e salve em {destino / nome}")
    return destino / nome


def yaw_de_pontos(nariz_x, esq_x, dir_x):
    """Yaw estimado (graus, positivo = rosto apontando para a direita da imagem) pela posição do nariz entre as bochechas: 0,5 = de frente."""
    larg = dir_x - esq_x
    if larg <= 1e-6:
        return 0.0
    r = (nariz_x - esq_x) / larg
    return float((r - 0.5) * 2.0 * 60.0)


def rotulo_cabeca(yaw, limiar=18.0):
    if yaw <= -limiar:
        return "virada_esquerda"
    if yaw >= limiar:
        return "virada_direita"
    return "olhando_camera"


def _reconhecedores(baixar=True):
    """(reconhecer_gestos(rgb) → [(tipo, conf)], pose_cabeca(rgb) → (tipo, conf, yaw) | None), criados uma vez."""
    if "fn" in _REC:
        return _REC["fn"]
    preparar_mediapipe()
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    mg = caminho_modelo("gesture_recognizer.task", baixar); mf = caminho_modelo("face_landmarker.task", baixar)
    rec = vision.GestureRecognizer.create_from_options(vision.GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_path=str(mg)), running_mode=vision.RunningMode.IMAGE, num_hands=2, min_hand_detection_confidence=0.5))
    lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(mf)), running_mode=vision.RunningMode.IMAGE, num_faces=1))

    def imagem(rgb):
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))

    def gestos(rgb):
        r = rec.recognize(imagem(rgb)); out = []
        for mao in r.gestures or []:
            if not mao:
                continue
            top = max(mao, key=lambda c: c.score)
            tipo = GESTOS.get(top.category_name)
            if tipo and top.score >= 0.5:
                out.append((tipo, float(top.score)))
        return out

    def cabeca(rgb):
        r = lm.detect(imagem(rgb))
        if not r.face_landmarks:
            return None
        pts = r.face_landmarks[0]; w = rgb.shape[1]
        yaw = yaw_de_pontos(pts[NARIZ].x * w, pts[BOCHECHA_ESQ].x * w, pts[BOCHECHA_DIR].x * w)
        return None, 1.0, round(yaw, 1)  # o rótulo é dado em detectar_gestos, com o limiar pedido
    _REC["fn"] = (gestos, cabeca)
    return _REC["fn"]


def _quadros(video, fps_amostra, inicio_s=None, fim_s=None, largura=480):
    """(t, rgb) a cada 1/fps_amostra s, reduzido para detecção; t no tempo do vídeo."""
    info = info_midia(video); w, h = info["largura"], info["altura"]
    esc = largura / w; W, H = largura, int(round(h * esc / 2) * 2)
    cmd = [FFMPEG, "-hide_banner", "-nostats"]
    if inicio_s:
        cmd += ["-ss", f"{float(inicio_s):.3f}"]
    cmd += ["-i", str(video)]
    if fim_s:
        cmd += ["-t", f"{max(0.0, float(fim_s) - float(inicio_s or 0)):.3f}"]
    cmd += ["-vf", f"fps={fps_amostra},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = W * H * 3; i = 0; t0 = float(inicio_s or 0)
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield t0 + i / fps_amostra, np.frombuffer(buf, dtype=np.uint8).reshape(H, W, 3)
            i += 1
    finally:
        p.stdout.close(); p.wait()


def agrupar(amostras, passo_s, min_dur_s=0.4, tolerancia=1):
    """amostras = [(t, [(tipo, conf), ...])] em ordem. Junta amostras seguidas do mesmo tipo (até `tolerancia` amostras sem ele no meio)
    num evento {tipo, inicio, fim, confianca}; fim = última amostra + passo. Descarta eventos mais curtos que min_dur_s."""
    abertos = {}; eventos = []

    def fechar(tipo):
        ev = abertos.pop(tipo)
        dur = ev["fim"] - ev["inicio"]
        if dur + 1e-9 >= min_dur_s:
            eventos.append({"tipo": tipo, "inicio": round(ev["inicio"], 2), "fim": round(ev["fim"], 2), "confianca": round(sum(ev["confs"]) / len(ev["confs"]), 2), "amostras": len(ev["confs"])})
    for t, rotulos in amostras:
        vistos = {}
        for tipo, conf in rotulos:
            vistos[tipo] = max(vistos.get(tipo, 0.0), float(conf))
        for tipo, conf in vistos.items():
            ev = abertos.get(tipo)
            if ev and t - ev["ultimo"] <= passo_s * (tolerancia + 1) + 1e-6:
                ev["fim"] = t + passo_s; ev["ultimo"] = t; ev["confs"].append(conf)
            else:
                if ev:
                    fechar(tipo)
                abertos[tipo] = {"inicio": t, "fim": t + passo_s, "ultimo": t, "confs": [conf]}
        for tipo in list(abertos):
            if tipo not in vistos and t - abertos[tipo]["ultimo"] > passo_s * (tolerancia + 1) + 1e-6:
                fechar(tipo)
    for tipo in list(abertos):
        fechar(tipo)
    return sorted(eventos, key=lambda e: (e["inicio"], e["tipo"]))


def resumo_de(eventos, n_amostras, com_rosto, olhando):
    """Frase curta para a conversa: quantos gestos, quantas viradas, quanto do tempo com o rosto para a câmera."""
    gestos = [e for e in eventos if e["tipo"] in GESTOS.values()]
    viradas = [e for e in eventos if e["tipo"] in ("virada_esquerda", "virada_direita")]
    partes = []
    if gestos:
        por = {}
        for e in gestos:
            por[e["tipo"]] = por.get(e["tipo"], 0) + 1
        partes.append("gestos: " + ", ".join(f"{k} ×{v}" for k, v in sorted(por.items())))
    else:
        partes.append("nenhum gesto de mão reconhecido")
    if viradas:
        partes.append(f"{len(viradas)} virada(s) de cabeça (candidatas a cutaway): " + "; ".join(f"{e['tipo'].split('_')[1]} {e['inicio']}–{e['fim']} s" for e in viradas[:6]))
    if n_amostras:
        partes.append(f"rosto em {100 * com_rosto // n_amostras}% das amostras, olhando para a câmera em {100 * olhando // max(1, com_rosto)}% delas" if com_rosto else "nenhum rosto encontrado")
    return "; ".join(partes) + "."


def detectar_gestos(video, saida_json=None, fps_amostra=5, inicio_s=None, fim_s=None, min_dur_s=0.4, limiar_virada=18.0, baixar_modelos=True):
    """Eventos de gesto e de pose da cabeça do vídeo (tempos do próprio arquivo: rode no vídeo cortado para usar no plano de grafismos).
    Devolve {"eventos": [{tipo, inicio, fim, confianca}], "resumo": "...", "amostras", "olhar": {...}}; com saida_json, grava o mesmo JSON.
    `olhando_camera` vira evento só para dar os trechos; as viradas (virada_esquerda/direita) são as candidatas a cutaway."""
    v = caminho(video); fps_amostra = max(1, int(fps_amostra)); passo = 1.0 / fps_amostra
    reconhecer, cabeca = _reconhecedores(baixar_modelos)
    amostras = []; n = 0; com_rosto = 0; olhando = 0; yaws = []
    for t, rgb in _quadros(v, fps_amostra, inicio_s, fim_s):
        rotulos = reconhecer(rgb)
        pose = cabeca(rgb)
        if pose:
            rot = rotulo_cabeca(pose[2], limiar_virada)
            com_rosto += 1; yaws.append(pose[2]); rotulos.append((rot, pose[1]))
            if rot == "olhando_camera":
                olhando += 1
        amostras.append((round(t, 3), rotulos)); n += 1
    eventos = agrupar(amostras, passo, min_dur_s=min_dur_s)
    out = {"video": str(v), "fps_amostra": fps_amostra, "inicio_s": float(inicio_s) if inicio_s is not None else 0.0, "fim_s": float(fim_s) if fim_s is not None else None,
           "amostras": n, "eventos": eventos, "olhar": {"amostras_com_rosto": com_rosto, "olhando_camera_pct": round(100.0 * olhando / com_rosto, 1) if com_rosto else None,
                                                        "yaw_medio": round(float(np.mean(yaws)), 1) if yaws else None, "limiar_virada": limiar_virada},
           "resumo": resumo_de(eventos, n, com_rosto, olhando), "tipos": list(TIPOS)}
    if saida_json:
        p = caminho_saida(saida_json); p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"); out["arquivo"] = str(p)
    return out


def eventos_de(gestos):
    """Lista de eventos a partir de: caminho do gestos.json, JSON inline, dict {"eventos": [...]} ou lista. Vazio/None → []."""
    if not gestos:
        return []
    if isinstance(gestos, (str, Path)):
        t = str(gestos).strip()
        gestos = json.loads(t) if t.startswith(("{", "[")) else json.loads(Path(caminho(t)).read_text(encoding="utf-8"))
    if isinstance(gestos, dict):
        gestos = gestos.get("eventos", [])
    return [e for e in (gestos or []) if isinstance(e, dict) and e.get("tipo") and e.get("inicio") is not None]


def ancorar_gesto(tipo, eventos, perto=None, janela_s=6.0):
    """Início do evento do tipo mais próximo de `perto` (sem `perto`, o primeiro). None se não houver (ou se o mais perto estiver fora da janela)."""
    cands = [float(e["inicio"]) for e in eventos if str(e.get("tipo")) == str(tipo)]
    if not cands:
        return None
    if perto is None:
        return cands[0]
    melhor = min(cands, key=lambda t: abs(t - float(perto)))
    return melhor if abs(melhor - float(perto)) <= janela_s else None
