"""Progresso ao vivo do pedido (11/11/2026): etapas, porcentagem e tempo restante lidos do registro da rodada (servico/progresso.py).
Isolado: registros stream-json sintéticos em pasta temporária. Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_progresso.py"""
import json, shutil, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from servico import progresso as P

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

T0 = datetime(2026, 11, 11, 14, 0, tzinfo=timezone.utc)
def ts(s): return (T0 + timedelta(seconds=s)).isoformat().replace("+00:00", "Z")
def uso(nome, **entrada): return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": nome, "input": entrada}]}}
def rodada(pasta, nome, eventos, fim=None):
    linhas = [json.dumps({"ts": ts(0), "meta": {"issue": "GRA-1"}})]
    linhas += [json.dumps({"ts": ts(s), "chunk": json.dumps(e)}) for s, e in eventos]
    if fim is not None:
        linhas.append(json.dumps({"ts": ts(fim), "chunk": json.dumps({"type": "result", "subtype": "success"})}))
    p = pasta / f"{nome}.ndjson"; p.write_text("\n".join(linhas) + "\n", encoding="utf-8"); return p

tmp = Path(tempfile.mkdtemp(prefix="gs-teste-progresso-"))
hist = tmp / "hist"; hist.mkdir()
M = "mcp__editor-de-video__"
EDICAO = [(30, uso(M + "extrair_trecho")), (60, uso(M + "transcrever")), (120, uso(M + "propor_cortes")), (200, uso(M + "aplicar_cortes")),
          (260, uso(M + "gerar_legenda")), (320, uso(M + "montar_remotion")), (620, uso(M + "folha_contato")),
          (700, uso("Bash", command='curl -s -X POST http://127.0.0.1:3200/api/issues/x/comments -d "## Resumo ..."'))]

# etapas: o plano postado na conversa cita legenda/capcut e não conta; grep no código não conta; capa fica no render
p = rodada(tmp, "viva", [(20, uso("Bash", command='curl -s -X POST http://127.0.0.1:3200/api/issues/x/comments -d "Plano: corte, legenda, grafismos, capcut"')),
                         (25, uso("Bash", command="grep -n montar_remotion acabamento.py")),
                         (30, uso(M + "extrair_trecho")), (60, uso(M + "transcrever")), (200, uso(M + "aplicar_cortes")),
                         (320, uso("Bash", command="python -I runner.py args_9x16.json  # montar_remotion")), (330, uso(M + "gerar_capa")),
                         (340, uso(M + "transcrever"))])
m = P.marcos(p)
check(list(sorted(m["chegou"], key=P.ORDEM.get)) == ["preparo", "transcricao", "cortes", "render"], f"etapas na ordem, sem falso positivo do plano e do grep ({sorted(m['chegou'], key=P.ORDEM.get)})")
check(m["atual"] == "render", "capa durante o render não pula para Revisão e retranscrever não volta a barra")

# sem histórico: estimativa inicial, porcentagem entre 1 e 99, etapas marcadas
r = P.calcular(p, hist, agora=T0 + timedelta(seconds=400))
check(r["estimativa"] == "inicial" and r["restante_s"] and r["restante_s"] > 0, f"sem histórico usa a estimativa inicial ({r['restante_s']} s)")
check(1 <= r["pct"] <= 99 and r["atual_nome"] == "Montando o vídeo", f"porcentagem {r['pct']}% na etapa {r['atual_nome']}")
check([e["estado"] for e in r["etapas"]][:6] == ["feita", "feita", "feita", "feita", "feita", "atual"], "etapas anteriores feitas, render atual")

# com 5 rodadas normais + 1 travada: histórico ignora a travada
for i in range(5):
    rodada(hist, f"ok{i}", EDICAO, fim=760)
rodada(hist, "travada", EDICAO, fim=3 * 3600)
P._HIST["dados"] = None
h = P.historico(hist)
check(h["rodadas"] == 5 and abs(h["total_s"] - 760) < 1, f"histórico usa as 5 normais e descarta a de 3 h ({h['rodadas']} rodadas, {h['total_s']} s)")
r2 = P.calcular(p, hist, agora=T0 + timedelta(seconds=400))
check(r2["estimativa"] == "historico" and r2["restante_s"] < 760, f"com histórico a estimativa vem das rodadas ({r2['restante_s']} s)")

# etapa muito acima do normal: avisa e não promete tempo
r3 = P.calcular(p, hist, agora=T0 + timedelta(seconds=320 + 2000))
check(r3["lenta"] and r3["restante_s"] is None, "etapa muito demorada vira aviso, sem estimativa")
r4 = P.calcular(rodada(tmp, "vazia", []), hist, agora=T0 + timedelta(seconds=10))
check(r4["atual"] is None and r4["atual_nome"] == "Lendo o pedido", "rodada sem ferramenta ainda: 'Lendo o pedido'")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
