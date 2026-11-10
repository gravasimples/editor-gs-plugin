"""Garimpo de referências (09/11/2026): candidatos com desempenho relativo, decisão humana, aprovado vira ficha. YouTube API falsa, download falso,
Gemini falso, pasta temporária. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_garimpo.py"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-garimpo-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws"); os.environ["EDITOR_GS_MAQUINA"] = str(tmp / "maq"); os.environ["GEMINI_API_KEY"] = "falsa"
os.environ["EDITOR_GS_GSI"] = str(tmp / "gsi")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import garimpo as G, repertorio as R
from editor_video.util import FFMPEG, ErroFerramenta
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

check(G._id("https://www.tiktok.com/@creatorcarolshop/video/769") == "tt-769", "id do TikTok não confunde '…shop/video' com post do Instagram")
check(G._id("https://www.instagram.com/reel/AbC_1/") == "ig-AbC_1" and G._id("https://youtu.be/YPBZsH-FP-s") == "yt-YPBZsH-FP-s", "ids de Reel e YouTube")

# candidatos do vidIQ
s = G.salvar_candidatos([{"url": "https://www.instagram.com/reel/AAA", "criador": "@a", "views": 100000, "mediana": 2000, "outlier": 50.0},
                         {"url": "https://www.instagram.com/reel/BBB", "criador": "@b", "views": 30000, "mediana": 3000, "outlier": 10.0},
                         {"criador": "sem link"}], "vidiq", "teste")
check(s["novos"] == ["ig-AAA", "ig-BBB"], "salva candidatos com link e ignora sem link")
s2 = G.salvar_candidatos([{"url": "https://www.instagram.com/reel/AAA/", "views": 120000}], "vidiq")
lc = G.listar_candidatos()
check(s2["ja_tinha"] == ["ig-AAA"] and lc["n"] == 2 and lc["candidatos"][0]["desempenho"]["views"] == 120000, "mesma URL atualiza números sem duplicar")
check(lc["candidatos"][0]["id"] == "ig-AAA", "lista do maior outlier ao menor")
check(str(G._arq()).startswith(str(tmp)), "candidatos ficam na pasta temporária")

# decisão humana
try:
    G.decidir_candidato("ig-AAA", "aprovar", por="", formato="fala"); ok = False
except ErroFerramenta:
    ok = True
check(ok, "sem 'por' a decisão é recusada (decisão é humana)")
check("erro" in servidor.decidir_candidato_referencia("ig-AAA", "aprovar", "Raphael", formato="inventado"), "formato inválido devolve erro")
check(G.decidir_candidato("ig-BBB", "rejeitar", por="Raphael", motivo="fora do nicho")["estado"] == "rejeitado", "rejeitar só marca")

v = tmp / "ref.mp4"
subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x568:d=2", "-f", "lavfi", "-i", "sine=f=440:d=2", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(v)], check=True)
def req_falso(metodo, url, dados=None, headers=None, raw=False):
    if ":generateContent" in url:
        r = {"decupagem": [{"inicio": 0, "fim": 2, "layout": "cheio", "enquadramento": "medio", "transicao": "punch", "grafismo": {"tipo": "nenhum"}}], "receita": ["x"]}
        return 200, {}, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(r)}]}}]}).encode()
    if "upload/v1beta/files" in url:
        return 200, {"X-Goog-Upload-URL": "https://up"}, b"{}"
    if url == "https://up":
        return 200, {}, json.dumps({"file": {"name": "files/x", "uri": "https://arq"}}).encode()
    return 200, {}, json.dumps({"state": "ACTIVE"}).encode()
d = G.decidir_candidato("ig-AAA", "aprovar", por="Raphael", formato="fala", _baixar_=lambda url, cid: v, _req_=req_falso)
f = R.ficha(d["ficha"])
check(d["estado"] == "aprovado" and f["formato"] == "fala" and f["desempenho"]["outlier"] == 50.0 and f["desempenho"]["fonte_dados"] == "vidiq", "aprovado vira ficha com o desempenho da fonte")
check(f["fonte"] == "https://www.instagram.com/reel/AAA" and f["direitos"] == "so_referencia" and f["decupagem"], "ficha guarda link, só referência e decupagem")
c = next(x for x in G.listar_candidatos("")["candidatos"] if x["id"] == "ig-AAA")
check(c["decidido_por"] == "Raphael" and c["ficha"] == d["ficha"], "candidato registra quem decidiu e a ficha criada")
def baixa_falha(url, cid):
    raise ErroFerramenta("Instagram pediu login")
G.salvar_candidatos([{"url": "https://www.instagram.com/reel/CCC"}], "vidiq")
try:
    G.decidir_candidato("ig-CCC", "aprovar", por="Raphael", formato="fala", _baixar_=baixa_falha)
except ErroFerramenta:
    pass
check(next(x for x in G.listar_candidatos("erro")["candidatos"])["id"] == "ig-CCC", "falha no download marca 'erro' com o motivo")

# YouTube API falsa: canal A com mediana 1000 (vídeo de 50 mil = outlier 50), canal B mediana 40 mil (não passa), vídeo em inglês fora
def get_falso(rota, p):
    if rota == "search":
        return {"items": [{"id": {"videoId": i}} for i in ("v1", "v2", "v3", "v4")]}
    if rota == "videos" and "snippet" in p["part"]:
        sn = lambda c, t: {"channelId": c, "channelTitle": c, "title": t, "publishedAt": "2026-10-01T00:00:00Z", "description": ""}
        return {"items": [{"id": "v1", "snippet": sn("A", "Como configurar o OBS"), "statistics": {"viewCount": "50000"}},
                          {"id": "v2", "snippet": sn("B", "Como gravar aula"), "statistics": {"viewCount": "60000"}},
                          {"id": "v3", "snippet": sn("A", "How to record in OBS"), "statistics": {"viewCount": "90000"}},
                          {"id": "v4", "snippet": sn("C", "Como gravar sua aula"), "statistics": {"viewCount": "3000"}}]}
    if rota == "channels":
        return {"items": [{"id": c, "contentDetails": {"relatedPlaylists": {"uploads": "U" + c}}, "statistics": {"subscriberCount": "5000"}} for c in ("A", "B", "C")]}
    if rota == "playlistItems":
        return {"items": [{"contentDetails": {"videoId": f"{p['playlistId']}{k}"}} for k in range(6)]}
    if rota == "videos":
        base = {"UA": 1000, "UB": 40000, "UC": 100}[p["id"][:2]]
        return {"items": [{"statistics": {"viewCount": str(base)}} for _ in p["id"].split(",")]}
y = G.buscar_youtube("obs", _get_=get_falso)
urls = [c["url"] for c in y["candidatos"]]
check(urls == ["https://www.youtube.com/shorts/v1"] and y["candidatos"][0]["outlier"] == 50.0 and y["candidatos"][0]["mediana"] == 1000, "YouTube: só outlier real, PT-BR e com views mínimas")
check(any(x["id"] == "yt-v1" and x["fonte"] == "youtube_api" for x in G.listar_candidatos()["candidatos"]), "achado do YouTube vira candidato aguardando")
check("erro" in servidor.buscar_referencias_youtube("obs"), "sem chave do YouTube devolve erro claro (GSI de teste sem .env)")
check(servidor.listar_candidatos_referencia("")["n"] >= 4, "MCP listar_candidatos_referencia")

print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
