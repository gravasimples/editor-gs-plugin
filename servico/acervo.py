"""Busca no acervo por fala (01/11/2026): "onde o Thiago fala de supressão de ruído?" devolve o trecho e o instante.
Fontes, só leitura: (1) transcrições do GSI em `dados/transcricoes/` (índice `indice.json`; segmentos `{s, e, t}` de vídeos do YouTube e
Reels do Instagram, lives inclusive); (2) transcrições do próprio Editor GS (`saida/<slug>/*palavras*.json`, segmentos com início e fim e o
caminho do vídeo em `entrada/`). Sem modelo de linguagem: busca por palavras e frase, sem acento e sem caixa. "Virar corte" baixa só o
trecho do original (yt-dlp com `--download-sections`) ou usa o vídeo local, e abre um pedido no Clipador (fase EDITAR, reels-padrao)."""
import json, re, shutil, subprocess, unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_CACHE = {}  # arquivo -> (mtime, segmentos)
_PALAVRAS = {}  # arquivo -> [(inicio, palavra normalizada)]
MARGEM_S = 5.0
PARADAS = {"de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "em", "no", "na", "nos", "nas", "um", "uma", "que", "com", "pra", "para", "por", "se", "ao", "the", "ou", "mas", "ja", "eu", "ele", "ela", "voce", "isso", "esse", "essa", "nao", "sim", "mais", "muito", "bem", "tem", "ta", "ne"}


def _norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip()


def fontes_gsi(gsi: Path):
    """Transcrições do GSI com arquivo presente. Cada fonte: id `gsi:<plataforma>:<id>`, título, link, data, formato, duração."""
    idx = gsi / "dados" / "transcricoes" / "indice.json"
    try:
        d = json.loads(idx.read_text(encoding="utf-8"))
    except Exception:  # noqa
        return []
    out = []
    for v in (d.values() if isinstance(d, dict) else d):
        if not isinstance(v, dict) or v.get("status") != "transcrito" or not v.get("arquivo"):
            continue
        p = gsi / v["arquivo"]
        if not p.exists():
            continue
        out.append({"id": f"gsi:{v.get('plataforma')}:{v.get('id')}", "origem": "gsi", "plataforma": v.get("plataforma"), "titulo": (v.get("titulo") or v.get("id") or "")[:120], "url": v.get("url"),
                    "data": (v.get("data") or "")[:10], "formato": v.get("formato"), "duracao_s": v.get("duracao_s"), "arquivo": str(p), "video_local": None, "slug": None, "conversa": None})
    return out


def fontes_app(saida: Path, cache_textos: dict = None):
    """Transcrições do Editor GS: um `palavras*.json` por entrega (sem as versões `cortado`, que repetem o texto com tempos remapeados)."""
    out = []; por_slug = {v.get("slug"): v for v in (cache_textos or {}).values() if v.get("slug")}
    for p in sorted(Path(saida).glob("*/*palavras*.json")) if Path(saida).exists() else []:
        if "cortado" in p.name or p.parent.name.startswith("_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa
            continue
        if not isinstance(d.get("segmentos"), list):
            continue
        slug = p.parent.name; item = por_slug.get(slug) or {}
        video = d.get("arquivo"); video = video if video and Path(video).exists() else None
        out.append({"id": f"app:{slug}:{p.stem}", "origem": "app", "plataforma": "app", "titulo": (item.get("titulo") or slug)[:120], "url": None, "data": datetime.fromtimestamp(p.stat().st_mtime).date().isoformat(),
                    "formato": "entrega", "duracao_s": d.get("duracao_s"), "arquivo": str(p), "video_local": video, "slug": slug, "conversa": item.get("id"), "codigo": item.get("codigo")})
    return out


def fontes(gsi: Path, saida: Path, cache_textos: dict = None):
    return fontes_gsi(gsi) + fontes_app(saida, cache_textos)


def segmentos(fonte: dict):
    """Lista de (inicio, fim, texto) da fonte, em cache por mtime."""
    p = Path(fonte["arquivo"])
    try:
        mt = p.stat().st_mtime
    except OSError:
        return []
    c = _CACHE.get(str(p))
    if c and c[0] == mt:
        return c[1]
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa
        return []
    if not isinstance(d, dict):
        return []
    segs = []
    pal = []  # palavras com tempo (entregas do app; transcrições do GSI quando tiverem): instante exato do termo achado
    for w in (d.get("palavras") if isinstance(d.get("palavras"), list) else []):  # algumas entregas gravam "palavras": <contagem>
        if not isinstance(w, dict):
            continue
        ini = w.get("inicio", w.get("s")); t = w.get("palavra") or w.get("w") or w.get("t")
        if ini is not None and t:
            pal.append((float(ini), _norm(t)))
    _PALAVRAS[str(p)] = pal
    for s in (d.get("segmentos") if isinstance(d.get("segmentos"), list) else []):
        if not isinstance(s, dict):
            continue
        ini = s.get("s", s.get("inicio")); fim = s.get("e", s.get("fim")); t = (s.get("t") or s.get("texto") or "").strip()
        if ini is None or not t:
            continue
        segs.append((float(ini), float(fim) if fim is not None else float(ini), t))
    _CACHE[str(p)] = (mt, segs)
    return segs


def _contexto(segs, i, antes=1, depois=1, max_chars=260):
    a = " ".join(s[2] for s in segs[max(0, i - antes):i])[-max_chars:]; d = " ".join(s[2] for s in segs[i + 1:i + 1 + depois])[:max_chars]
    return a, d


def janela_corte(segs, i, alvo_s=40.0, max_s=75.0, min_s=15.0):
    """Sugestão de corte a partir do segmento achado: começa nele e segue até fechar uma frase depois de `alvo_s` (ou até `max_s`)."""
    ini = segs[i][0]; fim = segs[i][1]
    for s in segs[i + 1:]:
        if s[0] - ini >= max_s:
            break
        fim = s[1]
        if fim - ini >= alvo_s and re.search(r"[.!?]\s*$", s[2]):
            break
    if fim - ini < min_s:
        fim = min(ini + min_s, segs[-1][1])
    return round(max(0.0, ini - 0.3), 2), round(fim, 2)


def instante(fonte: dict, seg, tokens):
    """Instante do primeiro termo buscado dentro do segmento: exato pelas palavras com tempo; senão aproximado pela posição do texto no segmento."""
    ini, fim, texto = seg
    for t, w in _PALAVRAS.get(fonte["arquivo"], []):
        if ini - 0.05 <= t <= fim + 0.05 and any(tok in w for tok in tokens):
            return round(t, 2), "exato"
    tn = _norm(texto); pos = min((tn.find(tok) for tok in tokens if tok in tn), default=-1)
    if pos <= 0 or not tn:
        return round(ini, 2), "inicio_da_frase"
    return round(ini + (fim - ini) * pos / len(tn), 2), "aproximado"


def youtube_id(url: str):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|live/|embed/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def embed(fonte: dict, inicio: float, fim: float):
    """Player do YouTube já no trecho (sem cookies), para ouvir sem sair do app."""
    vid = youtube_id(fonte.get("url")) if fonte.get("plataforma") == "youtube" else None
    return f"https://www.youtube-nocookie.com/embed/{vid}?start={max(0, int(inicio) - 1)}&end={int(fim) + 2}&autoplay=1&rel=0" if vid else None


def link_instante(fonte: dict, s: float):
    u = fonte.get("url")
    if not u:
        return None
    if fonte.get("plataforma") == "youtube":
        return f"{u}{'&' if '?' in u else '?'}t={int(s)}s"
    return u


def buscar(q: str, lista: list, limite: int = 40, max_por_fonte: int = 3, origem: str = None):
    """Trechos onde a fala contém a frase (3 pontos), todas as palavras no mesmo segmento (2) ou no segmento mais o seguinte (1)."""
    qn = _norm(q); todos = [t for t in re.findall(r"\w+", qn) if len(t) > 1]
    tokens = [t for t in todos if t not in PARADAS] or todos  # "supressão de ruído" procura supressao + ruido
    if not tokens:
        return []
    out = []
    for f in lista:
        if origem and origem != "tudo" and (f["origem"] if origem in ("gsi", "app") else f["plataforma"]) != origem:
            continue
        segs = segmentos(f)
        if not segs:
            continue
        normed = [_norm(s[2]) for s in segs]
        achados = []
        for i, text in enumerate(normed):
            if qn in text:
                sc = 3
            elif all(t in text for t in tokens):
                sc = 2
            elif i + 1 < len(normed) and all(t in text + " " + normed[i + 1] for t in tokens) and not all(t in normed[i + 1] for t in tokens):
                sc = 1  # palavras repartidas entre este segmento e o seguinte (se o seguinte sozinho tem tudo, ele é que pontua)
            else:
                continue
            antes, depois = _contexto(segs, i); ji, jf = janela_corte(segs, i); t_exato, t_tipo = instante(f, segs[i], tokens)
            achados.append({"fonte": {k: f.get(k) for k in ("id", "origem", "plataforma", "titulo", "url", "data", "formato", "duracao_s", "slug", "conversa", "codigo")}, "video_local": bool(f.get("video_local")),
                            "inicio": segs[i][0], "fim": segs[i][1], "trecho": segs[i][2], "antes": antes, "depois": depois, "pontos": sc, "link": link_instante(f, t_exato),
                            "instante": t_exato, "instante_tipo": t_tipo, "embed": embed(f, t_exato, segs[i][1]),
                            "corte_sugerido": {"inicio": ji, "fim": jf}})
        achados.sort(key=lambda a: (-a["pontos"], a["inicio"]))
        out += achados[:max_por_fonte]
    out.sort(key=lambda a: (a["pontos"], a["fonte"]["data"] or ""), reverse=True)  # mais pontos, depois mais recente
    return out[:limite]


def resumo(lista: list):
    return {"total": len(lista), "gsi": sum(1 for f in lista if f["origem"] == "gsi"), "app": sum(1 for f in lista if f["origem"] == "app"),
            "youtube": sum(1 for f in lista if f["plataforma"] == "youtube"), "instagram": sum(1 for f in lista if f["plataforma"] == "instagram"),
            "com_video_local": sum(1 for f in lista if f.get("video_local"))}


class ErroAcervo(Exception):
    pass


def baixar_trecho(url: str, inicio: float, fim: float, pasta: Path, margem: float = MARGEM_S):
    """Baixa só a janela [inicio-margem, fim+margem] do original com yt-dlp (`--download-sections`, cortes em keyframe forçados) em
    pasta/origem.mp4. Devolve (caminho, deslocamento): o instante `inicio` do original fica em `deslocamento` s no arquivo."""
    from servico import referencias as _refs
    pasta = Path(pasta); alvo = pasta / "origem.mp4"
    a = max(0.0, float(inicio) - margem); b = float(fim) + margem; desloc = float(inicio) - a
    if alvo.exists() and alvo.stat().st_size > 1000:
        return alvo, desloc
    if not _refs.YTDLP.exists():
        raise ErroAcervo("yt-dlp não instalado no venv do editor-gs")
    pasta.mkdir(parents=True, exist_ok=True)
    cmd = [str(_refs.YTDLP), "--no-playlist", "--no-warnings", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4",
           "--download-sections", f"*{a:.2f}-{b:.2f}", "--force-keyframes-at-cuts", "-o", str(pasta / "origem.%(ext)s"), url]
    if _refs.NODE.exists():
        cmd[1:1] = ["--js-runtimes", f"node:{_refs.NODE}"]
    ck = _refs.cookies_para(url)
    if ck:
        cmd[1:1] = ["--cookies", str(ck)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        raise ErroAcervo("download do trecho passou de 15 min")
    if r.returncode != 0:
        raise ErroAcervo(((r.stderr or r.stdout).strip()[-300:]) or "yt-dlp falhou")
    achado = next((p for p in pasta.iterdir() if p.name.startswith("origem.") and p.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov")), None)
    if not achado:
        raise ErroAcervo("yt-dlp não gerou vídeo")
    if achado != alvo:
        shutil.move(str(achado), str(alvo))
    return alvo, desloc


def slug_corte(fonte: dict, inicio: float, titulo: str):
    from servico import referencias as _refs
    base = _refs._slug(titulo or fonte.get("titulo") or "corte", 36)
    return f"{datetime.now():%Y-%m-%d}-acervo-{base}-{int(inicio)}s"[:80]
