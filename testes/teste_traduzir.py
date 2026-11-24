"""Teste isolado de revisao.traduzir_srt com o Gemini por dublê (sem rede): mantém tempos e quantidade, marca destaque, rejeita contagem errada."""
import json, os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import revisao
from editor_video.util import ErroFerramenta

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

with tempfile.TemporaryDirectory(prefix="editor-gs-trad-") as tmp:
    tmp = Path(tmp); os.environ["GEMINI_API_KEY"] = "teste"
    (tmp / "pt.srt").write_text("1\n00:00:00,500 --> 00:00:02,000\nLiga o modo estúdio\n\n2\n00:00:02,000 --> 00:00:03,500\nno OBS, ó.\n\n3\n00:00:04,000 --> 00:00:05,000\nPronto, tá gravando.\n", encoding="utf-8")
    prompts = []
    def req_falso(metodo, url, dados=None, headers=None, raw=False):
        prompts.append(dados["contents"][0]["parts"][0]["text"])
        resp = {"blocos": ["Turn on *Studio* Mode", "in OBS, look.", "Done, *recording*."]}
        return 200, {}, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(resp)}]}}], "usageMetadata": {"totalTokenCount": 321}}).encode()
    r = revisao.traduzir_srt(tmp / "pt.srt", tmp / "en.srt", idioma="en", contexto="webcam no OBS", _req_=req_falso)
    txt = (tmp / "en.srt").read_text(encoding="utf-8")
    check(r["n_blocos"] == 3 and "00:00:00,500 --> 00:00:02,000" in txt and "Turn on *Studio* Mode" in txt and "Done, *recording*." in txt, "SRT traduzido mantém tempos e destaque *palavra*")
    check("inglês" in prompts[0] and "3 blocos" in prompts[0] and "webcam no OBS" in prompts[0] and "1|Liga o modo estúdio" in prompts[0] and "asteriscos" in prompts[0], "prompt pede idioma, contagem, contexto, blocos numerados e destaque")
    check(r["uso"]["totalTokenCount"] == 321 and "models/gemini-3.5-flash" in r["modelo"] or r["modelo"].startswith("gemini"), f"modelo e uso devolvidos ({r['modelo']})")
    r2 = revisao.traduzir_srt(tmp / "pt.srt", tmp / "en2.srt", idioma="es", curto=True, destaque=False, _req_=req_falso)
    check("20% mais curtas" in prompts[-1] and "asteriscos" not in prompts[-1] and "espanhol" in prompts[-1], "curto=True e destaque=False mudam o prompt")
    check("*" not in (tmp / "en2.srt").read_text(encoding="utf-8"), "sem destaque, asteriscos do modelo são removidos")
    def req_errado(metodo, url, dados=None, headers=None, raw=False):
        return 200, {}, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps({"blocos": ["só um"]})}]}}]}).encode()
    try:
        revisao.traduzir_srt(tmp / "pt.srt", tmp / "x.srt", _req_=req_errado); check(False, "contagem errada dá erro")
    except ErroFerramenta as e:
        check("1 blocos para 3" in str(e), "contagem errada dá erro")
    def req_lixo(metodo, url, dados=None, headers=None, raw=False):
        return 200, {}, json.dumps({"candidates": [{"content": {"parts": [{"text": "não é json"}]}}]}).encode()
    try:
        revisao.traduzir_srt(tmp / "pt.srt", tmp / "x.srt", _req_=req_lixo); check(False, "resposta sem JSON dá erro")
    except ErroFerramenta:
        check(True, "resposta sem JSON dá erro")
    try:
        revisao.traduzir_srt(tmp / "nao.srt", tmp / "x.srt", _req_=req_falso); check(False, "SRT inexistente dá erro")
    except ErroFerramenta:
        check(True, "SRT inexistente dá erro")

print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
