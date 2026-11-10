"""Banco de material para o Editor GS.
1) Drive da empresa (espelho só leitura em workspace/materiais/, índice indice.json): acha takes, fotos, prints e trilhas que combinam com o tema.
2) Bancos gratuitos com API (chave no .env do projeto): Pexels (PEXELS_API_KEY; vídeos e fotos, Pexels License, sem atribuição obrigatória,
   link "Photos provided by Pexels" recomendado) e Pixabay (PIXABAY_API_KEY; vídeos e fotos, Content License, mostrar a origem, não hotlink,
   cache de 24 h). O que é baixado vai para workspace/banco/<fonte>/ com um <id>.licenca.json ao lado (origem, autor, URL, licença, atribuição).
Regra do manual da marca: banco de imagem é só APOIO (b-roll de contexto, fundo, trilha, efeito). Nunca no lugar de foto/print real do Thiago,
do setup ou do OBS, nem apresentado como se fosse. Sem chave, a busca nos bancos vira pendência e o Drive continua funcionando."""
import json, os, re, time, unicodedata, urllib.error, urllib.parse, urllib.request
from pathlib import Path
from .util import ErroFerramenta

RAIZ = Path(__file__).resolve().parents[3]
WORKSPACE = Path(os.environ.get("EDITOR_GS_WORKSPACE") or RAIZ / "workspace")
MATERIAIS = WORKSPACE / "materiais"
BANCO = WORKSPACE / "banco"
UA = "EditorGS/1.0 (+https://gravasimples.com.br)"
STOP = {"de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "um", "uma", "no", "na", "nos", "nas", "para", "pra", "com", "que", "em", "por", "como", "ou",
        "seu", "sua", "meu", "minha", "the", "and", "for", "video", "vídeo", "reels", "reel", "sobre", "sem", "mais", "menos", "ao", "à", "quem", "ja", "já",
        "mesmo", "mesma", "tempo", "vez", "vezes", "hoje", "agora", "aqui", "isso", "esse", "essa", "este", "esta", "ainda", "todo", "toda", "cada", "quando", "onde", "porque", "nao", "não", "bem", "muito", "pouco", "coisa", "jeito", "forma", "dica", "dicas", "passo", "passos"}
SINONIMOS = {"webcam": ["camera", "cam", "logitech", "c922", "c920"], "camera": ["webcam", "cam"], "microfone": ["mic", "audio", "voz"], "audio": ["microfone", "mic", "som"],
             "tela": ["print", "captura", "screen", "monitor"], "obs": ["obs", "cena", "fonte", "studio"], "aula": ["professor", "ensinar", "curso", "live"],
             "live": ["transmissao", "stream", "ao-vivo"], "celular": ["iphone", "android", "smartphone", "phone"], "luz": ["ring", "iluminacao", "lampada", "led"],
             "setup": ["mesa", "estudio", "bastidor"], "gravar": ["gravacao", "take", "rec"], "notebook": ["laptop", "computador", "pc"]}
TRADUCAO = {"webcam": "webcam", "camera": "camera", "microfone": "microphone", "audio": "audio", "tela": "screen", "aula": "online class", "professor": "teacher",
            "gravar": "recording", "gravacao": "recording", "celular": "smartphone", "luz": "ring light", "setup": "desk setup", "estudio": "studio", "live": "livestream",
            "notebook": "laptop", "computador": "computer", "mesa": "desk", "teclado": "keyboard", "fone": "headphones", "ensinar": "teaching", "curso": "online course",
            "video": "video", "editar": "video editing", "roteiro": "script writing", "obs": "streaming software"}
EXT_VIDEO = {".mp4", ".mov", ".mkv", ".webm"}
EXT_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
EXT_IMG = {".png", ".jpg", ".jpeg", ".webp"}


def _norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def palavras_chave(tema):
    """Palavras do tema (sem acento, sem palavras vazias, 3+ letras) mais sinônimos conhecidos."""
    base = [w for w in _norm(tema).split() if len(w) >= 3 and w not in STOP]
    extra = []
    for w in base:
        extra += SINONIMOS.get(w, [])
    vistos, out = set(), []
    for w in base + extra:
        if w not in vistos:
            vistos.add(w); out.append(w)
    return out


def consulta_ingles(tema):
    """Consulta curta em inglês para os bancos (Pexels/Pixabay indexam em inglês): traduz as palavras conhecidas, mantém as outras."""
    partes = [TRADUCAO.get(w, w) for w in palavras_chave(tema) if w not in {s for v in SINONIMOS.values() for s in v} or w in TRADUCAO]
    vistos, out = set(), []
    for p in partes:
        if p not in vistos:
            vistos.add(p); out.append(p)
    return " ".join(out[:4]) or _norm(tema)[:60]


def _chave(nome):
    k = os.environ.get(nome, "").strip().strip('"')
    if not k:
        env = RAIZ / ".env"
        if env.exists():
            for l in env.read_text(encoding="utf-8").splitlines():
                if l.startswith(nome + "="):
                    k = l.split("=", 1)[1].strip().strip('"')
    return k or None


def _tipo_de(p: Path):
    e = p.suffix.lower()
    return "video" if e in EXT_VIDEO else "audio" if e in EXT_AUDIO else "imagem" if e in EXT_IMG else "arquivo"


# --- Drive (espelho) --------------------------------------------------------------------------------
def buscar_drive(tema, tipos=("video", "imagem", "audio"), n=8, materiais: Path | None = None):
    """Itens de materiais/ cujo caminho (pasta + nome) casa com as palavras do tema. Pontua por palavra encontrada; pasta conta mais que nome."""
    pasta = materiais or MATERIAIS; idx = pasta / "indice.json"
    if not idx.exists():
        return {"itens": [], "aviso": "materiais/indice.json não existe: sincronize a Biblioteca (Drive) no app."}
    try:
        itens = json.loads(idx.read_text(encoding="utf-8")).get("itens", [])
    except Exception:
        return {"itens": [], "aviso": "indice.json ilegível"}
    chaves = palavras_chave(tema); base = {w for w in _norm(tema).split() if len(w) >= 3 and w not in STOP}; out = []
    for it in itens:
        cam = it.get("caminho", ""); tipo = _tipo_de(Path(cam)) if it.get("tipo") in (None, "arquivo", "video") else it["tipo"]
        if tipo not in tipos:
            continue
        texto = _norm(cam); pastas = _norm(cam.rsplit("/", 1)[0]) if "/" in cam else ""
        # palavra do próprio tema vale mais que sinônimo; pasta vale mais que nome do arquivo
        pontos = sum(((3 if w in base else 1) + (1 if w in pastas else 0)) for w in chaves if w in texto)
        if pontos:
            out.append({"origem": "drive", "caminho": f"materiais/{cam}", "tipo": tipo, "duracao_s": it.get("duracao_s"), "tamanho_mb": it.get("tamanho_mb"), "pontos": pontos,
                        "licenca": "material da empresa", "atribuicao": None})
    out.sort(key=lambda x: (-x["pontos"], x["caminho"]))
    return {"itens": out[:n], "total": len(out), "palavras": chaves}


# --- bancos gratuitos --------------------------------------------------------------------------------
def _http_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _download(url, destino: Path, headers=None, timeout=300):
    destino.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(destino, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    return destino


def _melhor_arquivo_pexels(video, vertical):
    arqs = [a for a in video.get("video_files", []) if a.get("file_type") == "video/mp4" and a.get("width") and a.get("height")]
    if not arqs:
        return None
    def nota(a):
        h = a["height"]; w = a["width"]; ok = (h > w) == vertical
        return (ok, -abs(min(w, h) - 1080))
    return sorted(arqs, key=nota, reverse=True)[0]


def buscar_pexels(consulta, tipos, n, vertical, _http=None):
    k = _chave("PEXELS_API_KEY")
    if not k:
        return {"itens": [], "pendencia": "PEXELS_API_KEY ausente no .env do Editor GS (chave gratuita em pexels.com/api)."}
    http = _http or _http_json; hdr = {"Authorization": k}; ori = "portrait" if vertical else "landscape"; out = []
    try:
        if "video" in tipos:
            r = http(f"https://api.pexels.com/videos/search?query={urllib.parse.quote(consulta)}&orientation={ori}&per_page={n}", hdr)
            for v in r.get("videos", []):
                a = _melhor_arquivo_pexels(v, vertical)
                if a:
                    out.append({"origem": "pexels", "tipo": "video", "id": str(v["id"]), "url": v.get("url"), "autor": (v.get("user") or {}).get("name"), "duracao_s": v.get("duration"),
                                "largura": a["width"], "altura": a["height"], "download": a["link"], "ext": ".mp4", "licenca": "Pexels License (uso comercial, sem atribuição obrigatória)",
                                "atribuicao": f"Vídeo de {(v.get('user') or {}).get('name') or 'autor'} no Pexels"})
        if "imagem" in tipos:
            r = http(f"https://api.pexels.com/v1/search?query={urllib.parse.quote(consulta)}&orientation={ori}&per_page={n}", hdr)
            for p in r.get("photos", []):
                src = p.get("src") or {}
                out.append({"origem": "pexels", "tipo": "imagem", "id": str(p["id"]), "url": p.get("url"), "autor": p.get("photographer"), "largura": p.get("width"), "altura": p.get("height"),
                            "download": src.get("large2x") or src.get("original"), "ext": ".jpg", "licenca": "Pexels License (uso comercial, sem atribuição obrigatória)",
                            "atribuicao": f"Foto de {p.get('photographer') or 'autor'} no Pexels"})
    except urllib.error.HTTPError as e:
        return {"itens": out, "pendencia": f"Pexels respondeu {e.code} (chave inválida ou limite de 200/h)."}
    except Exception as e:  # noqa
        return {"itens": out, "pendencia": f"Pexels indisponível: {type(e).__name__}"}
    return {"itens": out}


def buscar_pixabay(consulta, tipos, n, vertical, _http=None):
    k = _chave("PIXABAY_API_KEY")
    if not k:
        return {"itens": [], "pendencia": "PIXABAY_API_KEY ausente no .env do Editor GS (chave gratuita em pixabay.com/api/docs)."}
    http = _http or _http_json; ori = "vertical" if vertical else "horizontal"; out = []; q = urllib.parse.quote(consulta)
    try:
        if "video" in tipos:
            r = http(f"https://pixabay.com/api/videos/?key={k}&q={q}&orientation={ori}&per_page={max(3, n)}&safesearch=true")
            for v in r.get("hits", []):
                vs = v.get("videos") or {}; a = vs.get("large") or vs.get("medium") or vs.get("small")
                if a and a.get("url"):
                    out.append({"origem": "pixabay", "tipo": "video", "id": str(v["id"]), "url": v.get("pageURL"), "autor": v.get("user"), "duracao_s": v.get("duration"),
                                "largura": a.get("width"), "altura": a.get("height"), "download": a["url"], "ext": ".mp4", "licenca": "Pixabay Content License (uso comercial; mostrar a origem)",
                                "atribuicao": f"Vídeo de {v.get('user') or 'autor'} no Pixabay"})
        if "imagem" in tipos:
            r = http(f"https://pixabay.com/api/?key={k}&q={q}&orientation={ori}&image_type=photo&per_page={max(3, n)}&safesearch=true")
            for p in r.get("hits", []):
                out.append({"origem": "pixabay", "tipo": "imagem", "id": str(p["id"]), "url": p.get("pageURL"), "autor": p.get("user"), "largura": p.get("imageWidth"), "altura": p.get("imageHeight"),
                            "download": p.get("largeImageURL") or p.get("webformatURL"), "ext": ".jpg", "licenca": "Pixabay Content License (uso comercial; mostrar a origem)",
                            "atribuicao": f"Foto de {p.get('user') or 'autor'} no Pixabay"})
    except urllib.error.HTTPError as e:
        return {"itens": out, "pendencia": f"Pixabay respondeu {e.code} (chave inválida ou limite de 100/min)."}
    except Exception as e:  # noqa
        return {"itens": out, "pendencia": f"Pixabay indisponível: {type(e).__name__}"}
    return {"itens": out}


def baixar_item(item, banco: Path | None = None, _down=None):
    """Baixa o item para banco/<fonte>/<id><ext> e grava <id>.licenca.json ao lado. Se já existe, reaproveita."""
    pasta = (banco or BANCO) / item["origem"]; destino = pasta / f"{item['id']}{item['ext']}"; lic = pasta / f"{item['id']}.licenca.json"
    if not destino.exists():
        (_down or _download)(item["download"], destino)
    lic.write_text(json.dumps({k: item.get(k) for k in ("origem", "tipo", "id", "url", "autor", "licenca", "atribuicao", "largura", "altura", "duracao_s")} | {"baixado_em": time.strftime("%Y-%m-%dT%H:%M:%S")},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        rel = destino.relative_to(WORKSPACE).as_posix()
    except ValueError:
        rel = destino.as_posix()  # fora do workspace: caminho absoluto, sempre com /
    return {**{k: item.get(k) for k in ("origem", "tipo", "id", "url", "autor", "licenca", "atribuicao", "largura", "altura", "duracao_s")}, "caminho": rel, "licenca_json": str(lic)}


def buscar_material(tema, tipos="video,imagem", fontes="drive,pexels,pixabay", n=5, orientacao="vertical", baixar=True, _http=None, _down=None, materiais=None, banco=None):
    """Material para um tema: primeiro o Drive da empresa (real), depois bancos gratuitos (apoio). Devolve itens do Drive, itens baixados do banco com licença,
    pendências (chave ausente, limite) e a regra de uso."""
    tema = (tema or "").strip()
    if not tema:
        raise ErroFerramenta("Informe o tema.")
    tp = tuple(t.strip() for t in (tipos or "video,imagem").split(",") if t.strip()); fs = [f.strip().lower() for f in (fontes or "drive").split(",") if f.strip()]
    n = max(1, min(int(n or 5), 15)); vertical = (orientacao or "vertical").lower().startswith("v")
    out = {"tema": tema, "palavras": palavras_chave(tema), "consulta_banco": consulta_ingles(tema), "drive": [], "banco": [], "pendencias": [],
           "regra": "Drive primeiro (material real). Banco de imagem só como apoio: b-roll de contexto, fundo, trilha, efeito. Nunca no lugar de foto/print real do Thiago, "
                    "do setup ou do OBS, nem apresentado como se fosse. Citar a origem (atribuicao) no ## Resumo e anotar em ## Pendências quando a cena merecer material real."}
    if "drive" in fs:
        d = buscar_drive(tema, tp, n, materiais=materiais); out["drive"] = d["itens"]
        if d.get("aviso"):
            out["pendencias"].append(d["aviso"])
    candidatos = []
    if "pexels" in fs:
        r = buscar_pexels(out["consulta_banco"], tp, n, vertical, _http=_http); candidatos += r["itens"]
        if r.get("pendencia"):
            out["pendencias"].append(r["pendencia"])
    if "pixabay" in fs:
        r = buscar_pixabay(out["consulta_banco"], tp, n, vertical, _http=_http); candidatos += r["itens"]
        if r.get("pendencia"):
            out["pendencias"].append(r["pendencia"])
    # intercala fontes e limita a n por tipo
    por_tipo = {}
    for c in candidatos:
        por_tipo.setdefault(c["tipo"], []).append(c)
    escolhidos = []
    for t, lst in por_tipo.items():
        escolhidos += lst[:n]
    for c in escolhidos:
        if baixar:
            try:
                out["banco"].append(baixar_item(c, banco=banco, _down=_down))
            except Exception as e:  # noqa
                out["pendencias"].append(f"{c['origem']} {c['id']}: download falhou ({type(e).__name__})")
        else:
            out["banco"].append({k: c.get(k) for k in ("origem", "tipo", "id", "url", "autor", "licenca", "atribuicao", "largura", "altura", "duracao_s", "download")})
    out["n_drive"] = len(out["drive"]); out["n_banco"] = len(out["banco"])
    return out


def listar_banco(banco: Path | None = None):
    """O que já foi baixado em workspace/banco/, com a licença de cada arquivo."""
    pasta = banco or BANCO; out = []
    if not pasta.exists():
        return {"itens": [], "n": 0, "pasta": str(pasta)}
    for lic in sorted(pasta.rglob("*.licenca.json")):
        try:
            d = json.loads(lic.read_text(encoding="utf-8"))
        except Exception:
            continue
        arq = next((p for p in lic.parent.glob(lic.name.replace(".licenca.json", ".*")) if p != lic), None)
        if arq:
            try:
                rel = arq.relative_to(WORKSPACE).as_posix()
            except ValueError:
                rel = arq.as_posix()
            out.append({**d, "caminho": rel})
    return {"itens": out, "n": len(out), "pasta": str(pasta)}
