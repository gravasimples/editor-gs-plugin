"""Testes isolados de banco.py (buscar_material): Drive por índice falso em pasta temporária; Pexels/Pixabay por dublê de HTTP e de download; nada toca a rede
nem workspace/. Chaves de API vêm de variáveis de ambiente falsas."""
import json, os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import banco
from editor_video.util import ErroFerramenta

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory(prefix="editor-gs-banco-") as tmp:
    tmp = Path(tmp); mat = tmp / "materiais"; mat.mkdir(); bco = tmp / "banco"
    itens = [{"caminho": "takes/thiago-setup-webcam-logitech.mp4", "tipo": "video", "tamanho_mb": 40.2, "duracao_s": 31.0},
             {"caminho": "prints/obs-cena-fontes.png", "tipo": "imagem", "tamanho_mb": 0.4, "duracao_s": None},
             {"caminho": "fotos/thiago-mesa-estudio.jpg", "tipo": "imagem", "tamanho_mb": 2.1, "duracao_s": None},
             {"caminho": "trilhas/calma-piano.mp3", "tipo": "video", "tamanho_mb": 3.0, "duracao_s": 120.0},
             {"caminho": "docs/contrato.pdf", "tipo": "arquivo", "tamanho_mb": 0.1, "duracao_s": None}]
    (mat / "indice.json").write_text(json.dumps({"quando": "x", "n": len(itens), "itens": itens}), encoding="utf-8")

    # palavras e consulta
    pc = banco.palavras_chave("Sua webcam trava no OBS? Olha só o que resolve")
    check("webcam" in pc and "obs" in pc and "camera" in pc and "sua" not in pc and "que" not in pc, f"palavras do tema com sinônimos e sem vazias ({pc[:6]})")
    check(banco.consulta_ingles("gravar a tela e a webcam no OBS") == "recording screen webcam streaming software", f"consulta em inglês para os bancos ({banco.consulta_ingles('gravar a tela e a webcam no OBS')!r})")

    # Drive
    d = banco.buscar_drive("webcam travada no OBS", materiais=mat)
    cams = [i["caminho"] for i in d["itens"]]
    check(set(cams[:2]) == {"materiais/takes/thiago-setup-webcam-logitech.mp4", "materiais/prints/obs-cena-fontes.png"} and not any("contrato" in c for c in cams), f"Drive: take da webcam e print do OBS no topo, PDF fora ({cams})")
    check(d["itens"][0]["origem"] == "drive" and d["itens"][0]["licenca"] == "material da empresa" and d["itens"][0]["atribuicao"] is None, "item do Drive marcado como material da empresa")
    d2 = banco.buscar_drive("trilha calma", tipos=("audio",), materiais=mat)
    check([i["caminho"] for i in d2["itens"]] == ["materiais/trilhas/calma-piano.mp3"] and d2["itens"][0]["tipo"] == "audio", "áudio do Drive reconhecido pela extensão mesmo com tipo 'video' no índice")
    check(banco.buscar_drive("x", materiais=tmp / "nao")["aviso"].startswith("materiais/indice.json"), "sem índice avisa para sincronizar")

    # bancos sem chave → pendência, Drive continua
    for k in ("PEXELS_API_KEY", "PIXABAY_API_KEY"):
        os.environ.pop(k, None)
    banco.RAIZ = tmp  # .env inexistente aqui
    r = banco.buscar_material("webcam travada no OBS", materiais=mat, banco=bco)
    check(r["n_drive"] >= 2 and r["n_banco"] == 0 and len(r["pendencias"]) == 2 and "PEXELS_API_KEY" in r["pendencias"][0], f"sem chave: Drive responde e os bancos viram pendência ({r['pendencias']})")
    check("apoio" in r["regra"] and "Thiago" in r["regra"], "regra do manual vem na resposta")

    # bancos com chave (HTTP e download falsos)
    os.environ["PEXELS_API_KEY"] = "px-teste"; os.environ["PIXABAY_API_KEY"] = "pb-teste"
    chamadas = []
    def http_falso(url, headers=None, timeout=30):
        chamadas.append((url, headers or {}))
        if "api.pexels.com/videos" in url:
            return {"videos": [{"id": 101, "url": "https://pexels.com/v/101", "duration": 12, "user": {"name": "Ana"}, "video_files": [
                {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "https://x/h.mp4"}, {"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "https://x/v.mp4"},
                {"file_type": "video/mp4", "width": 720, "height": 1280, "link": "https://x/v720.mp4"}]}]}
        if "api.pexels.com/v1/search" in url:
            return {"photos": [{"id": 202, "url": "https://pexels.com/p/202", "photographer": "Bia", "width": 3000, "height": 4500, "src": {"large2x": "https://x/p.jpg"}}]}
        if "pixabay.com/api/videos" in url:
            return {"hits": [{"id": 303, "pageURL": "https://pixabay.com/v/303", "user": "Caio", "duration": 20, "videos": {"large": {"url": "https://x/pb.mp4", "width": 1080, "height": 1920}}}]}
        if "pixabay.com/api/?" in url:
            return {"hits": [{"id": 404, "pageURL": "https://pixabay.com/p/404", "user": "Dani", "imageWidth": 2000, "imageHeight": 3000, "largeImageURL": "https://x/pb.jpg"}]}
        raise AssertionError(url)
    baixados = []
    def down_falso(url, destino, headers=None, timeout=300):
        baixados.append(url); destino.parent.mkdir(parents=True, exist_ok=True); destino.write_bytes(b"\x00" * 100); return destino
    r = banco.buscar_material("webcam travada no OBS", n=2, _http=http_falso, _down=down_falso, materiais=mat, banco=bco)
    check(r["pendencias"] == [] and r["n_banco"] == 4 and sorted(x["origem"] for x in r["banco"]) == ["pexels", "pexels", "pixabay", "pixabay"], f"com chave: 2 vídeos + 2 fotos dos dois bancos ({[(x['origem'], x['tipo']) for x in r['banco']]})")
    px = next(x for x in r["banco"] if x["origem"] == "pexels" and x["tipo"] == "video")
    check(px["largura"] == 1080 and px["altura"] == 1920 and "https://x/v.mp4" in baixados, "Pexels: escolhe o arquivo vertical mais perto de 1080 para 9:16")
    check(any(h.get("Authorization") == "px-teste" for _, h in chamadas) and any("key=pb-teste" in u for u, _ in chamadas) and all("orientation=portrait" in u or "orientation=vertical" in u for u, _ in chamadas), "chaves e orientação nas chamadas")
    check(all("recording" not in u or "screen" in u for u, _ in chamadas) and all("query=webcam" in u or "q=webcam" in u for u, _ in chamadas), f"consulta em inglês nas URLs ({chamadas[0][0][:80]})")
    arq = bco / "pexels" / "101.mp4"; lic = bco / "pexels" / "101.licenca.json"
    check(arq.exists() and lic.exists() and json.loads(lic.read_text())["atribuicao"] == "Vídeo de Ana no Pexels" and "Pexels License" in json.loads(lic.read_text())["licenca"], "download vai para banco/<fonte>/<id> com licenca.json ao lado")
    check(px["caminho"].endswith("pexels/101.mp4") and "atribuicao" in px, f"item devolvido com caminho relativo e atribuição ({px['caminho']})")
    n0 = len(baixados); banco.buscar_material("webcam travada no OBS", n=2, _http=http_falso, _down=down_falso, materiais=mat, banco=bco)
    check(len(baixados) == n0, "segunda busca reaproveita o que já foi baixado")
    r2 = banco.buscar_material("webcam", n=1, orientacao="horizontal", tipos="video", fontes="pexels", baixar=False, _http=http_falso, _down=down_falso, materiais=mat, banco=bco)
    check(r2["n_banco"] == 1 and r2["banco"][0]["largura"] == 1920 and "download" in r2["banco"][0] and r2["drive"] == [], "horizontal sem baixar: só lista, arquivo 16:9")
    lb = banco.listar_banco(banco=bco)
    check(lb["n"] == 4 and all("licenca" in i and "caminho" in i for i in lb["itens"]), f"listar_banco mostra o que foi baixado com licença ({lb['n']})")
    def http_401(url, headers=None, timeout=30):
        import urllib.error; raise urllib.error.HTTPError(url, 401, "x", {}, None)
    r3 = banco.buscar_material("webcam", fontes="pexels", _http=http_401, _down=down_falso, materiais=mat, banco=bco)
    check(r3["n_banco"] == 0 and "401" in r3["pendencias"][0], "erro HTTP do banco vira pendência, sem derrubar a busca")
    try:
        banco.buscar_material("  ", materiais=mat, banco=bco); check(False, "tema vazio dá erro")
    except ErroFerramenta:
        check(True, "tema vazio dá erro")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
