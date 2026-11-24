"""Cortes de vídeo longo (15/11/2026, item 5 da ordem autorizada): borda em frase (não abre em "E…/Mas…/Então, …" nem em muleta solta, fecha a
frase em que parou, larga a última frase pendurada, o ar do fim não entra na frase seguinte colada), nota de qualidade sem modelo e
`conferir_cortes_longos` regravando o cortes.json com sobreposição resolvida. Também o catálogo do inventário de efeitos (sem Gemini).
Rodar: python -X utf8 -I testes/teste_cortes_longos.py"""
import json, os, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="gs-teste-longos-"))
os.environ["EDITOR_GS_WORKSPACE"] = str(tmp / "ws")
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video")); sys.path.insert(0, str(RAIZ))
from editor_video import longos as L, efeitos_ref as EF

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)


def fala(frases_txt, t0=0.0, passo=0.3, pausa=0.5):
    """Palavras artificiais: cada frase da lista, palavra a cada `passo` s, `pausa` s entre frases (0 = colada, como o Whisper às vezes faz)."""
    out, t = [], t0
    for f, pz in frases_txt:
        for w in f.split():
            out.append({"palavra": w, "inicio": round(t, 3), "fim": round(t + passo, 3)}); t += passo
        t += pz
    return out


# --- frases: pontuação e pausa longa fecham; pausa curta sem ponto não
pal = fala([("Olha só isso aqui.", 0.2), ("sem ponto mas com pausa longa", 1.0), ("E aí eu continuo.", 0.3)])
sp = L.frases(pal)
check([s[2] for s in sp] == ["Olha só isso aqui.", "sem ponto mas com pausa longa", "E aí eu continuo."], f"frases por ponto e pausa >= 0,9 s: {[s[2] for s in sp]}")

check(L.abertura_fraca("E aí eu fiz") and L.abertura_fraca("Mas o problema") and L.abertura_fraca("Então, vamos lá"), "abertura apoiada na anterior ou com muleta e vírgula é fraca")
check(not L.abertura_fraca("Então eu larguei tudo") and not L.abertura_fraca("O OBS grava sozinho"), "\"Então eu…\" sem vírgula e frase normal não são fracas")
check(L.termina_pendurado("e aí você precisa de") and not L.termina_pendurado("e pronto, tá gravando."), "fim pendurado em preposição")

# --- encaixe: começa no meio de frase → início da frase; termina no meio → fim da frase
frs = [("Hoje eu vou te mostrar o jeito certo de gravar aula no OBS.", 0.4),
       ("E aqui eu tenho a velocidade do obturador.", 0.4),
       ("O que são essas duas opções aqui?", 0.4),
       ("São basicamente o quanto de luz entra na câmera e isso muda tudo na imagem final.", 0.4),
       ("Percebe como a imagem fica mais limpa quando eu baixo o ISO bem devagar aqui.", 0.4),
       ("E pronto, tá gravando com qualidade de estúdio sem gastar nada com câmera nova.", 0.4),
       ("Depois disso você ainda precisa de", 0.4)]
pal = fala(frs); sp = L.frases(pal)
st = [s for s, _, _ in sp]; en = [e for _, e, _ in sp]
a, z, mudou = L.encaixar_em_frase(st[1] + 0.9, en[5] - 0.5, sp)
check(mudou and abs(a - (st[2] - 0.05)) < 0.02, f"corte que abre em \"E aqui eu tenho…\" passa para a pergunta seguinte: {a} (frase em {st[2]})")
check(abs(z - min(en[5] + L.RABO_S, st[6] - 0.05)) < 0.02, f"fecha a frase em que parou, com ar sem entrar na seguinte: {z} (frase termina {en[5]}, seguinte {st[6]})")
a2, z2, _ = L.encaixar_em_frase(st[2], en[6], sp)
check(abs(z2 - min(en[5] + L.RABO_S, st[6] - 0.05)) < 0.02, f"última frase pendurada (\"…precisa de\") sai quando mantém 70%: {z2}")

# --- ar do fim não invade frase colada
col = fala([("Eu vou desmarcar a exposição automática agora mesmo aqui no aplicativo da Logitech.", 0.0), ("E aqui eu tenho o ISO.", 0.3)], passo=0.35)
spc = L.frases(col)
_, zc, _ = L.encaixar_em_frase(0.0, spc[0][1], spc, min_s=4)
check(zc <= spc[1][0], f"frase seguinte colada: o fim não entra nela ({zc} <= {spc[1][0]})")

# --- nota de qualidade
q_bom = L.nota_qualidade(st[2] - 0.05, en[5] + 0.4, pal, sp, min_s=8)
q_ruim = L.nota_qualidade(st[1] + 0.9, en[5] - 0.5, pal, sp, min_s=8)
check(q_bom["nota"] == 100 and not q_bom["problemas"], f"corte em frase, abertura forte: 100 ({q_bom})")
check(q_ruim["nota"] <= 65 and "começa no meio de uma frase" in q_ruim["problemas"] and "termina no meio de uma frase" in q_ruim["problemas"], f"corte no meio das frases perde nota: {q_ruim}")
q_num = L.nota_qualidade(st[2] - 0.05, en[5] + 0.4, pal, sp, gancho="5 ajustes que salvam sua aula", min_s=8)
check(any("número" in p for p in q_num["problemas"]), f"gancho com número que ninguém disse: {q_num['problemas']}")
q_dur = L.nota_qualidade(st[2] - 0.05, en[3] + 0.4, pal, sp, min_s=20)
check(any("duração" in p for p in q_dur["problemas"]), "corte curto demais é apontado")

# --- conferir_cortes_longos regrava o arquivo, guarda o original e resolve sobreposição
pj = tmp / "palavras.json"; pj.write_text(json.dumps({"palavras": pal}), encoding="utf-8")
cj = tmp / "cortes.json"
cj.write_text(json.dumps({"origem": "x.mp4", "cortes": [
    {"id": "c01", "inicio": st[1] + 0.9, "fim": en[5] - 0.5, "nota": 5, "gancho": "o jeito certo"},
    {"id": "c02", "inicio": st[4], "fim": en[6], "nota": 3}]}), encoding="utf-8")
r = L.conferir_cortes_longos(str(cj), str(pj), min_s=8)
d = json.loads(cj.read_text(encoding="utf-8")); c = {x["id"]: x for x in d["cortes"]}
check("inicio_original" in c["c01"] and c["c01"]["qualidade"]["nota"] >= 85, f"c01 encaixado e com nota boa: {c['c01']['inicio']}–{c['c01']['fim']} {c['c01']['qualidade']}")
check("c02" in r["sobrepostos"] and any("sobrepõe" in p for p in c["c02"]["qualidade"]["problemas"]), f"c02 (nota menor) sobreposto fica marcado para sair: {r['sobrepostos']}")
check(d["qualidade_conjunto"]["encaixados"] >= 1 and d["cortes"][0]["id"] == "c01", "conjunto com resumo e ordenado por nota")

# --- propor_cortes_longos traz a qualidade em cada candidato
longa = fala([(f, 1.5 if i % 2 else 0.4) for i, (f, _) in enumerate(frs * 6)])
pj2 = tmp / "longa.json"; pj2.write_text(json.dumps({"palavras": longa}), encoding="utf-8")
pr = L.propor_cortes_longos(str(pj2), str(tmp / "cand.json"), n=3, min_s=20, max_s=60)
check(pr["candidatos"] and all("qualidade" in x and x["qualidade"]["nota"] >= 70 for x in pr["candidatos"]), f"candidatos com nota de qualidade: {[x['qualidade']['nota'] for x in pr['candidatos']]}")

# --- catálogo de efeitos (inventários prontos, sem Gemini)
dirf = EF._dir()
for i, efs in enumerate([[("camera", "Zoom de impacto", "punch"), ("texto", "Selo carimbo verde", "nenhum"), ("texto", "Título 3D", "parcial:manchete")],
                         [("texto", "Selo carimbo verde", "nenhum"), ("som", "Whoosh", "whoosh")]]):
    (dirf / f"v{i}.json").write_text(json.dumps({"id": f"v{i}", "titulo": f"V{i}", "assinatura": ["x"], "efeitos": [
        {"familia": f, "nome": n, "inicio": 1.0, "fim": 2.0, "vezes": 1, "como": "pop", "equivalente": eq, "diferenca": "sombra 3D" if eq.startswith("parcial") else "",
         "dificuldade": "facil", "impacto": "alto"} for f, n, eq in efs]}), encoding="utf-8")
cat = EF.catalogo()
check(cat["videos"] == 2 and cat["faltam"][0]["nome"] == "Selo carimbo verde" and cat["faltam"][0]["videos"] == 2, f"o que falta, do mais usado: {[(x['nome'], x['videos']) for x in cat['faltam']]}")
man = next(x for x in cat["temos"] if x["recurso"] == "manchete")
check(man["parcial"] == 1 and man["diferencas"][0]["diferenca"] == "sombra 3D", "parcial aparece com a diferença")
check(next(x for x in cat["temos"] if x["recurso"] == "punch")["igual"] == 1, "igual conta como já temos")

print(f"\n{len(FALHAS)} falha(s)"); sys.exit(1 if FALHAS else 0)
