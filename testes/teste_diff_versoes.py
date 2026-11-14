"""Diff "o que mudou" (10/11/2026): EDLs, planos de grafismos e estilos sintéticos; cobre par ausente e nada mudou.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_diff_versoes.py"""
import json, os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import diff_versoes as dv
from editor_video.util import ErroFerramenta
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

_td = tempfile.TemporaryDirectory(prefix="gs-teste-diff-", ignore_cleanup_errors=True); tmp = Path(_td.name)

# --- EDL: a versão B tira uma pausa de 12 a 14 s, devolve um trecho de 20 a 22 s
edl_a = {"manter": [{"inicio": 0.0, "fim": 10.0}, {"inicio": 12.0, "fim": 20.0}, {"inicio": 22.0, "fim": 30.0}],
         "removidos": [{"inicio": 10.0, "fim": 12.0, "motivo": "pausa", "texto": ""}, {"inicio": 20.0, "fim": 22.0, "motivo": "refação (frase repetida)", "texto": "olha de novo"}]}
edl_b = {"manter": [{"inicio": 0.0, "fim": 10.0}, {"inicio": 14.0, "fim": 22.0}, {"inicio": 22.0, "fim": 30.0}],
         "removidos": [{"inicio": 10.0, "fim": 14.0, "motivo": "pausa", "texto": ""}]}
(tmp / "a.json").write_text(json.dumps(edl_a), encoding="utf-8"); (tmp / "b.json").write_text(json.dumps(edl_b), encoding="utf-8")
r = dv.comparar_versoes(edl_a=tmp / "a.json", edl_b=tmp / "b.json")
c = r["cortes"]
check(c["tirou"] == [{"inicio": 12.0, "fim": 14.0, "duracao_s": 2.0, "motivo": "pausa", "texto": ""}], f"tirou o trecho 12–14 com motivo pausa: {c['tirou']}")
check(c["voltou"] == [{"inicio": 20.0, "fim": 22.0, "duracao_s": 2.0}], f"voltou o trecho 20–22: {c['voltou']}")
check(c["duracao_a_s"] == 26.0 and c["duracao_b_s"] == 26.0, f"durações: {c['duracao_a_s']} → {c['duracao_b_s']}")
check("Tirou a pausa de 0:12 a 0:14." in r["resumo"] and "Voltou o trecho de 0:20 a 0:22." in r["resumo"], f"resumo em frases: {r['resumo']}")
check(r["grafismos"] is None and r["estilo"] is None and r["mudou"], "pares ausentes ficam None; mudou=True")
check(dv.mmss(12.4) == "0:12,4" and dv.mmss(65) == "1:05", "mmss com décimo só quando precisa")

# EDL igual → nada mudou
r0 = dv.comparar_versoes(edl_a=edl_a, edl_b=json.dumps(edl_a))
check(r0["mudou"] is False and r0["resumo"] == ["Nada mudou."], "EDL igual (dict e JSON em texto): Nada mudou.")

# --- Grafismos: entra um número, sai uma manchete, logos muda de instante
ga = {"itens": [{"tipo": "manchete", "palavra": "caro", "texto": "Não custa caro"},
                {"tipo": "logos", "inicio": 8.0, "itens": [{"logo": "meet"}, {"logo": "zoom"}]},
                {"tipo": "kicker", "inicio": 1.0, "texto": "Áudio"}]}
gb = {"itens": [{"tipo": "logos", "inicio": 9.5, "itens": [{"logo": "meet"}, {"logo": "zoom"}]},
                {"tipo": "kicker", "inicio": 1.0, "texto": "Áudio"},
                {"tipo": "numero", "inicio": 31.0, "rotulo": "até", "texto": "R$ 0", "tela_cheia": True}]}
r = dv.comparar_versoes(grafismos_a=ga, grafismos_b=json.dumps(gb))
g = r["grafismos"]
check([x["tipo"] for x in g["entrou"]] == ["numero"] and [x["tipo"] for x in g["saiu"]] == ["manchete"], f"entrou numero, saiu manchete: {[x['tipo'] for x in g['entrou']]} / {[x['tipo'] for x in g['saiu']]}")
check(len(g["moveu"]) == 1 and g["moveu"][0]["mudou"]["inicio"] == {"de": 8.0, "para": 9.5}, f"logos mudou de 8 para 9,5: {g['moveu']}")
check("Entrou o gráfico numero 'R$ 0' em 0:31." in r["resumo"], f"frase do número: {r['resumo']}")
check(any(f.startswith("Saiu o gráfico manchete 'Não custa caro'") and "palavra 'caro'" in f for f in r["resumo"]), "frase da manchete cita a palavra")
check(any("logos" in f and "0:08" in f and "0:09,5" in f for f in r["resumo"]), f"frase do movimento: {r['resumo']}")
check(r["cortes"] is None, "sem EDL, cortes = None")

# --- Estilo: chaves achatadas
ea = {"nome": "padrao", "legenda": {"cor_destaque": "#F79615", "tamanho": 64}, "montagem": {"sfx": False}}
eb = {"nome": "padrao+ajustes", "legenda": {"cor_destaque": "#F4C2D7", "tamanho": 64, "posicao": "centro"}}
r = dv.comparar_versoes(estilo_a=ea, estilo_b=eb)
e = r["estilo"]
check(e["mudou"] == {"legenda.cor_destaque": {"de": "#F79615", "para": "#F4C2D7"}}, f"estilo mudou: {e['mudou']}")
check(e["entrou"] == {"legenda.posicao": "centro"} and e["saiu"] == {"montagem.sfx": False}, f"entrou/saiu: {e['entrou']} / {e['saiu']}")
check("Estilo: legenda.cor_destaque de #F79615 para #F4C2D7." in r["resumo"], f"frase do estilo: {r['resumo']}")

# --- os três pares juntos
r = dv.comparar_versoes(edl_a=edl_a, edl_b=edl_b, grafismos_a=ga, grafismos_b=gb, estilo_a=ea, estilo_b=eb)
check(all(r[k] is not None for k in ("cortes", "grafismos", "estilo")) and len(r["resumo"]) >= 7, f"três pares juntos: {len(r['resumo'])} frases")

# --- erros: só um lado do par; nenhum par
try:
    dv.comparar_versoes(edl_a=edl_a); check(False, "deveria recusar par incompleto")
except ErroFerramenta as ex:
    check("dois lados" in str(ex), f"par incompleto recusa: {ex}")
try:
    dv.comparar_versoes(); check(False, "deveria recusar sem pares")
except ErroFerramenta as ex:
    check("nada para comparar" in str(ex), f"sem pares recusa: {ex}")

# --- pela ferramenta do servidor (estilo por nome em estilos/)
s = servidor.comparar_versoes(edl_a=str(tmp / "a.json"), edl_b=str(tmp / "b.json"), estilo_a="padrao", estilo_b='{"base": "padrao", "legenda": {"cor_destaque": "#FFFFFF"}}')
check("erro" not in s and s["estilo"]["mudou"].get("legenda.cor_destaque", {}).get("para") == "#FFFFFF" and s["cortes"]["tirou"], f"servidor.comparar_versoes resolve estilo por nome e JSON inline: {s.get('resumo')}")
s2 = servidor.comparar_versoes(edl_a=str(tmp / "a.json"))
check("erro" in s2, f"servidor devolve erro em par incompleto: {s2}")

_td.cleanup()
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
