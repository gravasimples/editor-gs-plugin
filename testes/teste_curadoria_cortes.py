"""Curadoria de 13/11/2026: cortes que não comem sílaba, refação sem falso positivo, conectivo que liga ideias fica, conferir_emendas,
transição forte só com motivo, revisor com contexto. Sem vídeo e sem rede (literal desligado por não haver arquivo).
Rodar: ~/.venvs/editor-gs/Scripts/python -I testes/teste_curadoria_cortes.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import cortes as C, transicoes as T, revisao as R

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-curadoria-"))


def ws(texto, ini=0.0, passo=0.4, dur=0.3):
    return [{"palavra": w, "inicio": round(ini + i * passo, 3), "fim": round(ini + i * passo + dur, 3)} for i, w in enumerate(texto.split())]


# 1. conectivo isolado entre duas ideias fica; enchimento puro sai
p1 = ws("o microfone fica perto da boca.") + ws("e", ini=3.4) + ws("a luz vem de frente.", ini=4.6) + ws("hum", ini=7.6) + ws("pronto tá gravando.", ini=8.8)
(tmp / "p1.json").write_text(json.dumps({"palavras": p1, "duracao_s": 11.0}))
C.propor_cortes(str(tmp / "p1.json"), str(tmp / "e1.json"))
e1 = json.loads((tmp / "e1.json").read_text())
vicios = [r["texto"] for r in e1["removidos"] if r["motivo"] == "vício de linguagem isolado"]
check(vicios == ["hum"], f"'e' entre ideias fica, 'hum' sai ({vicios})")

# 2. margens: fim da fala ganha mais folga que o começo, também no bem_dinamico
p2 = ws("primeira frase aqui.") + ws("segunda frase depois.", ini=3.0)
(tmp / "p2.json").write_text(json.dumps({"palavras": p2, "duracao_s": 5.0}))
C.propor_cortes(str(tmp / "p2.json"), str(tmp / "e2.json"), modo="bem_dinamico")
e2 = json.loads((tmp / "e2.json").read_text())
m = e2["manter"]
check(abs(m[0]["fim"] - (p2[2]["fim"] + 0.10)) < 0.011 and abs(m[1]["inicio"] - (p2[3]["inicio"] - 0.06)) < 0.011,
      f"bem_dinamico: fim +0,10 s e começo −0,06 s ({m})")

# 3. refação: mesma abertura com frase diferente NÃO é refação; frase repetida é, e marca conferir quando a que fica é bem mais curta
segs = [{"inicio": 0.0, "fim": 3.0, "texto": "você precisa de uma luz de frente no rosto"},
        {"inicio": 3.5, "fim": 6.0, "texto": "você precisa de um microfone perto da boca"}]
check(C._repeticoes(segs, 15) == {}, "abertura igual, frases diferentes: nada sai")
segs2 = [{"inicio": 0.0, "fim": 3.0, "texto": "a luz de frente deixa o rosto bem iluminado sempre"},
         {"inicio": 3.5, "fim": 5.0, "texto": "a luz de frente deixa"}]
r = C._repeticoes(segs2, 15, similaridade=0.6)
check(0 in r and "conferir" in r[0], f"take que fica bem mais curto pede conferência ({r})")

# 4. conferir_emendas: palavra repetida e frase interrompida aparecem com o instante
p4 = ws("eu só tenho esse não") + ws("isso aqui foi tirado", ini=2.2) + ws("não tem outro jeito.", ini=4.0)
(tmp / "p4.json").write_text(json.dumps({"palavras": p4, "duracao_s": 6.0}))
(tmp / "e4.json").write_text(json.dumps({"manter": [{"inicio": 0.0, "fim": p4[4]["fim"] + 0.05}, {"inicio": p4[9]["inicio"] - 0.05, "fim": 6.0}]}))
ce = C.conferir_emendas(str(tmp / "e4.json"), str(tmp / "p4.json"))
al = ce["emendas"][0]["alertas"]
check(ce["n_emendas"] == 1 and any("repetida" in a for a in al) and any("interrompida" in a for a in al) and "tirado" in ce["emendas"][0]["tirado"],
      f"emenda mostra repetição, frase interrompida e o que saiu ({al})")
check("isso aqui foi tirado" not in ce["texto_final"] and ce["texto_final"].startswith("eu só tenho esse não não tem"), "texto_final é o que fica, para ler de ponta a ponta")
(tmp / "e5.json").write_text(json.dumps({"manter": [{"inicio": 0.0, "fim": p4[4]["inicio"] + 0.1}, {"inicio": p4[9]["inicio"], "fim": 6.0}]}))
check(any("cortada no fim" in a for a in C.conferir_emendas(str(tmp / "e5.json"), str(tmp / "p4.json"))["emendas"][0]["alertas"]), "palavra cortada pela metade é apontada")

# 5. transições: sem troca de assunto nem ênfase, nenhuma transição forte
plano = T.planejar([2.0, 4.1, 6.3, 8.2, 10.4, 12.6, 14.5, 16.8], 18.0, energia="bem_dinamico", receita={"seco": 0.4, "punch": 0.2, "deslize": 0.3, "zoom_blur": 0.1})
fortes = [p["entrada"] for p in plano["planos"] if p["entrada"] in T.FORTES or p["entrada"] == "flash"]
check(fortes == [], f"emendas sem motivo ficam em seco/punch ({plano['resumo']['por_tipo']})")
plano2 = T.planejar([2.0, 9.0, 16.0], 18.0, mudancas=[9.0], receita={"seco": 0.5, "deslize": 0.5})
check(any(p["entrada"] == "deslize" and abs(p["inicio"] - 9.0) < 0.01 for p in plano2["planos"]), "troca de assunto ganha a transição forte")

# 6. revisor recebe a fala e o plano de gráficos
pc = tmp / "pc.json"; pc.write_text(json.dumps({"segmentos": [{"inicio": 0.0, "fim": 2.0, "texto": "luz de frente"}]}))
gj = tmp / "g.json"; gj.write_text(json.dumps({"itens": [{"tipo": "logos", "inicio": 1.0, "palavra": "OBS", "itens": [{"texto": "OBS"}]}]}))
ctx = R.contexto_revisao(str(pc), str(gj), "Reels calmo")
check("0.0: luz de frente" in ctx and "logos OBS" in ctx and "Reels calmo" in ctx and "continuidade" in R.PROMPT and "efeito_sem_motivo" in R.PROMPT,
      "revisor recebe fala, gráficos e pedido; prompt procura continuidade e efeito sem motivo")

print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
