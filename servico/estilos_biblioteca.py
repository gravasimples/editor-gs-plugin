"""Biblioteca de estilos (03/11/2026): estilos completos, modelos de legenda, animações, transições, elementos e formatos, com prévia
feita pelos motores da entrega (servico/previa_estilo.py), cache por conteúdo e fila de um render por vez.
Os .json continuam sendo o que o agente lê (estilos/*.json, estilos/legendas/*.json, estilos/elementos.json); a página só os apresenta."""
import hashlib, json, os, re, subprocess, sys, threading, time
from collections import deque
from pathlib import Path
from servico import plataforma

RAIZ = Path(__file__).resolve().parents[1]
EST = RAIZ / "estilos"; LEG = EST / "legendas"; ELEM = EST / "elementos.json"
from servico import caminhos as _cam
PREVIAS = _cam.WORKSPACE / "estilos-previas"
VERSAO_PREVIA = "1"  # muda quando a amostra ou o renderizador mudam (invalida o cache)
PY = str(plataforma.python_editor_gs())

TEMAS = [("tutorial", "Tutorial"), ("dica", "Dica rápida"), ("lista", "Lista"), ("opiniao", "Opinião"), ("historia", "História"), ("bastidor", "Bastidor"),
         ("depoimento", "Depoimento"), ("entrevista", "Entrevista"), ("anuncio", "Anúncio"), ("gancho", "Gancho"), ("novidade", "Novidade"), ("antes-depois", "Antes e depois"),
         ("youtube", "YouTube"), ("aula", "Aula"), ("energia", "Energia"), ("tela", "Tela do OBS"), ("cliente", "Cliente / fora da marca")]

# elemento da biblioteca → efeito no bloco `montagem` de um estilo montado pela página
ELEMENTO_MONTAGEM = {
    "zoom-frase": {"zoom_por_frase": True}, "ritmo-4s": {"ritmo_zoom_s": 4}, "clarao": {"clarao_transicao": True},
    "gancho-palavra": {"gancho_animacao": "palavra"}, "gancho-bloco": {"gancho_animacao": "bloco"}, "vinheta": {"vinheta": True},
    "palavras-chave": {"palavras_chave": "auto"}, "capitulos": {"capitulos_obrigatorios": True}, "capitulos-auto": {"capitulos": "auto"}, "barra-progresso": {"barra_progresso": True},
    "terco-inferior": {"terco_inferior": True}, "broll-janela": {"broll": "auto"}, "broll-cheio": {"broll": "auto", "broll_modo": "cheio"},
    "tela-final": {"tela_final_cta": True}, "sfx": {"sfx": True},
}
DESLIGADO = {"zoom_por_frase": False, "ritmo_zoom_s": 0, "clarao_transicao": False, "gancho_animacao": "", "vinheta": False, "palavras_chave": "",
             "capitulos_obrigatorios": False, "capitulos": "", "barra_progresso": False, "terco_inferior": False, "broll": "", "tela_final_cta": False, "sfx": False, "trilha": ""}


def _ler(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def estilos():
    return [{"nome": p.stem, **_ler(p)} for p in sorted(EST.glob("*.json")) if p.name != "elementos.json"]


def legendas():
    return sorted((_ler(p) for p in LEG.glob("*.json")), key=lambda d: d.get("ordem", 99))


def elementos():
    return _ler(ELEM)["itens"]


def _spec(tipo, id_):
    if tipo == "estilo":
        p = EST / f"{id_}.json"
        d = _ler(p); return {k: d.get(k) for k in ("legenda", "montagem")}
    if tipo == "legenda":
        return _ler(LEG / f"{id_}.json")["legenda"]
    if tipo == "elemento":
        return next(i["previa"] for i in elementos() if i["id"] == id_)
    raise KeyError(tipo)


POSTER_S = {"elemento:tela-final": 7.6, "elemento:vinheta": 0.5, "elemento:sfx": 7.6, "elemento:clarao": 2.25, "elemento:carrossel-video": 1.0, "legenda:palavra-unica": 1.6}


def fazer_poster(tipo, id_, video):
    """Quadro do instante em que o efeito aparece (legenda já na tela, transição no meio), para a galeria mostrar a diferença antes de tocar."""
    t = POSTER_S.get(f"{tipo}:{id_}", 3.6 if tipo == "legenda" else 2.2 if tipo == "elemento" else 1.6)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-q:v", "4", str(Path(video).with_suffix(".jpg"))], timeout=60)


def arquivo_previa(tipo, id_):
    if not re.match(r"^[a-z0-9\-]+$", id_ or "") or tipo not in ("estilo", "legenda", "elemento"):
        raise KeyError("id inválido")
    h = hashlib.sha1((VERSAO_PREVIA + json.dumps(_spec(tipo, id_), sort_keys=True, ensure_ascii=False)).encode()).hexdigest()[:10]
    return PREVIAS / f"{tipo}-{id_}-{h}.mp4"


# fila: um render por vez, em segundo plano
_fila = deque(); _estado = {}; _lock = threading.Lock(); _thread = None


def _env():
    return plataforma.ambiente_cuda(python=PY)


def _trabalhar():
    global _thread
    while True:
        with _lock:
            if not _fila:
                _thread = None; return
            tipo, id_ = _fila.popleft(); chave = f"{tipo}:{id_}"; _estado[chave] = {"estado": "gerando", "desde": time.time()}
        try:
            alvo = arquivo_previa(tipo, id_)
            r = subprocess.run([PY, "-I", "-X", "utf8", str(RAIZ / "servico" / "previa_estilo.py"), tipo, id_, str(alvo)], capture_output=True, text=True, timeout=900, env=_env())
            if r.returncode != 0 or not alvo.exists():
                raise RuntimeError((r.stderr or r.stdout or "falhou").strip().splitlines()[-1][:300])
            fazer_poster(tipo, id_, alvo)
            for velho in list(PREVIAS.glob(f"{tipo}-{id_}-*.mp4")) + list(PREVIAS.glob(f"{tipo}-{id_}-*.jpg")):  # versões antigas do mesmo item
                if velho.stem != alvo.stem:
                    velho.unlink(missing_ok=True)
            with _lock:
                _estado.pop(chave, None)
        except Exception as ex:  # noqa: BLE001
            with _lock:
                _estado[chave] = {"estado": "erro", "erro": str(ex)[:300]}


def pedir_previas(itens):
    """itens = [(tipo, id)]; enfileira o que ainda não tem prévia nem está na fila. Devolve quantos entraram."""
    global _thread
    PREVIAS.mkdir(parents=True, exist_ok=True); n = 0
    with _lock:
        for tipo, id_ in itens:
            chave = f"{tipo}:{id_}"
            try:
                if arquivo_previa(tipo, id_).exists() or _estado.get(chave, {}).get("estado") in ("fila", "gerando"):
                    continue
            except (KeyError, FileNotFoundError, StopIteration):
                continue
            _fila.append((tipo, id_)); _estado[chave] = {"estado": "fila"}; n += 1
        if n and _thread is None:
            _thread = threading.Thread(target=_trabalhar, daemon=True); _thread.start()
    return n


def todos_itens():
    return [("legenda", d["id"]) for d in legendas()] + [("elemento", i["id"]) for i in elementos()] + [("estilo", e["nome"]) for e in estilos()]


def estado_previa(tipo, id_):
    try:
        a = arquivo_previa(tipo, id_)
    except (KeyError, FileNotFoundError, StopIteration):
        return {"estado": "indisponivel"}
    if a.exists():
        pj = a.with_suffix(".jpg")
        return {"estado": "pronta", "url": f"/api/gs/estilos/previa/{a.name}", "poster": f"/api/gs/estilos/previa/{pj.name}" if pj.exists() else None}
    with _lock:
        return dict(_estado.get(f"{tipo}:{id_}", {"estado": "sem"}))


def biblioteca():
    est = [{**e, "previa": estado_previa("estilo", e["nome"])} for e in estilos()]
    leg = [{**d, "previa": estado_previa("legenda", d["id"])} for d in legendas()]
    ele = [{**i, "previa": estado_previa("elemento", i["id"])} for i in elementos()]
    with _lock:
        fila = len(_fila) + sum(1 for v in _estado.values() if v.get("estado") == "gerando")
    return {"estilos": est, "legendas": leg, "elementos": ele, "temas": [{"id": a, "rotulo": b} for a, b in TEMAS], "fila": fila,
            "amostra": "estilos/previas/amostra.mp4 (6,8 s do Thiago falando para a câmera)"}


def montar_estilo(dados, slugify):
    """Cria estilos/<slug>.json a partir da página: modelo de legenda (+ cor de destaque), elementos ligados, transição, formato preferido, temas."""
    nome = (dados.get("nome") or "").strip()
    slug = slugify(nome, 30)
    if not slug or slug == "padrao":
        raise ValueError("Escolha outro nome para o estilo.")
    if (EST / f"{slug}.json").exists() and not dados.get("substituir"):
        raise FileExistsError(f"Já existe o estilo {slug}.")
    if (EST / f"{slug}.json").exists() and _ler(EST / f"{slug}.json").get("casa"):
        raise ValueError("Esse estilo é da casa; use outro nome.")
    base = _ler(EST / "padrao.json")
    leg_id = dados.get("legenda") or "karaoke-classico"
    leg = dict(_ler(LEG / f"{leg_id}.json")["legenda"])
    cor = (dados.get("cor_destaque") or "").strip()
    if cor:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", cor):
            raise ValueError("cor_destaque deve ser #RRGGBB.")
        leg["cor_destaque"] = cor.upper()
    mont = {**base.get("montagem", {}), **DESLIGADO}
    ligados = [e for e in (dados.get("elementos") or []) if e in ELEMENTO_MONTAGEM]
    for e in ligados:
        mont.update(ELEMENTO_MONTAGEM[e])
    if dados.get("trilha"):
        mont["trilha"] = "auto"
    validos = {i["id"] for i in elementos()}
    if dados.get("transicao") in validos:
        mont["transicao"] = dados["transicao"]
    if dados.get("formato") in ("pip", "antes-depois", "dividido"):
        mont["formato_preferido"] = dados["formato"]
    pro = sum(1 for e in ligados if e in ("palavras-chave", "ritmo-4s", "barra-progresso", "sfx", "broll-janela", "broll-cheio", "gancho-palavra", "capitulos", "capitulos-auto"))
    mont["nivel"] = 3 if pro >= 4 else 2 if (pro >= 1 or "zoom-frase" in ligados or "clarao" in ligados) else 1
    temas = [t for t in (dados.get("temas") or []) if t in dict(TEMAS)]
    d = {"nome": slug, "legenda": leg, "montagem": mont, "saida": base.get("saida", {}), "descricao": (dados.get("descricao") or "").strip()[:300],
         "temas": temas, "casa": False, "montado": {"legenda": leg_id, "elementos": ligados, "transicao": mont.get("transicao"), "formato": mont.get("formato_preferido"),
                                                     "trilha": bool(dados.get("trilha")), "em": time.strftime("%Y-%m-%d %H:%M")}}
    (EST / f"{slug}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return d
