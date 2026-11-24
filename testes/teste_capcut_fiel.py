"""CapCut fiel (12/11/2026): rascunho do CapCut a partir do projeto salvo da montagem. Isolado: projeto sintético e pasta de rascunhos temporária
com um cache de efeitos falso (nada toca o CapCut real). Sem render (renderizar=False), exceto o teste curto da camada transparente no fim.
Rodar: ~/.venvs/editor-gs/Scripts/python -X utf8 -I testes/teste_capcut_fiel.py [--sem-render]"""
import json, sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import capcut_fiel as cf, capcut  # noqa: E402
from editor_video.util import FFMPEG, rodar, info_midia  # noqa: E402

FALHAS = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: FALHAS.append(msg)

tmp = Path(tempfile.mkdtemp(prefix="capcut-fiel-"))
drafts = tmp / "User Data" / "Projects" / "com.lveditor.draft"; drafts.mkdir(parents=True)
# cache falso: o CapCut "já usou" a Infinito 2 (giro) num projeto qualquer
efeito = tmp / "User Data" / "Cache" / "effect" / "7037372139221029377" / "abc123"; efeito.mkdir(parents=True)
(drafts / "Projeto antigo").mkdir()
(drafts / "Projeto antigo" / "draft_content.json").write_text(json.dumps({"materials": {"transitions": [
    {"id": "X", "type": "transition", "name": "Infinito 2", "effect_id": "7037372139221029377", "resource_id": "7037372139221029377", "duration": 600000, "path": "velho"}]}}), encoding="utf-8")
(tmp / "User Data" / "Cache" / "effect" / "6763470111253729803" / "anim1").mkdir(parents=True)
(drafts / "Projeto com texto").mkdir()
(drafts / "Projeto com texto" / "draft_content.json").write_text(json.dumps({"materials": {"material_animations": [{"id": "A", "type": "sticker_animation", "animations": [
    {"id": "6763470111253729803", "type": "in", "start": 0, "duration": 500000, "path": "velho", "resource_id": "6763470111253729803", "name": "Deslizar para cima",
     "material_type": "sticker", "category_id": "ruchang_fav"}]}]}}), encoding="utf-8")
(drafts / "root_meta_info.json").write_text(json.dumps({"all_draft_store": []}), encoding="utf-8")

final = tmp / "saida" / "final_9x16.mp4"; d = tmp / "saida" / "_projeto" / "final_9x16"; (d / "midia" / "render").mkdir(parents=True)
rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=6", "-f", "lavfi", "-i", "sine=f=330:d=6",
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "midia" / "render" / "abc.mp4")])
trilha = tmp / "trilha.wav"
rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:d=4", str(trilha)])
(d / "legenda.ass").write_text("[Script Info]\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
                               "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                               "Style: Legenda,Inter ExtraBold,72,&H001596F7,&H00FFFFFF,&H00210900,&H80210900,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,230,1\n\n"
                               "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
                               "Dialogue: 0,0:00:00.50,0:00:01.70,Legenda,,0,0,0,,{\\k40}Olha {\\k30}só {\\k50}isso\n"
                               "Dialogue: 0,0:00:01.60,0:00:03.00,Legenda,,0,0,0,,{\\k40}Webcam {\\k100}pronta\n", encoding="utf-8")
props = {"video": "abc.mp4", "duracao_s": 6.0, "fps": 30, "largura": 360, "altura": 640, "segmentos": [{"inicio": 0.5, "fim": 1.7, "texto": "a"}, {"inicio": 2.0, "fim": 3.0, "texto": "b"}],
         "cortes_s": [], "zoom": {"ativo": False, "fator": 1, "alternar": False}, "clarao": {"ativo": False, "duracao_s": 0.2, "opacidade": 0.8},
         "frase_impacto": None, "tela_final": {"ativo": True, "duracao_s": 1.0, "titulo": "Fim", "destaque": "", "cta": "Siga", "marca": "@gs"},
         "camera": {"planos": [{"inicio": 0, "fim": 2, "z0": 1.0, "z1": 1.1, "entrada": "seco", "dur": 0},
                               {"inicio": 2, "fim": 4, "z0": 1.2, "z1": 1.2, "entrada": "giro", "dur": 0.1},
                               {"inicio": 4, "fim": 6, "z0": 1.0, "z1": 1.0, "entrada": "deslize", "dur": 0.1}], "origem": {"x": 0.5, "y": 0.45}},
         "grafismos": [{"tipo": "pilula", "texto": "OBS", "inicio": 1.0, "fim": 2.0, "posicao": "peito"}],
         "sfx": [{"arquivo": "pop-01.wav", "inicio": 1.0, "volume": 0.3}, {"arquivo": "pop-02.wav", "inicio": 1.03, "volume": 0.3}],
         "estilo": {"cor_destaque": "#F79615", "cor_fundo": "#000921", "cor_texto": "#FFFFFF", "fonte_titulo": "Inter", "fonte_texto": "Inter"}, "barra_progresso": True}
(d / "projeto.json").write_text(json.dumps({"versao": 1, "video_final": final.name, "formato": "9x16", "props": props,
                                            "acabamento": {"crf": 20, "legenda": True, "trilha": str(trilha), "trilha_volume_db": -20}}), encoding="utf-8")

# legenda ASS com karaokê vira tempo por palavra
fr = cf.frases_ass(d / "legenda.ass")
check(len(fr) == 2 and [p["palavra"] for p in fr[0]["palavras"]] == ["Olha", "só", "isso"] and abs(fr[0]["palavras"][1]["inicio"] - 0.9) < 0.01, "ASS com \\k: frases e tempo de cada palavra")
check(cf.juntar([(0, 1), (1.1, 2), (5, 6)]) == [[0, 2], [5, 6]], "trechos próximos se juntam num clipe")
check(list(cf.catalogo_transicoes(drafts)) == ["Infinito 2"] and cf.catalogo_transicoes(drafts)["Infinito 2"]["path"].endswith("abc123"), "catálogo de transições lê os rascunhos e o cache")

r = cf.exportar_capcut_projeto(d, nome="Teste fiel", legenda="nativa", pasta_drafts=drafts, renderizar=False)
doc = json.loads((Path(r["projeto"]) / "draft_content.json").read_text(encoding="utf-8"))
tr = {}
for t in doc["tracks"]:
    tr.setdefault(t["type"], []).append(t)
base = tr["video"][0]["segments"]
check(r["n_segmentos"] == 3 and len(base) == 3, "um clipe por plano da câmera")
check(abs(doc["duration"] / 1e6 - 7.0) < 0.01, "duração inclui a tela final")
kf = {k["property_type"]: k for k in base[0]["common_keyframes"]}
check(set(kf) == {"KFTypeScaleX", "KFTypePositionX", "KFTypePositionY"} and kf["KFTypeScaleX"]["keyframe_list"][-1]["values"] == [1.1], "zoom 1,0 → 1,1 vira keyframe de escala e posição")
check(base[1]["clip"]["scale"]["x"] == 1.2 and not base[1]["common_keyframes"], "plano parado: escala fixa, sem keyframe")
check(abs(base[1]["clip"]["transform"]["y"] - (-2 * 0.2 * 0.05)) < 1e-6, "zoom em torno da origem da câmera desloca o quadro")
trs = {m["id"]: m for m in doc["materials"]["transitions"]}
check([trs[x]["name"] for x in base[0]["extra_material_refs"] if x in trs] == ["Infinito 2"] and not any(x in trs for x in base[1]["extra_material_refs"]),
      "giro → Infinito 2 no clipe de antes; corte seco sem transição")
check(any("deslize" in a for a in r["avisos"]), "transição sem equivalente no cache vira aviso, não transição genérica")
txts = {m["id"]: m for m in doc["materials"]["texts"]}
leg_t = next(t for t in tr["text"] if txts[t["segments"][0]["material_id"]]["type"] == "subtitle")
s0, s1 = leg_t["segments"][0]["target_timerange"], leg_t["segments"][1]["target_timerange"]
check(r["n_legendas"] == 2 and s0["start"] == 500000, "legenda nativa: uma caixa por frase no tempo certo")
check(s0["start"] + s0["duration"] <= s1["start"], "frases que se sobrepõem no ASS não se sobrepõem na faixa do CapCut")
lm = txts[leg_t["segments"][0]["material_id"]]; txt = lm["words"]
check(txt["text"] == ["Olha", " ", "só", " ", "isso"] and txt["start_time"][2] == 400, "karaokê do CapCut com o tempo de cada palavra")
st = json.loads(lm["content"])["styles"][0]
check(lm["font_path"].endswith("fontes/Inter-ExtraBold.ttf") and Path(lm["font_path"]).exists() and st["font"]["path"] == lm["font_path"], "legenda nativa com a fonte do ASS copiada para o rascunho")
check(st["fill"]["content"]["solid"]["color"] == [1.0, 1.0, 1.0] and lm["ktv_color"] == "#F79615" and st["strokes"][0]["content"]["solid"]["color"][2] > 0.1,
      "cor do texto = cor antes do destaque (branco), destaque em ktv_color, contorno marinho")
check(lm["check_flag"] & 8 and lm["check_flag"] & 32 and 0.07 < lm["border_width"] < 0.1 and lm["has_shadow"], "contorno e sombra ligados (check_flag 8|32), espessura proporcional à letra")
y = leg_t["segments"][0]["clip"]["transform"]["y"]
check(-0.8 < y < -0.65 and 13 < st["size"] < 16, f"posição na altura da entrega (y={y}) e tamanho ({st['size']})")
# grafismo pílula → texto nativo com fundo e animação de entrada do cache
gt = next(t for t in tr["text"] if txts[t["segments"][0]["material_id"]]["type"] == "text")
gm = txts[gt["segments"][0]["material_id"]]
an = next(m for m in doc["materials"]["material_animations"] if m["id"] in gt["segments"][0]["extra_material_refs"])
check(r["grafismos_nativos"] == ["pilula"] and json.loads(gm["content"])["text"] == "OBS" and gm["check_flag"] & 16 and gm["background_color"] == "#F79615",
      "pílula vira texto nativo (caixa alta, fundo laranja)")
check([a["name"] for a in an["animations"]] == ["Deslizar para cima"] and an["animations"][0]["path"].endswith("anim1"), "animação de entrada nativa do cache")
check(gt["segments"][0]["target_timerange"]["start"] == 1000000, "texto do grafismo no tempo do grafismo")
# barra de progresso: clipe próprio (imagem) com keyframe de posição
nomes_v = {m["id"]: m["material_name"] for m in doc["materials"]["videos"]}
barra = [t for t in tr["video"] if any(nomes_v.get(sg["material_id"]) == "barra_progresso.png" for sg in t["segments"])]
kfb = {k["property_type"]: k for k in barra[0]["segments"][0]["common_keyframes"]} if barra else {}
check(r["barra_progresso"] and barra and [k["values"][0] for k in kfb["KFTypePositionX"]["keyframe_list"]] == [-2.0, 0.0], "barra de progresso num clipe próprio, enchendo da esquerda")
check(r["base"].get("volume") and base[0]["volume"] == r["base"]["volume"]["volume"] != 1.0, f"voz da base no volume de −16 LUFS ({r['base'].get('volume')})")
# legenda nativa com destaque: uma caixa por palavra, a palavra falada em laranja
rd = cf.exportar_capcut_projeto(d, nome="Teste destaque", legenda="nativa_destaque", pasta_drafts=drafts, renderizar=False)
docd = json.loads((Path(rd["projeto"]) / "draft_content.json").read_text(encoding="utf-8"))
subs = [m for m in docd["materials"]["texts"] if m["type"] == "subtitle"]
sty = [json.loads(m["content"])["styles"] for m in subs[:3]]
check(rd["n_legendas"] == 5 and [len(x) for x in sty] == [2, 2, 1] and sty[1][0]["range"] == [0, 7] and sty[1][0]["fill"]["content"]["solid"]["color"][0] > 0.9
      and sty[1][0]["fill"]["content"]["solid"]["color"][2] < 0.2, "destaque: uma caixa por palavra, falada em laranja")
# base no bruto: a EDL do slug bate com o vídeo cortado → clipes apontam para o bruto com o ponto de cada corte
bruto = tmp / "entrada" / "bruto.mp4"; bruto.parent.mkdir()
rodar([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=8", "-f", "lavfi", "-i", "sine=f=330:d=8",
       "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(bruto)])
(tmp / "saida" / "edl.json").write_text(json.dumps({"origem": str(bruto), "manter": [{"inicio": 0.0, "fim": 2.5}, {"inicio": 3.5, "fim": 7.0}]}), encoding="utf-8")
rb = cf.exportar_capcut_projeto(d, nome="Teste bruto", legenda="nenhuma", pasta_drafts=drafts, renderizar=False)
docb = json.loads((Path(rb["projeto"]) / "draft_content.json").read_text(encoding="utf-8"))
bb = docb["tracks"][0]["segments"]; src = [(round(x["source_timerange"]["start"] / 1e6, 2), round(x["target_timerange"]["start"] / 1e6, 2)) for x in bb]
check(rb["base"]["bruto"] == "bruto.mp4" and src == [(0.0, 0.0), (2.0, 2.0), (3.5, 2.5), (5.0, 4.0)], f"base no bruto: corte da EDL dentro do plano vira 2 clipes, source no bruto ({src})")
check(abs(bb[1]["clip"]["scale"]["x"] - 1.2) < 1e-6 and abs(bb[2]["clip"]["scale"]["x"] - 1.2) < 1e-6, "zoom do plano continua nos dois pedaços")
check(cf.pedacos_no_bruto(0, 6, [(1, 2), (5, 10)]) == [(0, 1, 1), (1, 6, 5)], "mapa do tempo cortado para o bruto")
aud = tr["audio"]
check(r["n_sfx"] == 2 and len(aud) == 3, "efeitos que se sobrepõem vão para faixas separadas + faixa da trilha")
vol = aud[-1]["segments"][0]["common_keyframes"][0]
check(vol["property_type"] == "KFTypeVolume" and min(k["values"][0] for k in vol["keyframe_list"]) < max(k["values"][0] for k in vol["keyframe_list"]), "trilha abaixa sob a fala (ducking por keyframe)")
check(len(aud[-1]["segments"]) == 2, "trilha curta repete até o fim")
check(any(f["type"] == "audio_fade" for f in doc["materials"]["audio_fades"]), "trilha com fade")
check(r["registrado_no_indice"] and json.loads((drafts / "root_meta_info.json").read_text(encoding="utf-8"))["all_draft_store"][-1]["draft_name"] == "Teste fiel", "entra no índice de rascunhos")

# exportador antigo: sem a transição genérica em todos os cortes
edl = tmp / "edl.json"; edl.write_text(json.dumps({"manter": [{"inicio": 0, "fim": 2}, {"inicio": 3, "fim": 5}]}), encoding="utf-8")
r0 = capcut.exportar_capcut(str(d / "midia" / "render" / "abc.mp4"), "Teste antigo", edl_json=str(edl), pasta_drafts=str(drafts), legenda=False)
doc0 = json.loads((Path(r0["pasta_wsl"]) / "draft_content.json").read_text(encoding="utf-8"))
check(not doc0["materials"].get("transitions"), "exportador antigo: cortes secos (antes punha Infinito 2 em todos)")

# captura por diff: o que o Raphael mudar à mão (ex.: karaokê com cor de destaque) aparece como campo alterado do texto
dep = json.loads(json.dumps(doc)); tid = doc["materials"]["texts"][0]["id"]; dep["materials"]["texts"][0]["ktv_color"] = "#00FF00"
dep["materials"].setdefault("material_animations", []).append({"id": "NOVA", "type": "sticker_animation", "animations": [{"name": "Karaokê"}]})
dif = cf.diff_rascunhos(doc, dep)
check(dif["alterados"]["texts"][tid]["ktv_color"]["depois"] == "#00FF00" and dif["novos"]["material_animations"][0]["id"] == "NOVA", "diff de captura: campo alterado e material novo")

if "--sem-render" not in sys.argv:  # camada transparente de verdade (Remotion → MOV PNG com alfa)
    from editor_video import acabamento as a
    links = a.ligar_midia_projeto(d)
    try:
        mov = a.renderizar_remotion_alpha("Montagem", {**props, "duracao_s": 2.0, "tela_final": None, "camera": None, "camada": "graficos"}, tmp / "g.mov")
    finally:
        for l in links:
            l.unlink(missing_ok=True)
    i = info_midia(mov)
    import subprocess
    pix = subprocess.run([FFMPEG, "-hide_banner", "-i", str(mov)], capture_output=True, text=True).stderr   # "Video: png (...), rgba"
    pix = next((l.strip() for l in pix.splitlines() if "Video:" in l), "")
    check(abs(i["duracao_s"] - 2.0) < 0.15 and "png" in pix and "rgba" in pix, f"camada de grafismos em MOV PNG com alfa ({pix})")
print(f"\n{len(FALHAS)} falha(s)")
sys.exit(1 if FALHAS else 0)
