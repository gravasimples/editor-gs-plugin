"""Efeitos com limite (15/11/2026, item 3 da ordem autorizada): zoom de impacto >= 8 s e <= 6/min, tremor <= 10% do Reels (5% do longo),
>= 3 s de outro impacto e nunca em texto sendo lido, pedido do agente sempre passa, whoosh com o pico no corte (150–300 ms antes) e no
máximo 1 a cada 5 s, palavra de impacto na subida de energia (até +150 ms depois do Whisper). Sem render.
Rodar: python -X utf8 -I testes/teste_efeitos_limite.py"""
import os, sys, tempfile, wave
from pathlib import Path
import numpy as np
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-efeitos-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import transicoes as T, nivel_pro as N, bordas as B

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def planos_de(tipos_por_t, dur):
    """Planos artificiais: um por instante, com a entrada pedida (o primeiro plano começa em 0)."""
    ts = sorted(tipos_por_t)
    out = [{"inicio": 0.0, "fim": ts[0], "entrada": "seco", "dur": 0.0}]
    for k, t in enumerate(ts):
        e = tipos_por_t[t]; forc = e.endswith("!")
        out.append({"inicio": t, "fim": ts[k + 1] if k + 1 < len(ts) else dur, "entrada": e.rstrip("!"), "dur": 0.08, **({"forcado": True} if forc else {})})
    return out

# --- zoom de impacto: 8 s entre si e no máximo 6 por minuto
p, reb = T.limitar_efeitos(planos_de({t: "punch" for t in range(2, 60, 2)}, 60.0), 60.0)
punch = [x["inicio"] for x in p if x["entrada"] == "punch"]
check(all(b - a >= T.PUNCH_GAP_S for a, b in zip(punch, punch[1:])), f"punch com 8 s ou mais entre si: {punch}")
check(len(punch) <= T.PUNCH_POR_MIN and reb["punch"] == 29 - len(punch), f"no máximo 6 por minuto, o resto vira seco ({len(punch)} ficaram, {reb})")
p2, _ = T.limitar_efeitos(planos_de({float(t): "punch" for t in range(1, 200)}, 200.0), 200.0)
pt = [x["inicio"] for x in p2 if x["entrada"] == "punch"]
check(all(sum(1 for y in pt if x <= y < x + 60) <= 6 for x in pt), "em qualquer janela de 60 s, no máximo 6")
check(all(x["dur"] == 0.0 for x in p2 if x["entrada"] == "seco"), "rebaixado vira seco de verdade (sem duração de efeito)")

# --- tremor: 10% do Reels, 3 s de outro impacto, nunca em texto sendo lido
p, reb = T.limitar_efeitos(planos_de({t: "tremor" for t in np.arange(1.0, 30.0, 1.0)}, 30.0), 30.0)
tr = [x["inicio"] for x in p if x["entrada"] == "tremor"]
check(len(tr) * T.TREMOR_VISIVEL_S <= 0.10 * 30 + 1e-9, f"tremor visível até 10% de 30 s: {len(tr)} tremores")
imp = sorted(x["inicio"] for x in p if x["entrada"] in ("tremor", "punch"))
check(all(b - a >= T.TREMOR_GAP_S for a, b in zip(imp, imp[1:])), f"3 s ou mais entre impactos: {imp}")
longo, _ = T.limitar_efeitos(planos_de({t: "tremor" for t in np.arange(3.0, 300.0, 3.0)}, 300.0), 300.0)
check(sum(1 for x in longo if x["entrada"] == "tremor") * T.TREMOR_VISIVEL_S <= 0.05 * 300 + 1e-9, "vídeo longo: tremor até 5%")
p, _ = T.limitar_efeitos(planos_de({5.0: "tremor", 12.0: "tremor", 20.0: "tremor"}, 30.0), 30.0, leitura=[(11.0, 14.0)])
check([x["entrada"] for x in p[1:]] == ["tremor", "punch", "tremor"], f"tremor em cima de texto sendo lido vira punch: {[x['entrada'] for x in p[1:]]}")
jan = T.janelas_de_leitura([{"tipo": "checklist", "inicio": 2, "fim": 5}, {"tipo": "pilula", "inicio": 6, "fim": 7}, {"tipo": "pilula", "inicio": 8, "fim": 9, "tela_cheia": True}],
                           [{"modo": "cheio", "inicio": 0, "fim": 10}, {"modo": "tutorial", "inicio": 10, "fim": 20}])
check(jan == [(2.0, 5.0), (8.0, 9.0), (10.0, 20.0)], f"leitura = grafismo de texto, tela cheia e bloco com tela: {jan}")

# --- pedido do agente sempre passa e ocupa a vaga
p, _ = T.limitar_efeitos(planos_de({4.0: "punch", 6.0: "punch!", 9.0: "punch"}, 30.0), 30.0)
check([x["entrada"] for x in p[1:]] == ["seco", "punch", "seco"], f"punch pedido pelo agente fica e os automáticos perto saem: {[x['entrada'] for x in p[1:]]}")
check(all("forcado" not in x for x in p), "marca interna não vai para o Remotion")

# --- planejar aplica os limites (energia bem dinâmica, muita ênfase)
cortes = [round(1.3 * k, 2) for k in range(1, 46)]
pl = T.planejar(cortes, 60.0, enfases=[c + 0.1 for c in cortes], energia="bem_dinamico", receita={"seco": 0.3, "punch": 0.7})
pp = [x["inicio"] for x in pl["planos"] if x["entrada"] == "punch"]
tt = [x["inicio"] for x in pl["planos"] if x["entrada"] == "tremor"]
check(all(b - a >= 8 for a, b in zip(pp, pp[1:])) and len(pp) <= 6, f"planejar: punch espaçado ({pp})")
check(len(tt) * T.TREMOR_VISIVEL_S <= 6.0, f"planejar: tremor até 10% ({tt})")
check("limites" in pl["resumo"] and sum(pl["resumo"]["limites"]["rebaixados"].values()) > 0, f"resumo conta os rebaixados: {pl['resumo']['limites']}")

# --- whoosh: pico no corte (150–300 ms antes) e 1 a cada 5 s
pasta = tmp / "sfx"; pasta.mkdir()
def wav_pico(nome, pico_s, dur=0.6, sr=8000):
    x = np.zeros(int(sr * dur)); i = int(pico_s * sr); x[max(0, i - 40):i + 40] = 0.8
    with wave.open(str(pasta / nome), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((x * 32767).astype(np.int16).tobytes())
wav_pico("w-cedo.wav", 0.03); wav_pico("w-meio.wav", 0.22); wav_pico("w-tarde.wav", 0.5)
check(abs(N.pico_sfx("w-meio.wav", pasta) - 0.22) <= 0.02, f"pico do arquivo medido: {N.pico_sfx('w-meio.wav', pasta)}")
check(N.antecipa_movimento("w-cedo.wav", pasta) == 0.15 and abs(N.antecipa_movimento("w-meio.wav", pasta) - 0.22) <= 0.02
      and N.antecipa_movimento("w-tarde.wav", pasta) == 0.30, "antecipação = pico preso entre 150 e 300 ms")
N.SFX_DIR, antigo = pasta, N.SFX_DIR
cat = {"whoosh": ["w-meio.wav"], "swipe": ["w-meio.wav"]}
ev = N.sfx_auto([1.0, 2.0, 3.5, 7.0, 9.0, 13.0], [], cortinas_s=[11.0], catalogo=cat)
mov = [e for e in ev if e["categoria"] in N.MOVIMENTO]
ev2 = N.sfx_auto([1.0, 6.0, 9.0, 15.0], [], cortinas_s=[4.0], catalogo=cat)
check([round(e["inicio"] + 0.22, 1) for e in mov] == [1.0, 11.0] and len(ev2) == 3 and ev2[0]["categoria"] == "swipe", f"whoosh e swipe dividem a vaga de 1 a cada 5 s e a cortina vem primeiro (ev2={[(e["categoria"], e["inicio"]) for e in ev2]}): {[(e['categoria'], e['inicio']) for e in mov]}")
check(all(0.15 <= c - e["inicio"] <= 0.30 for e, c in zip(mov, [1.0, 11.0])), "cada whoosh entra 150–300 ms antes do corte")
pl_s = [{"inicio": 0.0, "entrada": "seco"}] + [{"inicio": t, "entrada": "zoom_blur"} for t in (2.0, 4.0, 8.0)] + [{"inicio": 9.0, "entrada": "deslize"}]
import editor_video.nivel_pro as NP
orig = NP.escolher_sfx; NP.escolher_sfx = lambda c, t, cat=None: "w-meio.wav"
try:
    sp = T.sfx_dos_planos(pl_s)
finally:
    NP.escolher_sfx = orig; N.SFX_DIR = antigo
check([round(e["inicio"] + 0.22, 1) for e in sp] == [2.0, 8.0], f"transições: som de movimento 1 a cada 5 s, pico no corte: {[e['inicio'] for e in sp]}")

# --- palavra de impacto na subida de energia (até +150 ms)
env = {"db": np.full(500, -50.0), "off": 0.0}
env["db"][212:260] = -10.0            # ataque da voz em 2,12 s; o Whisper disse 2,00
check(abs(B.subida_de_energia(env, 2.0) - 2.12) <= 0.011, f"ataque achado depois do Whisper: {B.subida_de_energia(env, 2.0)}")
env["db"][300:] = -50.0; env["db"][330:400] = -10.0  # ataque em 3,30: longe demais (mais de 150 ms)
check(B.subida_de_energia(env, 3.0) == 3.0, "sem subida até 150 ms, fica no Whisper")
al = B.alinhar_na_energia([{"texto": "PRONTO", "inicio": 2.0, "fim": 2.05}], env)
check(al[0]["inicio"] == 2.12 and al[0]["fim"] > al[0]["inicio"], f"palavra-chave alinhada e o fim acompanha: {al}")
check(B.alinhar_na_energia([{"inicio": 2.0}], None) == [{"inicio": 2.0}], "sem áudio, nada muda")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
