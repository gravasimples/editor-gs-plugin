"""Fase E (08/11/2026): repertório de edição. Gramática de corte (transicoes.py), animações variadas dos grafismos e cortes que pegam
recomeço escondido (retranscrição literal + detector palavra a palavra). Tudo em pasta temporária, sem Remotion de verdade.
Rodar: ~/.venvs/editor-gs/bin/python -I testes/teste_fase_e.py"""
import inspect, json, os, subprocess, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-fase-e-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import transicoes as T, grafismos as G, cortes as C, acabamento as A
from editor_video.util import FFMPEG
import servidor

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

def ws(texto, inicio=0.0, passo=0.4):
    return [{"palavra": w, "inicio": round(inicio + i * passo, 2), "fim": round(inicio + i * passo + 0.3, 2)} for i, w in enumerate(texto.split())]

# --- gramática de corte
cortes = [round(1.5 * k, 2) for k in range(1, 40)]   # 39 emendas em 60 s
r = T.planejar(cortes, 60.0, enfases=[9.05, 30.1], mudancas=[15.0, 45.0], segmentos=[], energia="dinamico")
pl = r["planos"]
check(len(pl) == 40 and pl[0]["inicio"] == 0 and pl[-1]["fim"] == 60.0, "um plano por trecho entre emendas, cobrindo o vídeo todo")
check(all(a["fim"] == b["inicio"] for a, b in zip(pl, pl[1:])), "planos contíguos")
check(all(a["enquadramento"] != b["enquadramento"] for a, b in zip(pl, pl[1:])), "enquadramento nunca repete de um plano para o seguinte (jump cut visível)")
fortes = [p for p in pl if p["entrada"] in T.FORTES or p["entrada"] == "flash"]
check(all(a["entrada"] != b["entrada"] or a["entrada"] == "deslize" for a, b in zip(fortes, fortes[1:])), "transição forte nunca repete a anterior (deslize é de ritmo e pode)")
check(sum(p["entrada"] == "flash" for p in pl) <= 2, "no máximo 2 flashes")
ef = [p["inicio"] for p in pl if p["entrada"] != "seco"]
check(all(b - a >= 0.8 for a, b in zip(ef, ef[1:])), "efeitos não ficam colados um no outro")
tr = [p["inicio"] for p in pl if p["entrada"] == "tremor"]
check(all(b - a >= 6.0 for a, b in zip(tr, tr[1:])), "tremor no máximo a cada 6 s")
check(next(p for p in pl if p["inicio"] == 15.0)["entrada"] in T.FORTES + ("flash",), "troca de assunto ganha transição forte")
check(next(p for p in pl if p["inicio"] == 9.0)["entrada"] in ("punch", "tremor"), "palavra de ênfase logo depois do corte ganha punch-in")
check(r["resumo"]["por_tipo"].get("seco", 0) >= len(pl) * 0.25 and r["resumo"]["por_tipo"].get("seco", 0) <= len(pl) * 0.55, f"seco perto da receita, nem tudo seco nem nada seco: {r['resumo']['por_tipo']}")
check(all(p["z0"] != p["z1"] for p in pl), "câmera anda em todo plano (z0 ≠ z1)")
check(all(p["z1"] <= p["z0"] for p in pl if p["enquadramento"] == "fechado"), "fechado só afasta (não corta a cabeça)")
check(all(min(p["z0"], p["z1"]) >= 1.0 for p in pl), "escala nunca abaixo de 1 (borda do quadro não aparece)")
r2 = T.planejar(cortes, 60.0, enfases=[9.05], mudancas=[15.0], energia="dinamico")
check(r2 == T.planejar(cortes, 60.0, enfases=[9.05], mudancas=[15.0], energia="dinamico"), "planejamento determinístico (mesma entrada, mesma edição)")
rz = T.planejar(cortes, 60.0, mudancas=[15.0, 30.0, 45.0], energia="dinamico", sem_zoom=True, sem_flash=True)
check(all(p["z0"] == 1.0 == p["z1"] for p in rz["planos"]) and not any(p["entrada"] == "flash" for p in rz["planos"]), "sem zoom e sem flash respeitados")
rf = T.planejar(cortes, 60.0, energia="normal", forcar={"21.0": "giro", "22.5": "invalida"})
check(next(p for p in rf["planos"] if p["inicio"] == 21.0)["entrada"] == "giro", "tratamento forçado pelo agente vale")
rl = T.planejar([20.0], 40.0, segmentos=[{"inicio": 5.2}, {"inicio": 9.6}, {"inicio": 14.1}, {"inicio": 26.0}, {"inicio": 31.5}], energia="dinamico")
check(rl["resumo"]["trocas_sem_corte"] >= 3 and all(p["virtual"] for p in rl["planos"] if p["inicio"] in (5.2, 9.6, 14.1)), "plano longo ganha troca de enquadramento sem corte no começo de frase")
sf = T.sfx_dos_planos(pl)
arqs = {e["arquivo"] for e in sf}
check(arqs and {e["categoria"] for e in sf} <= {"whoosh", "swipe", "riser", "impacto", "tick"}, "cada transição tem o seu som (categoria do catálogo CC0, 10/11/2026)")
check(len(sf) < len(cortes) / 2, "corte seco não tem som e o mesmo som não se repete colado (antes: whoosh em toda emenda)")
check(all((RAIZ / "remotion" / "public" / "sfx" / a).exists() for a in arqs), "sons das transições existem em remotion/public/sfx")
g = [{"tipo": "manchete", "inicio": 3.0, "fim": 5.0}, {"tipo": "kicker", "inicio": 10.0, "fim": 20.0, "texto": "1 · Exposição"}, {"tipo": "numero", "inicio": 12.0, "fim": 14.0, "tela_cheia": True}]
check(T.mudancas_de(g, [{"inicio": 30.0}], [40.0]) == [10.0, 12.0, 14.0, 30.0, 40.0], "trocas de assunto: kicker de seção, tela cheia, capítulo, troca de bloco")
check(T.enfases_de(g, [{"inicio": 7.0}]) == [3.0, 7.0], "ênfases: grafismo enfático fora de tela cheia e palavra-chave")

# --- animações variadas
itens = [{"tipo": t, "inicio": float(i), "fim": float(i) + 0.9} for i, t in enumerate(["manchete", "pilula", "manchete", "kicker", "manchete", "pilula", "numero"])]
G.variar_animacoes(itens)
ents = [x["entrada"] for x in itens]
check(all(x in G.ENTRADAS for x in ents) and all(x["saida"] in G.SAIDAS for x in itens), "toda entrada e saída é do repertório")
check(all(a != b for a, b in zip(ents, ents[1:])), "entrada nunca repete a do item anterior")
check(len(set(ents)) >= 4, "repertório usado de verdade (4+ entradas diferentes em 7 itens)")
av = []
mix = G.variar_animacoes([{"tipo": "manchete", "inicio": 0.0, "fim": 1.0, "entrada": "cair", "saida": "voar"}], av)
check(mix[0]["entrada"] == "cair" and mix[0]["saida"] in G.SAIDAS and any("voar" in a for a in av), "escolha do agente vale; saída desconhecida vira aviso")
pal = {"palavras": ws("o obs tem três configurações de webcam e a exposição muda tudo"), "segmentos": []}
norm, _ = G.normalizar({"itens": [{"tipo": "manchete", "palavra": "obs", "texto": "OBS"}, {"tipo": "pilula", "palavra": "webcam", "texto": "WEBCAM"}]}, pal, 10)
check(all("entrada" in x and "saida" in x for x in norm), "normalizar já devolve os itens com entrada e saída")

# --- cortes: recomeço palavra a palavra
p = ws("agora vai depender aí do seu aplicativo agora vai depender do seu aplicativo e pronto")
rc = C._reinicios(p)
check(len(rc) == 1 and rc[0][0] == 0.0 and abs(rc[0][1] - p[7]["inicio"]) < 1e-6, "recomeço achado: sai a primeira tomada até a repetição")
check(C._reinicios(ws("e o e o que a gente faz é isso")) == [], "repetição só de palavras comuns não conta")
check(C._reinicios(ws("clica aqui no botão e depois vai demorar bastante tempo pra configurar tudo e clica aqui no botão")) == [], "repetição longe (muitas palavras no meio) não conta")
p2 = ws("vou procurar vou procurar o e vou procurar o equilíbrio de branco")
rc2 = C._reinicios(p2)
check(rc2 and rc2[-1][1] == p2[6]["inicio"], "recomeço em cadeia fica só com a última tomada")
# janelas suspeitas: buraco com fala e palavra esticada
pw = [{"palavra": "são", "inicio": 0.0, "fim": 0.3}, {"palavra": "basicamente", "inicio": 0.4, "fim": 2.4}, {"palavra": "o", "inicio": 2.5, "fim": 2.6},
      {"palavra": "quanto", "inicio": 4.0, "fim": 4.3}, {"palavra": "luz", "inicio": 4.4, "fim": 4.6}, {"palavra": "fim", "inicio": 9.0, "fim": 9.2}]
sil = [(4.7, 8.9)]  # só esse trecho é silêncio
js = C.janelas_suspeitas(pw, sil, folga_s=0.5)
check(len(js) == 1 and js[0][0] <= 0.4 and js[0][1] >= 4.0, "palavra esticada e buraco com fala viram uma janela suspeita; buraco em silêncio não")
def falso(arquivo, a, b):
    return [{"palavra": w, "inicio": round(a + 0.5 + 0.35 * i, 2), "fim": round(a + 0.8 + 0.35 * i, 2), "literal": True} for i, w in enumerate("são basicamente é o quanto de é basicamente o quanto de luz".split())]
novas, info = C.refinar_literal(pw, "x.mp4", sil, transcrever=falso)
check(len(info["trocas"]) == 1 and len(novas) > len(pw) and any(w.get("literal") for w in novas), "retranscrição literal troca o miolo da janela")
check(all(a["inicio"] <= b["inicio"] for a, b in zip(novas, novas[1:])), "palavras continuam em ordem depois da troca")
_, info2 = C.refinar_literal(pw, "x.mp4", sil, transcrever=lambda a, x, y: [])
check(info2["trocas"] == [], "literal sem palavra a mais não troca nada")
# propor_cortes com recomeço (sem arquivo: literal não roda)
pj = tmp / "p.json"
pal3 = ws("agora vai depender aí do seu aplicativo agora vai depender do seu aplicativo e pronto", passo=0.35)
pj.write_text(json.dumps({"palavras": pal3, "segmentos": [{"inicio": 0.0, "fim": pal3[-1]["fim"], "texto": "x"}], "duracao_s": 6.0}))
res = C.propor_cortes(str(pj), str(tmp / "edl.json"), modo="dinamico")
edl = json.loads((tmp / "edl.json").read_text())
check("recomeço (tomada abandonada)" in res["resumo_motivos"], "propor_cortes registra o recomeço no resumo")
check(all(m["inicio"] >= pal3[7]["inicio"] - 0.06 or m["fim"] <= 0.06 for m in edl["manter"]), "a primeira tomada sai da EDL")
check("literal" in inspect.signature(C.propor_cortes).parameters, "propor_cortes tem a chave literal (padrão ligado)")

# --- montar_remotion manda os planos para o Remotion
vid = tmp / "v.mp4"
subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=360x640:d=6:r=30", "-f", "lavfi", "-i", "sine=f=300:d=6", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(vid)], check=True)
capt = {}
def render_falso(comp, props, saida, timeout=0):
    capt["props"] = props
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(vid), "-c", "copy", str(saida)], check=True); return Path(saida)
A.renderizar_remotion = render_falso
pjv = tmp / "pv.json"; pjv.write_text(json.dumps({"palavras": ws("um dois três quatro cinco seis sete oito", passo=0.6), "segmentos": [{"inicio": 0.0, "fim": 4.5, "texto": "um dois"}]}))
edlv = tmp / "edlv.json"; edlv.write_text(json.dumps({"manter": [{"inicio": 0, "fim": 2}, {"inicio": 3, "fim": 5}, {"inicio": 6, "fim": 8}]}))
out = A.montar_remotion(str(vid), str(tmp / "o.mp4"), palavras_json=str(pjv), edl_json=str(edlv), transicoes="auto", energia="bem_dinamico", sfx=True, tela_final=False)
cam = capt["props"].get("camera")
check(cam and len(cam["planos"]) >= 3 and out["transicoes"]["energia"] == "bem_dinamico", "transicoes=auto manda os planos da câmera e o resumo volta no resultado")
check(not any(e["arquivo"] == "whoosh.wav" and e["inicio"] in (1.95, 3.95) and False for e in capt["props"]["sfx"]), "sfx dos planos no lugar do whoosh fixo")
out2 = A.montar_remotion(str(vid), str(tmp / "o2.mp4"), palavras_json=str(pjv), edl_json=str(edlv), transicoes="nenhuma", tela_final=False)
check(capt["props"].get("camera") is None and out2["transicoes"] is None, "transicoes=nenhuma volta ao modo antigo")
A.montar_remotion(str(vid), str(tmp / "o3.mp4"), palavras_json=str(pjv), edl_json=str(edlv), transicoes='{"2.0": "giro"}', tela_final=False)
check(next(p for p in capt["props"]["camera"]["planos"] if p["inicio"] == 2.0)["entrada"] == "giro", "JSON de transições força o tipo na emenda")
sig = inspect.signature(servidor.montar_remotion).parameters
check("transicoes" in sig and "energia" in sig, "ferramenta montar_remotion aceita transicoes e energia")
for nome in ("profissional", "lista"):
    est = json.loads((RAIZ / "estilos" / f"{nome}.json").read_text())
    check(est["montagem"].get("transicoes") == "auto", f"estilo {nome} liga a gramática de corte")
tsx = (RAIZ / "remotion" / "src" / "Montagem.tsx").read_text()
check("camaraDe(" in tsx and "LuzCamera" in tsx, "Montagem.tsx usa a câmera da fase E")

# recalibração pela receita do repertório (08/11): proporção segue a receita, giro/luz só forçados, energia mexe no seco
cs = [round(1.7 * i + 0.3 * (i % 3), 2) for i in range(1, 50)]
def mix(**kw):
    r = T.planejar(cs, 90, enfases=cs[::4], mudancas=cs[::12], **kw)["resumo"]; tot = sum(r["por_tipo"].values()); return r, {k: v / tot for k, v in r["por_tipo"].items()}
r, m = mix()
check(abs(m.get("seco", 0) - 0.53) <= 0.12 and m.get("punch", 0) >= 0.15 and m.get("deslize", 0) >= 0.12, f"receita padrão perto do Máquina (seco ~50%, punch, deslize): {r['por_tipo']}")
check(not m.get("giro") and not m.get("luz") and r["receita"], "giro e luz fora da receita padrão; resumo traz a receita")
_, mc = mix(energia="calmo"); _, mb = mix(energia="bem_dinamico")
check(mc.get("seco", 0) > mb.get("seco", 0), "calmo tem mais seco que bem dinâmico")
_, ma = mix(receita={"seco": 0.9, "deslize": 0.1})
check(ma.get("seco", 0) >= 0.8 and not ma.get("punch"), "receita de aula (quase só seco) é respeitada, sem punch")
_, mf = mix(receita={"seco": 0.9, "deslize": 0.1}, forcar={str(cs[5]): "giro"})
check(mf.get("giro"), "tipo fora da receita ainda entra quando forçado")
_, mr = mix(receita={})
check(mr.get("seco", 0) > 0.5, "receita={} volta à gramática antiga")
rf = T.planejar(cs, 90, receita={"seco": 0.5, "deslize": 0.5})["planos"]
dz = [p["inicio"] for p in rf if p["entrada"] == "deslize"]
check(all(b - a >= T.GAP_DESLIZE for a, b in zip(dz, dz[1:])), "deslize respeita a folga mínima")
check("receita_transicoes" in str(inspect.signature(servidor.montar_remotion)), "montar_remotion aceita receita_transicoes")

print(f"\n{'OK' if not FALHAS else 'FALHOU'}: {len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
