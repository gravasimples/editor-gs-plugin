"""Teste isolado de gerar_apostila (PDF A4 e slides 16:9) em pasta temporária."""
import json, subprocess, sys, tempfile, os
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import apostila
from editor_video.util import ErroFerramenta, FFMPEG
FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)
with tempfile.TemporaryDirectory(prefix="editor-gs-apostila-", ignore_cleanup_errors=True) as tmp:  # Windows: o chdir segura a pasta
    tmp = Path(tmp); os.chdir(tmp)
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=1:d=1", "-frames:v", "1", str(tmp / "print.png")], check=True)
    cont = {"titulo": "Checklist do OBS para a primeira aula", "destaque": "OBS", "subtitulo": "Do zero à primeira gravação, sem susto", "autor": "Grava Simples", "data": "30/10/2026",
            "secoes": [{"titulo": "Antes de abrir o OBS", "destaque": "Antes", "blocos": [{"paragrafo": "Separe o que vai mostrar na tela. Uma coisa por vez."}, {"lista": ["Webcam ligada", "Microfone escolhido", "Luz na frente do rosto"]}, {"dica": "Feche o que não vai usar: o OBS gosta de computador folgado."}]},
                       {"titulo": "Configurações que importam", "blocos": [{"subtitulo": "Vídeo"}, {"passos": ["Configurações → Vídeo", "Resolução de saída 1920×1080", "FPS comum em 30"]}, {"imagem": str(tmp / "print.png"), "legenda": "Tela de Vídeo do OBS"}, {"atencao": "Não mude a resolução de base com uma gravação aberta."}]},
                       {"titulo": "Gravar", "blocos": ["Clique em Iniciar gravação e fale como se fosse para um amigo.", {"tabela": [["Botão", "O que faz"], ["Iniciar gravação", "grava o arquivo"], ["Iniciar transmissão", "manda ao vivo"]]}]}],
            "cta": "Dúvida? Comenta no vídeo que a gente responde."}
    (tmp / "c.json").write_text(json.dumps(cont, ensure_ascii=False), encoding="utf-8")
    r = apostila.gerar_apostila(tmp / "c.json", tmp / "saida" / "apostila.pdf")
    check(Path(r["pdf"]).exists() and r["paginas"] and r["paginas"] >= 2 and r["secoes"] == 3 and r["tamanho_kb"] > 20, f"apostila A4 gerada ({r['paginas']} páginas, {r['tamanho_kb']} KB)")
    from pypdf import PdfReader
    txt = "".join(p.extract_text() or "" for p in PdfReader(r["pdf"]).pages)
    check("Checklist do OBS" in txt and "FPS comum em 30" in txt and "ATENÇÃO" in txt and "Neste material" in txt, "texto, passos, caixa de atenção e sumário no PDF")
    r2 = apostila.gerar_apostila(cont, tmp / "saida" / "slides.pdf", formato="slides")
    pg = PdfReader(r2["pdf"]).pages
    check(r2["paginas"] == 4 and abs(float(pg[0].mediabox.width) - 960) < 1, f"slides 16:9: capa + uma página por seção ({r2['paginas']})")
    try:
        apostila.gerar_apostila({"titulo": "x"}, tmp / "saida" / "x.pdf"); check(False, "sem seções dá erro")
    except ErroFerramenta:
        check(True, "sem seções dá erro")
    try:
        apostila.gerar_apostila({"titulo": "x", "secoes": [{"titulo": "a", "blocos": [{"imagem": str(tmp / "nao.png")}]}]}, tmp / "saida" / "y.pdf"); check(False, "imagem inexistente dá erro")
    except ErroFerramenta as e:
        check("Imagem" in str(e) or "não encontrado" in str(e), "imagem inexistente dá erro")
    (tmp / "entrada").mkdir()
    try:
        apostila.gerar_apostila(cont, tmp / "entrada" / "z.pdf"); check(False, "não grava em entrada/")
    except ErroFerramenta:
        check(True, "não grava em entrada/")
    import shutil; shutil.copy(r["pdf"], os.environ.get("APOSTILA_COPIA", "/dev/null")) if os.environ.get("APOSTILA_COPIA") else None
print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
