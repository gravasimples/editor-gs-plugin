"""Busca por fala e ganchos, fase 2 (03/11/2026): instante exato por palavra, player do YouTube no trecho, tipos de gancho e resumo por tipo,
gancho escolhido indo para o pedido do Reel reciclado. Sem banco nem rede: arquivos temporários. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_busca_ganchos_fase2.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import acervo as acv, ganchos as gch, automacoes as aut

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

td = Path(tempfile.mkdtemp())
# entrega com palavras: instante exato
p1 = td / "palavras.json"
p1.write_text(json.dumps({"segmentos": [{"inicio": 10.0, "fim": 16.0, "texto": "Agora eu vou ligar a supressão de ruído no microfone."}],
                          "palavras": [{"palavra": w, "inicio": 10.0 + i * 0.6, "fim": 10.5 + i * 0.6} for i, w in enumerate("Agora eu vou ligar a supressão de ruído no microfone.".split())]}))
f1 = {"id": "app:x:palavras", "origem": "app", "plataforma": "app", "titulo": "t", "url": None, "data": "2026-11-01", "arquivo": str(p1), "video_local": "/x.mp4"}
r = acv.buscar("supressão de ruído", [f1])
check(r and r[0]["instante_tipo"] == "exato" and abs(r[0]["instante"] - (10.0 + 5 * 0.6)) < 0.01, f"instante exato da palavra ({r[0]['instante'] if r else None})")
# GSI só com frases (s, e, t): aproximado pela posição; YouTube ganha embed no instante
p2 = td / "gsi.json"; p2.write_text(json.dumps({"segmentos": [{"s": 100.0, "e": 110.0, "t": "um dois três quatro cinco seis sete oito webcam nove"}]}))
f2 = {"id": "gsi:youtube:abc", "origem": "gsi", "plataforma": "youtube", "titulo": "v", "url": "https://www.youtube.com/watch?v=FgYvRFmGZjc", "data": "2026-10-01", "arquivo": str(p2), "video_local": None}
r = acv.buscar("webcam", [f2])
check(r and r[0]["instante_tipo"] == "aproximado" and 104 < r[0]["instante"] < 110, f"sem palavras: instante aproximado pela posição ({r[0]['instante'] if r else None})")
check(r and r[0]["embed"].startswith("https://www.youtube-nocookie.com/embed/FgYvRFmGZjc?start=") and "t=" in r[0]["link"], "YouTube: player embutido no trecho e link no instante")
check(acv.youtube_id("https://youtu.be/FgYvRFmGZjc") == "FgYvRFmGZjc" and acv.youtube_id("https://instagram.com/p/x") is None, "id do YouTube por link curto; Instagram sem embed")

# tipos de gancho
casos = {"Você sabia que o OBS grava em dois formatos?": "pergunta", "Pare de gravar com a luz atrás de você": "erro", "3 erros que deixam sua aula amadora": "erro",
         "5 passos para gravar sua primeira aula": "numero", "Celular x webcam: qual vale mais": "contraste", "Antes e depois do meu cenário": "contraste",
         "O segredo do áudio limpo": "segredo", "Chegou a atualização do OBS 32": "novidade", "Como gravar aula sem gastar nada": "como", "Pov: primeira live sozinho": "historia",
         "Um canal que começou dentro de um quarto": "outro"}
erros = {t: (gch.tipo_gancho(t), e) for t, e in casos.items() if gch.tipo_gancho(t) != e}
check(not erros, f"tipos de gancho por regra ({erros or 'todos certos'})")
itens = [{"gancho": "a", "tipo": "pergunta", "razao": r} for r in (0.5, 1.0, 1.2, 40.0)] + [{"gancho": "b", "tipo": "erro", "razao": 2.0}, {"gancho": "c", "tipo": "erro", "razao": None}]
t = {x["tipo"]: x for x in gch.por_tipo(itens)}
check(t["pergunta"]["razao_mediana"] == 1.1 and t["pergunta"]["razao_media"] > 10 and t["pergunta"]["melhor_razao"] == 40.0, "resumo por tipo: mediana resiste ao viral; melhor exemplo")
check(t["erro"]["n"] == 2 and t["erro"]["medidos"] == 1 and t["erro"]["pouca_amostra"], "conta medidos e marca pouca amostra")
check(gch.por_tipo(itens)[0]["tipo"] == "erro", "ordena pela mediana")

# gancho da biblioteca no pedido do Reel reciclado
fonte = {"plataforma": "instagram", "id": "X", "titulo": "Reel antigo", "publicado": "2025-01-01", "views": 1000, "razao": 3.0, "origem": "gsi"}
txt = aut.reciclado_pedido(fonte, "entrada/x.mp4", None, gancho_sugerido="Pare de gravar com a luz atrás")
check("Gancho escolhido pelo Raphael" in txt and "Pare de gravar com a luz atrás" in txt, "gancho escolhido entra no pedido do Reel reciclado")
check("Gancho escolhido" not in aut.reciclado_pedido(fonte, "entrada/x.mp4"), "sem gancho escolhido, pedido igual ao de antes")
print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
