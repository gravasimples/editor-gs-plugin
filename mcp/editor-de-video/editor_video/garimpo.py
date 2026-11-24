"""Garimpo de referências (09/11/2026): achar → escolher → decupar. Candidatos de fontes que medem desempenho relativo ao próprio perfil
(outlier = views ÷ mediana do criador) ficam em workspace/repertorio/candidatos.json esperando decisão humana; aprovado vira ficha do
repertório (yt-dlp baixa o vídeo público, `repertorio.adicionar_referencia` mede e decupa).
Fontes: YouTube Data API (grátis, chave YOUTUBE_API_KEY do .env do GSI, só leitura) e o que o Claude Code trouxer do vidIQ (150 créditos
grátis por mês, 5 por busca: Reels e TikTok outliers). Nada entra no repertório sem `decidir_candidato(..., por=<humano>)`.
Referência é só estudo: nunca reutilizar imagem, áudio ou texto dela."""
import json, os, re, statistics, subprocess, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .util import ler_json, salvar_json, ErroFerramenta
from . import repertorio

GSI = Path(os.environ.get("EDITOR_GS_GSI", "/mnt/c/Users/rapha/Desktop/Claude/Claude Code/grava-simples-intelligence"))
YTDLP = Path.home() / ".venvs" / "editor-gs" / "bin" / "yt-dlp"
API = "https://www.googleapis.com/youtube/v3/"
ESTADOS = ("aguardando", "aprovado", "rejeitado", "erro")


def _arq():
    return repertorio.WORKSPACE / "repertorio" / "candidatos.json"


def _videos_dir():
    return repertorio.WORKSPACE / "repertorio" / "_videos"


def _ler():
    a = _arq()
    return ler_json(a) if a.exists() else {"candidatos": []}


def _id(url):
    u = url.rstrip("/")
    m = re.search(r"instagram\.com/(?:reels?|p)/([\w-]+)", u) or re.search(r"(?:shorts/|v=|youtu\.be/)([\w-]+)", u) or re.search(r"video/(\d+)", u)
    plat = "ig" if "instagram" in u else "yt" if "youtu" in u else "tt" if "tiktok" in u else "web"
    return f"{plat}-{m.group(1) if m else re.sub(r'[^a-z0-9]+', '-', u.lower())[-40:]}"


def salvar_candidatos(itens, fonte, busca=""):
    """itens: [{url, criador, titulo, views, mediana, outlier, gancho, formato_visto, notas, publicado}] (o que a fonte informar; nada é inventado).
    Junta com os que já existem pela URL (mantém a decisão humana já tomada). Devolve {novos, ja_tinha}."""
    base = _ler(); por_id = {c["id"]: c for c in base["candidatos"]}
    novos, ja = [], []
    for it in itens:
        if not it.get("url"):
            continue
        cid = _id(it["url"])
        if cid in por_id:
            c = por_id[cid]
            c["desempenho"] = {**c.get("desempenho", {}), **{k: it[k] for k in ("views", "mediana", "outlier") if it.get(k) is not None}}
            ja.append(cid); continue
        c = {"id": cid, "url": it["url"], "criador": it.get("criador", ""), "titulo": (it.get("titulo") or "")[:160], "fonte": fonte, "busca": busca,
             "desempenho": {k: it[k] for k in ("views", "mediana", "outlier", "seguidores") if it.get(k) is not None},
             "gancho": it.get("gancho", ""), "formato_visto": it.get("formato_visto", ""), "notas": it.get("notas", ""), "publicado": it.get("publicado", ""),
             "estado": "aguardando", "achado_em": datetime.now().isoformat(timespec="seconds")}
        base["candidatos"].append(c); por_id[cid] = c; novos.append(cid)
    salvar_json(_arq(), base)
    return {"novos": novos, "ja_tinha": ja, "arquivo": str(_arq())}


def listar_candidatos(estado="aguardando"):
    cs = [c for c in _ler()["candidatos"] if not estado or c["estado"] == estado]
    cs.sort(key=lambda c: -(c.get("desempenho", {}).get("outlier") or 0))
    return {"n": len(cs), "candidatos": cs}


def _baixar(url, cid):
    pasta = _videos_dir(); pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / f"{cid}.mp4"
    if alvo.exists() and alvo.stat().st_size > 1000:
        return alvo
    if not YTDLP.exists():
        raise ErroFerramenta("yt-dlp não instalado no venv do editor-gs")
    cmd = [str(YTDLP), "--no-playlist", "--no-warnings", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4",
           "-o", str(pasta / f"{cid}.%(ext)s"), url]
    ck = Path(__file__).resolve().parents[3] / ".cookies" / ("instagram.txt" if "instagram" in url else "youtube.txt")
    if ck.exists() and ck.stat().st_size > 0:
        cmd[1:1] = ["--cookies", str(ck)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not alvo.exists():
        raise ErroFerramenta(((r.stderr or r.stdout).strip()[-300:] or "yt-dlp falhou") + (" | Instagram pediu login: exporte os cookies para .cookies/instagram.txt" if "instagram" in url and "login" in (r.stderr or "").lower() else ""))
    return alvo


def decidir_candidato(id_, decisao, por, formato="", motivo="", decupar=True, _baixar_=None, _req_=None):
    """decisao: aprovar | rejeitar. `por` = quem decidiu (humano; obrigatório). Aprovar baixa o vídeo público e cria a ficha (formato do repertório)."""
    if not str(por).strip():
        raise ErroFerramenta("decisão de referência é humana: informe por=<quem decidiu>")
    if decisao not in ("aprovar", "rejeitar"):
        raise ErroFerramenta("decisao deve ser aprovar ou rejeitar")
    base = _ler(); c = next((x for x in base["candidatos"] if x["id"] == id_), None)
    if not c:
        raise ErroFerramenta(f"candidato não encontrado: {id_}")
    c["decidido_por"], c["decidido_em"], c["motivo"] = por, datetime.now().isoformat(timespec="seconds"), motivo
    if decisao == "rejeitar":
        c["estado"] = "rejeitado"; salvar_json(_arq(), base)
        return {"id": id_, "estado": "rejeitado"}
    if formato not in repertorio.FORMATOS:
        raise ErroFerramenta(f"para aprovar, formato deve ser um de: {', '.join(repertorio.FORMATOS)}")
    try:
        v = (_baixar_ or _baixar)(c["url"], id_)
        titulo = f"{c.get('criador') or c['fonte']} {c.get('titulo') or id_}"[:70]
        r = repertorio.adicionar_referencia(str(v), titulo, formato, fonte=c["url"], desempenho={**c.get("desempenho", {}), "fonte_dados": c["fonte"], "publicado": c.get("publicado")},
                                            decupar=decupar, _req_=_req_)
        c.update(estado="aprovado", ficha=r["id"], formato=formato)
    except ErroFerramenta as e:
        c.update(estado="erro", erro=str(e)[:400]); salvar_json(_arq(), base)
        raise
    salvar_json(_arq(), base)
    return {"id": id_, "estado": "aprovado", "ficha": c["ficha"], "decupagem": r.get("decupagem")}


# --- YouTube Data API (grátis, ~100 unidades por busca + ~2 por canal; cota diária de 10 mil) ---------------------------------------
def _chave_youtube():
    k = os.environ.get("YOUTUBE_API_KEY", "").strip().strip('"')
    env = GSI / ".env"
    if not k and env.exists():
        for l in env.read_text(encoding="utf-8").splitlines():
            if l.startswith("YOUTUBE_API_KEY="):
                k = l.split("=", 1)[1].strip().strip('"')
    return k or None


def _get(rota, _get_=None, **params):
    if _get_:
        return _get_(rota, params)
    url = API + rota + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


PT = re.compile(r"\b(como|para|você|voce|não|nao|seu|sua|meu|minha|grava\w*|aula|dica|configur\w*)\b|ção|ões|ã", re.I)


def _pt(sn):
    lang = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "").lower()
    return lang.startswith("pt") if lang else bool(PT.search(sn.get("title", "") + " " + sn.get("description", "")[:200]))


def buscar_youtube(termos, dias=120, n=15, min_outlier=3.0, curtos=True, min_views=10000, _get_=None):
    """Shorts (ou vídeos) em PT-BR sobre os termos; para cada canal, mediana das views dos 15 envios mais recentes; fica quem passou de
    min_outlier × a mediana e tem pelo menos min_views (canal minúsculo dá outlier enganoso); só PT-BR. Salva como candidatos (fonte youtube_api) e devolve a lista."""
    chave = _chave_youtube() if not _get_ else "teste"
    if not chave:
        raise ErroFerramenta("sem YOUTUBE_API_KEY (procurei no ambiente e no .env do GSI)")
    depois = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    p = {"part": "snippet", "q": termos, "type": "video", "maxResults": min(50, n * 3), "regionCode": "BR", "relevanceLanguage": "pt",
         "publishedAfter": depois, "order": "viewCount", "key": chave}
    if curtos:
        p["videoDuration"] = "short"
    ids = [i["id"]["videoId"] for i in _get("search", _get_, **p).get("items", []) if i.get("id", {}).get("videoId")]
    if not ids:
        return {"n": 0, "candidatos": []}
    vids = _get("videos", _get_, part="snippet,statistics", id=",".join(ids), key=chave).get("items", [])
    canais = sorted({v["snippet"]["channelId"] for v in vids})
    ch = {c["id"]: c for c in _get("channels", _get_, part="contentDetails,statistics", id=",".join(canais), key=chave).get("items", [])}
    medianas = {}
    for cid, c in ch.items():
        up = c["contentDetails"]["relatedPlaylists"]["uploads"]
        rec = [i["contentDetails"]["videoId"] for i in _get("playlistItems", _get_, part="contentDetails", playlistId=up, maxResults=15, key=chave).get("items", [])]
        vs = [int(x["statistics"].get("viewCount", 0)) for x in _get("videos", _get_, part="statistics", id=",".join(rec), key=chave).get("items", [])] if rec else []
        medianas[cid] = statistics.median(vs) if len(vs) >= 5 else None
    itens = []
    for v in vids:
        views = int(v["statistics"].get("viewCount", 0)); med = medianas.get(v["snippet"]["channelId"])
        if not med or views / med < min_outlier or views < min_views or not _pt(v["snippet"]):
            continue
        sn = v["snippet"]; seg = ch.get(sn["channelId"], {}).get("statistics", {}).get("subscriberCount")
        itens.append({"url": f"https://www.youtube.com/shorts/{v['id']}" if curtos else f"https://www.youtube.com/watch?v={v['id']}", "criador": sn["channelTitle"],
                      "titulo": sn["title"], "views": views, "mediana": round(med), "outlier": round(views / med, 1), "publicado": sn["publishedAt"][:10],
                      **({"seguidores": int(seg)} if seg else {})})
    itens.sort(key=lambda x: -x["outlier"]); itens = itens[:n]
    s = salvar_candidatos(itens, "youtube_api", termos)
    return {"n": len(itens), "novos": s["novos"], "candidatos": itens}
