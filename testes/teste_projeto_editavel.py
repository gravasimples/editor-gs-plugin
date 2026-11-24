"""Projeto editável (12/11/2026): montar_remotion guarda props + mídias em _projeto/<final>/ e rerenderizar_projeto refaz a entrega a partir dali,
com props editadas. Isolado: vídeo sintético numa pasta temporária; renderiza de verdade (Remotion), ~1–2 min.
Rodar: ~/.venvs/editor-gs/Scripts/python -X utf8 -I testes/teste_projeto_editavel.py"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import acabamento as a  # noqa: E402
from editor_video.util import FFMPEG, info_midia, rodar  # noqa: E402

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="projeto-teste-"))
src = tmp / "bruto.mp4"
rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30:duration=3", "-f", "lavfi", "-i", "sine=f=330:d=3",
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)])
saida = tmp / "saida" / "final_9x16.mp4"
r = a.montar_remotion(str(src), str(saida), formato="9x16", resolucao="720p" if ("9x16", "720p") in a.RES else "1080p", tela_final=False, zoom=False, clarao=False)
d = a.pasta_projeto(saida)
check(r.get("projeto") and (d / "projeto.json").exists(), "projeto.json salvo ao lado da entrega")
proj = json.loads((d / "projeto.json").read_text(encoding="utf-8")) if (d / "projeto.json").exists() else {}
check((d / "midia" / "render" / proj.get("props", {}).get("video", "?")).exists(), "vídeo base guardado em midia/render com o nome das props")
check(not any((a.REMOTION / "public" / "render").glob(proj.get("props", {}).get("video", "nada") + "*")) if proj else False, "public/render limpo depois do render")
props = {**proj["props"], "clarao": {"ativo": True, "duracao_s": 0.22, "opacidade": 0.85}, "cortes_s": [1.5]}
saida2 = tmp / "saida" / "final_9x16_v2.mp4"
r2 = a.rerenderizar_projeto(d, str(saida2), props=props)
check(saida2.exists() and abs(info_midia(saida2)["duracao_s"] - info_midia(saida)["duracao_s"]) < 0.2, f"rerender com props editadas ({r2.get('tempo_s')} s)")
check(not any(p.name.endswith("-remotion.mp4") for p in (a.REMOTION / "public" / "render").iterdir()), "sem intermediário esquecido em public/render")

# ---- fase 2 (12/11/2026): EDL editável (aparar/reordenar trechos) e troca do estilo da legenda ----
sys.path.insert(0, str(RAIZ))
from editor_video import cortes as ct, legenda as lg  # noqa: E402
from servico import editor_manual as edm  # noqa: E402
bruto = tmp / "entrada_bruto.mp4"
rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=30:duration=6", "-f", "lavfi", "-i", "sine=f=440:d=6",
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(bruto)])
txt = "um dois tres quatro cinco seis sete oito nove dez onze doze".split()
pal_b = {"palavras": [{"palavra": w, "inicio": round(0.1 + 0.48 * i, 2), "fim": round(0.1 + 0.48 * i + 0.4, 2)} for i, w in enumerate(txt)],
         "segmentos": [{"inicio": 0.1, "fim": 5.9, "texto": " ".join(txt)}]}
(tmp / "palavras.json").write_text(json.dumps(pal_b), encoding="utf-8")
edl = {"origem": str(bruto), "palavras_json": str(tmp / "palavras.json"), "duracao_original_s": 6.0, "manter": [{"inicio": 0.0, "fim": 2.5}, {"inicio": 3.0, "fim": 5.9}]}
(tmp / "edl.json").write_text(json.dumps(edl), encoding="utf-8")
est_padrao = json.loads((RAIZ / "estilos" / "padrao.json").read_text(encoding="utf-8"))
rc = ct.cortar_e_legendar(str(bruto), str(tmp / "palavras.json"), str(tmp / "edl.json"), str(tmp / "saida" / "cortado.mp4"), str(tmp / "saida" / "palavras_cortado.json"),
                          formatos="9x16", estilo=est_padrao)
saida3 = tmp / "saida" / "final_edl.mp4"
a.montar_remotion(rc["video"], str(saida3), palavras_json=rc["palavras_json"], edl_json=str(tmp / "edl.json"), legenda_ass=rc["legendas"]["9x16"]["ass"], formato="9x16",
                  resolucao="720p" if ("9x16", "720p") in a.RES else "1080p", tela_final=False, zoom=False, clarao=False, sfx=False, transicoes="auto")
d3 = a.pasta_projeto(saida3); pj3 = json.loads((d3 / "projeto.json").read_text(encoding="utf-8"))
check((pj3.get("edl") or {}).get("bruto") == str(bruto) and len(pj3["edl"]["manter"]) == 2 and (d3 / "palavras_bruto.json").exists(), "projeto guarda o bruto, a EDL e as palavras do bruto")
info3 = edm.edl_info(d3, pj3)
check(info3["disponivel"] and info3.get("tem_palavras"), f"EDL disponível para aparar ({info3.get('motivo')})")
atual = edm.estilo_legenda_atual(d3, pj3)
check(atual["modo"] == "ass" and bool(atual["legenda"].get("cor_destaque")), f"estilo atual reconhecido ({atual['id']})")
estilos = edm.estilos_legenda()
check("karaoke-pop" in [e["id"] for e in estilos] and any(e["cinetica"] for e in estilos), f"biblioteca de estilos de legenda ({len(estilos)})")
rw = edm._remapear(pal_b["palavras"], [{"inicio": 3.0, "fim": 5.9}, {"inicio": 0.0, "fim": 2.5}])
check([w["palavra"] for w in rw][:2] == ["sete", "oito"] and all(x["fim"] <= y["inicio"] + 1e-6 for x, y in zip(rw, rw[1:])), "reordenar trechos leva as palavras junto, na ordem nova")
nova = [{"id": 0, "inicio": 0.0, "fim": 2.5}, {"id": 1, "inicio": 3.0, "fim": 4.9}]  # 2º trecho perde 1 s do fim
pv = edm.previa_legenda(d3, nova, "karaoke-pop", None)
n_pv = sum(len(l["palavras"]) for l in pv["linhas"])
check(0 < n_pv < len(txt) and pv["estilo"].get("animacao") == "pop" and all(w["texto"].isupper() for l in pv["linhas"] for w in l["palavras"]), f"prévia da legenda na EDL nova e no estilo novo ({n_pv} palavras)")
pv2 = edm.previa_legenda(d3, nova, "cinetica-onda", None)
check(bool(pv2["cinetica"]) and pv2["cinetica"]["animacao"] == "onda", "prévia da legenda cinética")
fr = edm.frases(d3 / "legenda.ass"); corr = {0: " ".join(["Uno"] + fr[0]["texto"].split()[1:])}
props_ed = {**pj3["props"], "duracao_s": 4.4}  # o editor manda as props já remapeadas; o servidor troca vídeo, duração real e legenda
pr, avisos, refeita = edm.preparar_edl_e_legenda(d3, props_ed, nova, "karaoke-pop", corr)
check(refeita and pr["video"] != pj3["props"]["video"] and abs(pr["duracao_s"] - 4.4) < 0.1, f"bruto recortado pela EDL nova ({pr['duracao_s']} s; avisos {avisos})")
ass_txt = (d3 / "legenda.ass").read_text(encoding="utf-8")
cab, _ = lg._estilo_ass(edm._bloco_estilo("karaoke-pop"), "9x16")
check(next(l for l in cab.splitlines() if l.startswith("Style:")) in ass_txt, "legenda refeita no estilo escolhido")
check("UNO" in ass_txt and "ONZE" not in ass_txt and "DOZE" not in ass_txt, "correção levada junto e palavras do trecho aparado fora da legenda")
pj3b = json.loads((d3 / "projeto.json").read_text(encoding="utf-8"))
check(pj3b["edl"]["manter"][1]["fim"] == 4.9 and pj3b["legenda_estilo"]["id"] == "karaoke-pop", "projeto.json com a EDL e o estilo novos")
saida4 = tmp / "saida" / "final_edl_editado_v1.mp4"
r4 = a.rerenderizar_projeto(d3, str(saida4), props=pr)
check(saida4.exists() and abs(info_midia(saida4)["duracao_s"] - pr["duracao_s"]) < 0.2, f"render pela EDL editada ({r4.get('duracao_s')} s em {r4.get('tempo_s')} s)")
pr2, _, ref2 = edm.preparar_edl_e_legenda(d3, pr, None, "cinetica-tipografica", None)
check(ref2 and (pr2.get("legenda_cinetica") or {}).get("animacao") == "tipografica" and not (d3 / "legenda.ass").exists(), "troca para legenda cinética (a ASS vai para o histórico)")
print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
