"""CapCut fiel (12/11/2026): projeto editável do CapCut a partir do projeto salvo da montagem (saida/<slug>/_projeto/<final>/projeto.json).

Formatos capturados por diff do projeto "Editor GS - referencia" editado à mão no CapCut 9.7.1 (modelos/capcut-9.7-recursos.json).
Camadas, de baixo para cima:
- base: o vídeo cortado em planos, com o zoom em keyframe (escala + posição) e a transição do próprio CapCut na troca de plano;
- b-roll em tela cheia: clipe próprio com zoom lento;
- grafismos e cartelas: um MOV PNG transparente (o CapCut ignora o alfa do ProRes 4444 e do WebM, mas respeita MOV PNG), um clipe por trecho;
- legenda: MOV PNG idêntico à entrega, ou texto nativo do CapCut (editável), uma caixa por frase com tempo por palavra;
- efeitos sonoros (clipes de áudio com o volume da montagem) e trilha (volume com keyframes de ducking sob a fala, fade de entrada e saída).
O exportador antigo (capcut.exportar_capcut) punha a transição "Infinito 2" em todos os cortes porque ela veio no modelo; aqui transição só entra onde o plano pede."""
import copy, json, math, os, re, shutil, time, uuid
from pathlib import Path
from .util import info_midia, rodar, ErroFerramenta, FFMPEG
from .capcut import MODELO, DRAFTS_PADRAO, US, _uid, _win

RECURSOS = Path(__file__).resolve().parent / "modelos" / "capcut-9.7-recursos.json"
# entrada do plano (transicoes.py) → transições do CapCut, em ordem de preferência; só entra a que estiver no cache do CapCut
# (uma transição passa a existir no cache quando é aplicada uma vez em qualquer projeto desta máquina)
MAPA_TRANSICOES = {
    "punch": ["Zoom hiper com recolher", "Zoom 2"], "zoom_blur": ["Zoom hiper com recolher"], "tremor": ["Zoom hiper com recolher"],
    "luz": ["Brilho 2", "Dissolução gradual"], "flash": ["Brilho 2", "Flash", "Dissolução gradual"], "giro": ["Infinito 2", "Girar"],
    "deslize": ["Deslizar", "Empurrar", "Zoom hiper com recolher"], "dissolver": ["Dissolver", "Dissolução gradual", "Sobrepor"],
}
# entrada/saída dos grafismos (Grafismos.tsx) → animação de texto do CapCut (sticker_animation), também só as que estão no cache
MAPA_ANIM_TEXTO = {
    "in": {"mascara": ["Máquina de escrever", "Deslizar para cima"], "*": ["Deslizar para cima", "Máquina de escrever"]},
    "out": {"sobe": ["Deslizar para cima", "Deslizar para baixo"], "*": ["Deslizar para baixo"]},
}
# tamanho do texto do CapCut: o motor de texto desenha a letra com fontSize*300/72 px (script_segment_js do cache) numa tela de referência de 1080 px
# no lado menor (estimativa: conferir no CapCut com a entrega ao lado). A fonte do ASS mede a altura da linha (≈1,21 em na Inter).
PX_POR_TAMANHO = 300 / 72
EM_POR_LINHA_ASS = 1.21
ALVO_LUFS, ALVO_TP = -16.0, -1.5
RAIZ_FONTES = Path(__file__).resolve().parents[3] / "fontes"


def _cache_efeitos(drafts: Path) -> Path:
    return drafts.parents[1] / "Cache" / "effect"


def _caminho_efeito(cache: Path, effect_id: str):
    d = cache / str(effect_id)
    if not d.is_dir():
        return None
    subs = [s for s in d.iterdir() if s.is_dir() and not s.name.endswith("_tmp")]
    return str(subs[0]).replace("\\", "/") if subs else None


def catalogo_transicoes(drafts=None) -> dict:
    """Transições que o CapCut desta máquina já usou em algum projeto e que estão no cache: {nome: material}."""
    drafts = Path(drafts) if drafts else DRAFTS_PADRAO; cache = _cache_efeitos(drafts); cat = {}
    for f in list(drafts.glob("*/draft_content.json")) + list(drafts.glob("*/Timelines/*/draft_content.json")):
        try:
            mats = json.loads(f.read_text(encoding="utf-8")).get("materials", {})
        except Exception:  # noqa: BLE001
            continue
        for t in mats.get("transitions", []):
            nome = t.get("name"); ef = t.get("effect_id")
            if nome and ef and nome not in cat:
                p = _caminho_efeito(cache, ef)
                if p:
                    cat[nome] = {**t, "path": p}
    return cat


def _nova_pasta(drafts: Path, nome: str):
    nome_pasta = re.sub(r"[^\w\- ]+", "", nome).strip() or "EditorGS"
    pasta = drafts / nome_pasta
    if pasta.exists():
        nome_pasta = f"{nome_pasta} {time.strftime('%H%M%S')}"; pasta = drafts / nome_pasta
    pasta.mkdir(parents=True)
    return pasta, nome_pasta


def _ligar(origem: Path, pasta: Path) -> Path:
    destino = pasta / origem.name
    if not destino.exists():
        try:
            os.link(origem, destino)
        except OSError:
            shutil.copy2(origem, destino)
    return destino


def _gravar_rascunho(modelo, drafts, pasta, nome_pasta, doc, midias):
    """draft_content.json + draft_meta_info.json e a entrada no índice de rascunhos (root_meta_info.json, com cópia de segurança)."""
    (pasta / "draft_content.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    agora = int(time.time())
    meta = copy.deepcopy(modelo["meta"]); meta["draft_id"] = doc["id"]; meta["draft_name"] = nome_pasta
    meta["draft_fold_path"] = _win(pasta); meta["draft_root_path"] = _win(drafts); meta["draft_timeline_materials_size_"] = 0
    for k in ("tm_draft_create", "tm_draft_modified"):
        meta[k] = int(time.time() * US)
    meta["tm_duration"] = doc["duration"]
    meta["draft_materials"] = [{"type": 0, "value": [{
        "ai_group_type": "", "create_time": agora, "duration": m["duration"], "enter_from": 0, "extra_info": Path(m["path"]).name, "file_Path": m["path"],
        "height": m["height"], "id": str(uuid.uuid4()), "import_time": agora, "import_time_ms": int(time.time() * US), "item_source": 1, "md5": "",
        "metetype": "photo" if m["type"] == "photo" else "video", "roughcut_time_range": {"duration": -1, "start": -1}, "sub_time_range": {"duration": -1, "start": -1},
        "type": 0, "width": m["width"]} for m in midias]}]
    (pasta / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    idx = drafts / "root_meta_info.json"
    if not (idx.exists() and modelo.get("root_entry")):
        return False
    try:
        root = json.loads(idx.read_text(encoding="utf-8")); shutil.copy2(idx, drafts / "root_meta_info.json.editor-gs.bak")
        ent = copy.deepcopy(modelo["root_entry"])
        ent.update({"draft_id": doc["id"], "draft_name": nome_pasta, "draft_fold_path": _win(pasta), "draft_root_path": _win(drafts),
                    "draft_json_file": _win(pasta) + "/draft_content.json", "draft_cover": "", "draft_timeline_materials_size_": 0,
                    "tm_draft_create": meta["tm_draft_create"], "tm_draft_modified": meta["tm_draft_modified"], "tm_duration": doc["duration"]})
        root.setdefault("all_draft_store", []).insert(0, ent)
        idx.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        return False


def frases_ass(ass) -> list:
    """Frases de uma legenda ASS palavra por palavra (uma linha Dialogue por palavra destacada, a mesma frase em linhas seguidas)."""
    def t(s):
        h, m, r = s.split(":"); return int(h) * 3600 + int(m) * 60 + float(r)
    linhas, frases_k = [], []
    for ln in Path(ass).read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("Dialogue:"):
            c = ln.split(",", 9)
            if len(c) == 10:
                ini, fim, bruto = t(c[1]), t(c[2]), c[9].replace("\\N", " ")
                texto = re.sub(r"\s+", " ", re.sub(r"\{[^}]*\}", "", bruto)).strip()
                ks = re.findall(r"\{[^}]*?\\k[fo]?(\d+)[^}]*\}([^{]*)", bruto)   # karaokê: {\kNN}palavra, NN em centésimos de segundo
                if ks:
                    cur = ini; pals = []
                    for cs, w in ks:
                        if w.strip():
                            pals.append({"palavra": w.strip(), "inicio": cur, "fim": min(fim, cur + int(cs) / 100)})
                        cur += int(cs) / 100
                    frases_k.append({"texto": texto, "inicio": ini, "fim": fim, "linhas": [(ini, fim)], "palavras": pals})
                    continue
                linhas.append((ini, fim, texto))
    if frases_k:
        return sorted(frases_k, key=lambda f: f["inicio"])
    frases = []
    for ini, fim, txt in sorted(linhas):
        if not txt:
            continue
        if frases and frases[-1]["texto"] == txt and ini - frases[-1]["fim"] < 0.05:
            frases[-1]["fim"] = fim; frases[-1]["linhas"].append((ini, fim))
        else:
            frases.append({"texto": txt, "inicio": ini, "fim": fim, "linhas": [(ini, fim)]})
    for f in frases:
        pals = f["texto"].split(" ")
        if len(f["linhas"]) == len(pals):
            f["palavras"] = [{"palavra": p, "inicio": a, "fim": z} for p, (a, z) in zip(pals, f["linhas"])]
        else:  # sem uma linha por palavra: divide o tempo da frase pelo tamanho das palavras
            tot = sum(len(p) for p in pals) or 1; cur = f["inicio"]; f["palavras"] = []
            for p in pals:
                dd = (f["fim"] - f["inicio"]) * len(p) / tot; f["palavras"].append({"palavra": p, "inicio": cur, "fim": cur + dd}); cur += dd
    return frases


def _cor_ass(c):
    """&HAABBGGRR do ASS → ('#RRGGBB', opacidade 0..1)."""
    h = str(c).strip().lstrip("&Hh").rstrip("&").rjust(8, "0")[-8:]
    a, b, g, r = h[0:2], h[2:4], h[4:6], h[6:8]
    return f"#{r}{g}{b}".upper(), round(1 - int(a, 16) / 255, 3)


ESTILO_PADRAO_ASS = ("Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
                     "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                     ["Legenda,Inter ExtraBold,72,&H001596F7,&H00FFFFFF,&H00210900,&H80210900,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,230,1"])


def estilo_ass(ass) -> dict:
    """Estilo 'Legenda' (ou o primeiro) de um ASS do motor (legenda.py): fonte, tamanho, cores, contorno, sombra, alinhamento e margens, na resolução do ASS."""
    txt = Path(ass).read_text(encoding="utf-8", errors="replace"); res = {"PlayResX": 1080, "PlayResY": 1920}
    for k in res:
        m = re.search(rf"^{k}:\s*(\d+)", txt, re.M)
        if m:
            res[k] = int(m.group(1))
    fmt = next((ln.split(":", 1)[1] for ln in txt.splitlines() if ln.startswith("Format:") and "PrimaryColour" in ln), None)
    estilos = [ln.split(":", 1)[1] for ln in txt.splitlines() if ln.startswith("Style:")]
    if not fmt or not estilos:   # ASS sem estilo (legendas antigas, testes): o padrão do motor (legenda.py, estilo Grava Simples)
        fmt, estilos = ESTILO_PADRAO_ASS
    campos = [x.strip() for x in fmt.split(",")]
    linha = next((s for s in estilos if s.split(",")[0].strip() == "Legenda"), estilos[0])
    v = dict(zip(campos, [x.strip() for x in linha.split(",", len(campos) - 1)]))
    num = lambda k, d=0.0: float(v.get(k) or d)
    prim, a_prim = _cor_ass(v.get("PrimaryColour", "&H00FFFFFF")); sec, _ = _cor_ass(v.get("SecondaryColour", "&H00FFFFFF"))
    cont, _ = _cor_ass(v.get("OutlineColour", "&H00000000")); somb, a_somb = _cor_ass(v.get("BackColour", "&H80000000"))
    return {"fonte": v.get("Fontname", "Inter"), "tamanho": num("Fontsize", 64), "cor_primaria": prim, "cor_secundaria": sec, "cor_contorno": cont,
            "cor_sombra": somb, "sombra_alpha": a_somb, "negrito": v.get("Bold", "0") not in ("0", ""), "espaco": num("Spacing"),
            "caixa": v.get("BorderStyle", "1") == "3", "contorno": num("Outline"), "sombra": num("Shadow"), "alinhamento": int(num("Alignment", 2)),
            "margem_l": num("MarginL"), "margem_r": num("MarginR"), "margem_v": num("MarginV"), "res_x": res["PlayResX"], "res_y": res["PlayResY"],
            "karaoke": bool(re.search(r"^Dialogue:.*\\k[fo]?\d", txt, re.M))}


def achar_fonte(nome, pastas=None):
    """Arquivo .ttf/.otf da pasta de fontes do motor pelo nome da fonte do ASS ('Inter ExtraBold', 'Poppins Bold') ou do estilo ('InterGS' = Inter 800)."""
    from PIL import ImageFont
    pastas = [Path(p) for p in (pastas or [RAIZ_FONTES])]
    norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    alvo = norm(nome)
    if alvo in ("intergs", "inter800", "interextrabold", ""):
        alvo = "interextrabold"
    achados = {}
    for p in pastas:
        for f in sorted(list(p.glob("*.ttf")) + list(p.glob("*.otf"))):
            try:
                fam, est = ImageFont.truetype(str(f), 12).getname()
            except Exception:  # noqa: BLE001
                continue
            for chave in (norm(f"{fam}{est}"), norm(fam) if norm(est) in ("regular", "") else None, norm(f.stem)):
                if chave:
                    achados.setdefault(chave, f)
    return achados.get(alvo) or achados.get(alvo + "regular") or next((f for k, f in achados.items() if k.startswith(alvo)), None)


def _rgb(cor):
    c = str(cor).lstrip("#")[:6]
    return [round(int(c[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)]


def material_texto(modelo, texto, fonte, tamanho, cor, faixas=None, contorno=None, sombra=None, fundo=None, alinhamento=1, largura_max=0.82, tipo="text", ktv=None):
    """Material de texto do CapCut (formato do 9.x: content.styles com fill/strokes/shadows por faixa, campos espelhados no material).
    faixas = [(ini, fim, cor)] em caracteres (palavras destacadas); contorno = (cor, largura relativa à letra); sombra = (cor, alfa, distância, ângulo);
    fundo = (cor, alfa, raio) para pílulas. Formatos conferidos nos rascunhos desta máquina (strokes, shadows, check_flag 7|8 contorno|32 sombra)."""
    tm = copy.deepcopy(modelo["text_material"]); tm["id"] = _uid(); tm["name"] = ""; tm["type"] = tipo
    fp = str(fonte).replace("\\", "/") if fonte else tm.get("font_path", "")
    def estilo(a, z, c):
        st = {"fill": {"alpha": 1.0, "content": {"render_type": "solid", "solid": {"alpha": 1.0, "color": _rgb(c)}}},
              "font": {"id": "", "path": fp}, "size": round(float(tamanho), 2), "range": [a, z]}
        if contorno:
            st["strokes"] = [{"content": {"render_type": "solid", "solid": {"alpha": 1.0, "color": _rgb(contorno[0])}}, "width": round(float(contorno[1]), 4), "mode": 0}]
        if sombra:
            st["shadows"] = [{"distance": float(sombra[2]), "content": {"render_type": "solid", "solid": {"alpha": float(sombra[1]), "color": _rgb(sombra[0])}},
                              "feather": 0.15, "angle": float(sombra[3]), "alpha": float(sombra[1]), "thickness_projection_angle": -45,
                              "thickness_projection_enable": False, "thickness_projection_distance": 0}]
        return st
    cortes = sorted({0, len(texto)} | {x for a, z, _ in (faixas or []) for x in (a, z) if 0 <= x <= len(texto)})
    def cor_em(i):
        return next((c for a, z, c in (faixas or []) if a <= i < z), cor)
    styles = [estilo(a, z, cor_em(a)) for a, z in zip(cortes, cortes[1:]) if z > a]
    c = {"text": texto, "styles": styles}
    tm["content"] = json.dumps(c, ensure_ascii=False); tm["base_content"] = tm["content"]; tm["recognize_text"] = texto if tipo == "subtitle" else ""
    tm.update({"font_path": fp, "font_name": Path(fp).stem if fp else "", "font_size": round(float(tamanho), 2), "text_color": cor.upper(), "alignment": alinhamento,
               "line_max_width": round(float(largura_max), 3), "use_effect_default_color": False, "words": {"start_time": [], "end_time": [], "text": []}})
    flag = 7
    if contorno:
        tm["border_color"] = contorno[0].upper(); tm["border_width"] = round(float(contorno[1]), 4); tm["border_alpha"] = 1.0; flag |= 8
    else:
        tm["border_color"] = ""
    if sombra:
        ang = math.radians(float(sombra[3]))
        tm.update({"has_shadow": True, "shadow_color": sombra[0].upper(), "shadow_alpha": float(sombra[1]), "shadow_distance": float(sombra[2]), "shadow_angle": float(sombra[3]),
                   "shadow_point": {"x": round(0.9 * math.cos(ang), 6), "y": round(0.9 * math.sin(ang), 6)}}); flag |= 32
    if fundo:
        tm.update({"background_color": fundo[0].upper(), "background_alpha": float(fundo[1]), "background_style": 1, "background_round_radius": float(fundo[2]),
                   "background_width": 0.14, "background_height": 0.14}); flag |= 16
    if ktv:
        tm["ktv_color"] = ktv.upper()
    tm["check_flag"] = flag
    return tm


def legenda_capcut(ass, W, H):
    """Estilo da legenda da entrega traduzido para o texto do CapCut: fonte (arquivo do motor), tamanho, cores, contorno, sombra, posição (transform y) e largura."""
    e = estilo_ass(ass); k = H / e["res_y"]; fs = e["tamanho"] * k; em = fs / EM_POR_LINHA_ASS
    tam = em / PX_POR_TAMANHO * (1080 / min(W, H))
    cor = e["cor_secundaria"] if e["karaoke"] else e["cor_primaria"]
    al = e["alinhamento"]; mv = e["margem_v"] * k
    if al in (7, 8, 9):
        cy = mv + fs / 2
    elif al in (4, 5, 6):
        cy = H / 2
    else:
        cy = H - mv - fs / 2
    contorno = (e["cor_contorno"], min(0.2, e["contorno"] * k / em)) if e["contorno"] > 0 and not e["caixa"] else None
    sombra = (e["cor_sombra"], e["sombra_alpha"], round(e["sombra"] * k / em * 100, 2), -45.0) if e["sombra"] > 0 and not e["caixa"] else None
    fundo = (e["cor_contorno"], e["sombra_alpha"] or 0.8, 0.3) if e["caixa"] else None
    largura = max(0.3, min(1.0, (W - (e["margem_l"] + e["margem_r"]) * W / e["res_x"]) / W))
    return {"fonte": achar_fonte(e["fonte"]), "nome_fonte": e["fonte"], "tamanho": round(tam, 2), "cor": cor, "destaque": e["cor_primaria"] if e["karaoke"] else None,
            "contorno": contorno, "sombra": sombra, "fundo": fundo, "y": round((H / 2 - cy) / (H / 2), 4), "largura": round(largura, 3),
            "alinhamento": {1: 0, 4: 0, 7: 0, 3: 2, 6: 2, 9: 2}.get(al, 1), "karaoke": e["karaoke"]}


def grafismo_texto(g, est, W, H):
    """Grafismo que é só texto (pílula, kicker, manchete simples) → parâmetros do texto nativo do CapCut, ou None (fica no MOV transparente).
    Medidas do Grafismos.tsx: zona peito começa em 54,5 % da altura, topo em 7,5 %, centro no meio acima da legenda; u = W/1080 no vertical."""
    if g.get("tela_cheia") or g.get("tipo") not in ("pilula", "kicker", "manchete") or not (g.get("texto") or "").strip():
        return None
    if g["tipo"] == "manchete" and (g.get("rotulo") or g.get("ondas") or g.get("caixa") or g.get("troca")):
        return None
    vertical = H > W; u = W / 1080 if vertical else H / 1080 * 0.85
    texto = str(g["texto"]).upper(); dest = est.get("cor_destaque", "#F79615"); fundo_cor = est.get("cor_fundo", "#000921"); branco = est.get("cor_texto", "#FFFFFF")
    if g["tipo"] == "pilula":
        px, cor, fundo, sombra, faixas = 46 * u, fundo_cor, (dest, 1.0, 1.0), None, []
        alt = px * (1 + 0.84)
    elif g["tipo"] == "kicker":
        px, cor, fundo, sombra, faixas = 30 * u, branco, ("#0B193D", 0.92, 1.0), None, []
        alt = px * (1 + 0.84)
    else:
        px, cor, fundo = 80 * u, branco, None; alt = px * 1.08; sombra = ("#000000", 0.55, 4.0, -90.0)
        alvo = {re.sub(r"[^\w]", "", w.lower()) for w in str(g.get("destaque") or "").split()}; faixas = []; i = 0
        for w in texto.split(" "):
            if w and re.sub(r"[^\w]", "", w.lower()) in alvo:
                faixas.append((i, i + len(w), dest))
            i += len(w) + 1
    zona = g.get("posicao") or "peito"
    if zona == "centro":
        cy = (H - H * 0.12) / 2
    else:
        cy = H * ((0.075 if vertical else 0.07) if zona == "topo" else (0.545 if vertical else 0.6)) + alt / 2
    tam = px / PX_POR_TAMANHO * (1080 / min(W, H))
    return {"texto": texto, "tamanho": round(tam, 2), "cor": cor, "faixas": faixas, "fundo": fundo, "sombra": sombra, "y": round((H / 2 - cy) / (H / 2), 4),
            "largura": 0.9, "fonte": achar_fonte("InterGS")}


def catalogo_animacoes_texto(drafts=None) -> dict:
    """Animações de texto (entrada/saída) que o CapCut desta máquina já usou e que estão no cache: {(tipo, nome): animação}."""
    drafts = Path(drafts) if drafts else DRAFTS_PADRAO; cache = _cache_efeitos(drafts); cat = {}
    for f in drafts.glob("*/draft_content.json"):
        try:
            mats = json.loads(f.read_text(encoding="utf-8")).get("materials", {})
        except Exception:  # noqa: BLE001
            continue
        for a in mats.get("material_animations", []):
            for x in a.get("animations") or []:
                chave = (x.get("type"), x.get("name"))
                if x.get("material_type") == "sticker" and chave[0] in ("in", "out") and chave not in cat:
                    p = _caminho_efeito(cache, x.get("resource_id") or x.get("id"))
                    if p:
                        cat[chave] = {**x, "path": p}
    return cat


def fonte_bruta(d: Path, props, edl_proj=None) -> dict | None:
    """Bruto + EDL que geraram o vídeo cortado da montagem (saida/<slug>/edl_ajustada.json ou edl.json), para a base do CapCut apontar ao bruto
    com o ponto de entrada/saída de cada corte (dá para estender o corte com a sobra). Só quando a soma dos trechos bate com a duração do vídeo
    e o bruto tem a mesma resolução do cortado (sem reenquadramento entre um e outro); senão None e a base usa o cortado."""
    slug = Path(d).parent.parent; dur_v = float(props["duracao_s"])
    ws = Path(d).parents[3] if len(Path(d).parents) > 3 else None
    fontes = []
    if (edl_proj or {}).get("bruto") and edl_proj.get("manter"):   # projeto.json com "edl" (editor manual, fase 2): é a referência certa
        fontes.append((Path(d) / "projeto.json", {"origem": edl_proj["bruto"], "manter": edl_proj["manter"]}))
    for nome in ("edl_ajustada.json", "edl.json"):
        try:
            fontes.append((slug / nome, json.loads((slug / nome).read_text(encoding="utf-8"))))
        except Exception:  # noqa: BLE001
            continue
    for f, edl in fontes:
        try:
            manter = [(float(m["inicio"]), float(m["fim"])) for m in edl.get("manter") or []]
        except Exception:  # noqa: BLE001
            continue
        if not manter or abs(sum(z - a for a, z in manter) - dur_v) > 0.08:
            continue
        orig = str(edl.get("origem") or ""); cands = [Path(orig)]
        m = re.search(r"/workspace/(.+)$", orig.replace("\\", "/"))
        if m and ws:
            cands.append(ws / m.group(1))
        if ws:
            cands.append(ws / "entrada" / slug.name / Path(orig.replace("\\", "/")).name)
        bruto = next((c for c in cands if str(c) not in ("", ".") and c.is_file()), None)
        if not bruto:
            continue
        try:
            ib = info_midia(bruto); ic = info_midia(Path(d) / "midia" / "render" / props["video"])
        except Exception:  # noqa: BLE001
            continue
        if (ib["largura"], ib["altura"]) != (ic["largura"], ic["altura"]) or ib["duracao_s"] < manter[-1][1] - 0.1 or bool(ib["tem_audio"]) != bool(ic["tem_audio"]):
            continue
        return {"bruto": bruto, "manter": manter, "edl": f}
    return None


def pedacos_no_bruto(a, z, manter):
    """Trecho [a, z] da linha do tempo cortada → [(ini_cortado, fim_cortado, ini_no_bruto)], um por trecho mantido da EDL que ele cruza."""
    out = []; acc = 0.0
    for ma, mz in manter:
        d = mz - ma; ia, iz = max(a, acc), min(z, acc + d)
        if iz - ia > 0.02:
            out.append((ia, iz, ma + (ia - acc)))
        acc += d
    return out


def volume_para_lufs(arq, alvo=ALVO_LUFS, pico=ALVO_TP):
    """Ganho linear que leva o áudio a −16 LUFS (o alvo da entrega) sem passar do pico de −1,5 dBTP (o CapCut não tem limitador). None sem áudio."""
    from .util import _loudnorm_medir
    try:
        m = _loudnorm_medir(arq, "", alvo, pico); i, tp = float(m["input_i"]), float(m["input_tp"])
    except Exception:  # noqa: BLE001
        return None
    if i < -60:
        return None
    g = min(alvo - i, pico - tp)
    return {"volume": round(max(0.1, min(6.0, 10 ** (g / 20))), 4), "lufs_antes": round(i, 1), "pico_antes": round(tp, 1), "ganho_db": round(g, 1)}


def barra_png(arq: Path, W, H, est):
    """Barra de progresso da Montagem (rodapé, altura max(5, 0,6 % da tela), degradê do destaque) como imagem da largura da tela."""
    from PIL import Image
    h = max(5, round(H * 0.006)); a = _rgb(est.get("cor_destaque", "#F79615")); b = _rgb("#E9760D")
    im = Image.new("RGBA", (W, h))
    for x in range(W):
        t = x / max(1, W - 1); im.paste(tuple(int(255 * (a[i] + (b[i] - a[i]) * t)) for i in range(3)) + (255,), (x, 0, x + 1, h))
    im.save(arq); return h


def juntar(trechos, folga=0.15):
    out = []
    for a, z in sorted(trechos):
        if out and a <= out[-1][1] + folga:
            out[-1][1] = max(out[-1][1], z)
        else:
            out.append([a, z])
    return out


def trechos_graficos(props, atraso, dur_v, total):
    """Trechos da linha do tempo final em que a camada de grafismos tem algo visível (cada um vira um clipe no CapCut)."""
    vin = props.get("vinheta") if (props.get("vinheta") or {}).get("ativo") else None
    tf = props.get("tela_final") if (props.get("tela_final") or {}).get("ativo") else None
    lay = props.get("layout") or {}
    ev = [(atraso + g["inicio"] - 0.05, atraso + g["fim"] + 0.4) for g in props.get("grafismos") or []]
    ev += [(atraso + c["inicio"], atraso + c["inicio"] + 2.6) for c in props.get("capitulos") or []]
    if not props.get("grafismos"):
        ev += [(atraso + k["inicio"], atraso + max(k["fim"], k["inicio"] + 0.6)) for k in props.get("palavras_chave") or []]
    if (props.get("frase_impacto") or {}).get("texto"):
        ev.append((atraso, atraso + float(props["frase_impacto"]["duracao_s"])))
    if (props.get("terco") or {}).get("texto"):
        ev.append((atraso + props["terco"]["inicio_s"], atraso + props["terco"]["inicio_s"] + props["terco"]["duracao_s"]))
    ev += [(atraso + b["inicio"], atraso + b["inicio"] + b["duracao_s"]) for b in props.get("broll") or [] if b.get("modo") == "janela"]
    if not props.get("camera") and (props.get("clarao") or {}).get("ativo"):
        dc = float(props["clarao"].get("duracao_s") or 0.2); ev += [(atraso + c - dc, atraso + c + dc) for c in props.get("cortes_s") or []]
    if vin:
        ev.append((0, atraso))
    if tf:
        ev.append((atraso + dur_v - 0.25, total))
    if props.get("barra_progresso") or lay.get("passos") or lay.get("cortinas_s"):
        ev.append((atraso, atraso + dur_v))
    return [(max(0.0, a), min(total, z)) for a, z in juntar(ev) if min(total, z) - max(0.0, a) > 0.05]


LEGENDAS = ("nativa", "nativa_destaque", "identica", "nenhuma")


def exportar_capcut_projeto(pasta_projeto, nome=None, legenda="nativa", pasta_drafts=None, renderizar=True, base_bruto=True):
    """Cria o rascunho do CapCut fiel à entrega. legenda: "nativa" (padrão: texto do CapCut editável no estilo da entrega, uma caixa por frase),
    "nativa_destaque" (texto nativo com a palavra falada na cor de destaque: uma caixa por palavra, como o ASS), "identica" (camada transparente
    igual à entrega) ou "nenhuma". base_bruto: a base aponta para o bruto com o ponto de entrada/saída de cada corte (quando a EDL bate).
    renderizar=False pula os renders das camadas transparentes (teste rápido). Com render, leva de 1 a 4 min."""
    if legenda not in LEGENDAS:
        raise ErroFerramenta(f"legenda: {', '.join(LEGENDAS)}")
    from . import acabamento as acb, grafismos as grf
    t0 = time.monotonic(); d = Path(pasta_projeto)
    proj = json.loads((d / "projeto.json").read_text(encoding="utf-8")); props = proj["props"]; ac = proj.get("acabamento") or {}
    modelo = json.loads(MODELO.read_text(encoding="utf-8")); rec = json.loads(RECURSOS.read_text(encoding="utf-8"))
    drafts = Path(pasta_drafts) if pasta_drafts else DRAFTS_PADRAO
    if not drafts.exists():
        raise ErroFerramenta(f"Pasta de projetos do CapCut não encontrada: {drafts}")
    pasta, nome_pasta = _nova_pasta(drafts, nome or f"Editor GS - {str(proj.get('video_final') or d.name).rsplit('.', 1)[0]}")
    W, H, fps = int(props["largura"]), int(props["altura"]), float(props.get("fps") or 30)
    vin = props.get("vinheta") if (props.get("vinheta") or {}).get("ativo") else None
    tf = props.get("tela_final") if (props.get("tela_final") or {}).get("ativo") else None
    atraso = float(vin["duracao_s"]) if vin else 0.0; dur_v = float(props["duracao_s"])
    total = atraso + dur_v + (float(tf["duracao_s"]) if tf else 0.0)
    doc = copy.deepcopy(modelo["doc"]); doc["id"] = _uid(); doc["name"] = nome_pasta; doc["fps"] = fps
    doc["canvas_config"] = {"ratio": "original", "width": W, "height": H, "background": None}
    agora = int(time.time()); doc["create_time"] = agora; doc["update_time"] = agora
    mats = copy.deepcopy(modelo["materials_vazios"])
    for k in ("videos", "audios", "texts", "transitions", "audio_fades", "canvases"):
        mats.setdefault(k, [])
    midias, avisos, tracks = [], [], []

    def us(s):
        return int(round(s * US))

    def material(arq: Path, foto=False, alfa=False):
        m = copy.deepcopy(rec["video_material"]); m["id"] = _uid(); m["path"] = _win(arq); m["material_name"] = arq.name
        if foto:
            from PIL import Image
            with Image.open(arq) as im:
                m["width"], m["height"] = im.size
            m["type"] = "photo"; m["duration"] = 10_800_000_000; m["has_audio"] = False
        else:
            info = info_midia(arq)
            m["type"] = "video"; m["duration"] = us(info["duracao_s"]); m["width"] = info["largura"]; m["height"] = info["altura"]
            m["has_audio"] = bool(info["tem_audio"]) and not alfa
        mats["videos"].append(m); midias.append(m); return m

    def segmento(mat, src, dur, ini, render_index=0, canvas=None):
        s = copy.deepcopy(rec["video_segment"]); s["id"] = _uid(); s["material_id"] = mat["id"]
        s["source_timerange"] = {"start": us(src), "duration": us(dur)}; s["target_timerange"] = {"start": us(ini), "duration": us(dur)}
        s["render_index"] = render_index; s["common_keyframes"] = []; refs = []
        for k, m in rec["video_extras"].items():
            mm = copy.deepcopy(m); mm["id"] = _uid()
            if k == "canvases" and canvas:
                mm.update(canvas)
            mats.setdefault(k, []).append(mm); refs.append(mm["id"])
        s["extra_material_refs"] = refs; return s

    def keyframes(s, tipo, pontos):
        kf = copy.deepcopy(rec["keyframe"]); kf["id"] = _uid(); kf["property_type"] = tipo; base = kf["keyframe_list"][0]; kf["keyframe_list"] = []
        for off, val in pontos:
            k = copy.deepcopy(base); k["id"] = _uid(); k["time_offset"] = us(off); k["values"] = [val]; kf["keyframe_list"].append(k)
        s["common_keyframes"].append(kf)

    def trilha_video(segs, flag=0):
        t = copy.deepcopy(rec["video_track_sobreposicao"] if flag else modelo["video_track"]); t["id"] = _uid(); t["flag"] = flag; t["segments"] = segs
        return t

    def audio(arq: Path, ini, dur, vol=1.0, fade=None):
        m = copy.deepcopy(rec["audio_material"]); m["id"] = _uid(); m["path"] = _win(arq); m["name"] = arq.name; m["music_id"] = str(uuid.uuid4())
        m["local_material_id"] = str(uuid.uuid4()); m["duration"] = us(info_midia(arq)["duracao_s"]); mats["audios"].append(m)
        s = copy.deepcopy(rec["audio_segment"]); s["id"] = _uid(); s["material_id"] = m["id"]; s["volume"] = vol; s["last_nonzero_volume"] = vol or 1.0
        s["source_timerange"] = {"start": 0, "duration": us(dur)}; s["target_timerange"] = {"start": us(ini), "duration": us(dur)}; s["common_keyframes"] = []; refs = []
        for k, x in rec["audio_extras"].items():
            mm = copy.deepcopy(x); mm["id"] = _uid(); mats.setdefault(k, []).append(mm); refs.append(mm["id"])
        if fade:
            fm = {"id": _uid(), "fade_in_duration": us(fade[0]), "fade_out_duration": us(fade[1]), "fade_type": 0, "type": "audio_fade"}
            mats["audio_fades"].append(fm); refs.append(fm["id"])
        s["extra_material_refs"] = refs; return s

    def trilha_audio(segs):
        t = copy.deepcopy(rec["audio_track"]); t["id"] = _uid(); t["segments"] = segs; return t

    def texto_seg(tm, ini, dur, y, render_index=14000):
        seg = copy.deepcopy(modelo["text_segment"]); seg["id"] = _uid(); seg["material_id"] = tm["id"]; seg["render_index"] = render_index
        seg["target_timerange"] = {"start": us(ini), "duration": max(1, us(dur))}; seg["clip"]["transform"] = {"x": 0.0, "y": y}; refs = []
        for k, m in modelo["text_extras"].items():
            mm = copy.deepcopy(m); mm["id"] = _uid(); mats.setdefault(k, []).append(mm); refs.append(mm["id"])
        seg["extra_material_refs"] = refs; return seg

    def pasta_fontes():
        p = pasta / "fontes"; p.mkdir(exist_ok=True); return p

    def _transicao(segs, ent, pl):
        if not segs or ent == "seco":
            return
        nome_t = next((n for n in MAPA_TRANSICOES.get(ent, []) if n in cat), None)
        if nome_t:  # a transição fica no clipe de antes (é assim que o CapCut grava)
            tm = copy.deepcopy(cat[nome_t]); tm["id"] = _uid()
            tm["duration"] = us(max(0.25, min(float(pl.get("dur") or 0.13) * 3, 0.8, segs[-1]["target_timerange"]["duration"] / US * 0.5)))
            mats["transitions"].append(tm); segs[-1]["extra_material_refs"].append(tm["id"]); transicoes.append(f"{ent} → {nome_t}")
        else:
            avisos.append(f"transição '{ent}' sem equivalente no cache do CapCut: aplique uma vez a '{MAPA_TRANSICOES.get(ent, ['?'])[0]}' em qualquer projeto e exporte de novo")

    links = acb.ligar_midia_projeto(d) if renderizar else []
    n_planos = n_graf = n_leg = n_sfx = n_barra = 0; transicoes = []; info_base = {"bruto": None}; info_leg = {}; nativos_ok = []; nativos = []; avisos_anim = set()
    cat = catalogo_transicoes(drafts)
    vol_base = volume_para_lufs(d / "midia" / "render" / props["video"]) if (d / "midia" / "render" / props["video"]).exists() else None
    if vol_base:   # o volume do clipe no CapCut leva a voz a −16 LUFS, como a entrega (que passa pelo loudnorm)
        info_base["volume"] = vol_base
    try:
        # ── base
        lay = props.get("layout") or None
        complexo = bool(lay and (lay.get("composto") or any(b.get("modo") != "cheio" for b in lay.get("blocos") or [])))
        muda = bool(props.get("largura_origem") and props.get("altura_origem")) and ((props["largura_origem"] > props["altura_origem"]) != (W > H))
        if complexo and renderizar:
            base = acb.renderizar_remotion("Montagem", {**props, "camada": "base", "vinheta": None, "tela_final": None, "sfx": []}, str(pasta / "base_layout.mp4"))
            mb = material(Path(base)); sb = segmento(mb, 0, min(dur_v, mb["duration"] / US), atraso)
            if vol_base:
                sb["volume"] = sb["last_nonzero_volume"] = vol_base["volume"]
            tracks.append(trilha_video([sb])); n_planos = 1
            avisos.append("layout com tela/painel/aula: a base veio renderizada (o zoom desse trecho não fica editável)")
        else:
            cortado = d / "midia" / "render" / props["video"]
            fb = fonte_bruta(d, props, proj.get("edl")) if base_bruto else None
            if fb:   # a base aponta para o bruto: cada corte com o seu ponto de entrada/saída (estica no CapCut com a sobra)
                mv = material(_ligar(fb["bruto"], pasta)); manter = fb["manter"]; info_base["bruto"] = fb["bruto"].name; info_base["edl"] = fb["edl"].name
            else:
                mv = material(_ligar(cortado, pasta)); manter = [(0.0, dur_v)]
            canvas = {"type": "canvas_blur", "blur": 0.375} if muda else None   # vídeo deitado no vertical: fundo desfocado do próprio CapCut
            cam = (props.get("camera") or {}).get("planos") or []
            if not cam:  # sem câmera (montagens antigas): um plano por trecho entre cortes, com o zoom alternado
                zc = props.get("zoom") or {}; fator = float(zc.get("fator") or 1.0) if zc.get("ativo") else 1.0
                pts = [0.0] + [c for c in (props.get("cortes_s") or []) if 0 < c < dur_v] + [dur_v]
                cam = [{"inicio": a, "fim": z, "z0": fator if (zc.get("alternar") and i % 2) else 1.0, "entrada": "seco"} for i, (a, z) in enumerate(zip(pts, pts[1:]))]
            ori = (props.get("camera") or {}).get("origem") or {"x": 0.5, "y": 0.45}
            ox, oy = float(ori.get("x", 0.5)), float(ori.get("y", 0.45))
            def pos(zz):   # escala em torno da origem da câmera: deslocamento do centro em meias larguras/alturas do quadro (y do CapCut cresce para cima)
                return 2 * (zz - 1) * (0.5 - ox), -2 * (zz - 1) * (0.5 - oy)
            segs = []
            if len(manter) > 1:   # troca de plano a menos de 0,12 s de um corte da EDL encosta no corte (sem clipe de 2 ou 3 quadros no CapCut)
                acc, bordas = 0.0, []
                for ma, mz in manter[:-1]:
                    acc += mz - ma; bordas.append(acc)
                enc = lambda t: next((b for b in bordas if abs(b - t) < 0.12), t)
                cam = [{**pl, "inicio": enc(float(pl["inicio"])), "fim": enc(float(pl["fim"]))} for pl in cam]
            for pl in cam:
                a, z = float(pl["inicio"]), min(float(pl["fim"]), dur_v)
                if z - a < 0.04:
                    continue
                z0p = float(pl.get("z0") or 1); z1p = float(pl.get("z1") or z0p); ent = str(pl.get("entrada") or "seco")
                zoom_em = lambda t: z0p + (z1p - z0p) * (t - a) / (z - a)   # o zoom do plano é contínuo; se o plano cruza um corte da EDL, cada pedaço leva a sua parte
                for k, (pa, pz, src) in enumerate(pedacos_no_bruto(a, z, manter)):
                    s = segmento(mv, src, pz - pa, atraso + pa, canvas=canvas); z0 = round(zoom_em(pa), 4); z1 = round(zoom_em(pz), 4)
                    s["clip"]["scale"] = {"x": z0, "y": z0}; s["uniform_scale"] = {"on": True, "value": z0}; s["clip"]["transform"] = {"x": pos(z0)[0], "y": pos(z0)[1]}
                    if vol_base:
                        s["volume"] = vol_base["volume"]; s["last_nonzero_volume"] = vol_base["volume"]
                    if abs(z1 - z0) > 0.003:
                        keyframes(s, "KFTypeScaleX", [(0, z0), (pz - pa, z1)])
                        keyframes(s, "KFTypePositionX", [(0, pos(z0)[0]), (pz - pa, pos(z1)[0])]); keyframes(s, "KFTypePositionY", [(0, pos(z0)[1]), (pz - pa, pos(z1)[1])])
                    if k:   # corte da EDL dentro do plano: emenda seca, como na entrega
                        segs.append(s); continue
                    _transicao(segs, ent, pl)
                    segs.append(s)
            n_planos = len(segs); tracks.append(trilha_video(segs))
        # ── b-roll em tela cheia (a janela arredondada vai na camada de grafismos)
        segs = []
        for b in (b for b in props.get("broll") or [] if b.get("modo") != "janela"):
            arq = d / "midia" / "render" / b["arquivo"]
            if not arq.exists():
                avisos.append(f"b-roll sem arquivo no projeto: {b['arquivo']}"); continue
            mb = material(_ligar(arq, pasta), foto=not b.get("video"))
            s = segmento(mb, 0, float(b["duracao_s"]), atraso + float(b["inicio"]), render_index=11001 + len(segs))
            keyframes(s, "KFTypeScaleX", [(0, 1.0), (float(b["duracao_s"]), 1.08)]); segs.append(s)
        if segs:
            tracks.append(trilha_video(segs, flag=2))
        # ── barra de progresso: imagem do rodapé num clipe próprio, entrando da esquerda por keyframe de posição (editável, sem render)
        if props.get("barra_progresso"):
            hb = barra_png(pasta / "barra_progresso.png", W, H, props.get("estilo") or {})
            mbar = material(pasta / "barra_progresso.png", foto=True)
            s = segmento(mbar, 0, dur_v, atraso, render_index=11090); y = -(1 - hb / H)
            s["clip"]["transform"] = {"x": -2.0, "y": y}
            keyframes(s, "KFTypePositionX", [(0, -2.0), (dur_v, 0.0)]); keyframes(s, "KFTypePositionY", [(0, y), (dur_v, y)])
            tracks.append(trilha_video([s], flag=2)); n_barra = 1
        # ── grafismos que são só texto → texto nativo do CapCut com animação de entrada/saída nativa; o resto no MOV transparente
        est = props.get("estilo") or {}; graf = props.get("grafismos") or []; nativos, restantes = [], []
        if not lay:   # com layout (painel/coluna) a zona do grafismo muda: fica no MOV
            for g in graf:
                gt = grafismo_texto(g, est, W, H)
                (nativos if gt else restantes).append((g, gt))
        else:
            restantes = [(g, None) for g in graf]
        if nativos:
            anims = catalogo_animacoes_texto(drafts); pistas_txt = []
            for g, gt in nativos:
                fonte = _ligar(gt["fonte"], pasta_fontes()) if gt["fonte"] else None
                tm = material_texto(modelo, gt["texto"], fonte, gt["tamanho"], gt["cor"], faixas=gt["faixas"], sombra=gt["sombra"], fundo=gt["fundo"],
                                    largura_max=gt["largura"], tipo="text")
                mats["texts"].append(tm)
                ini, fim = atraso + float(g["inicio"]), atraso + float(g["fim"])
                seg = texto_seg(tm, ini, fim - ini, gt["y"], render_index=15000 + len(nativos_ok))
                lst = []
                for tipo, chave, dur in (("in", g.get("entrada") or "mola", 0.38), ("out", g.get("saida") or "some", 0.28)):
                    nomes = MAPA_ANIM_TEXTO[tipo].get(chave) or MAPA_ANIM_TEXTO[tipo]["*"]
                    nm = next((n for n in nomes if (tipo, n) in anims), None)
                    if nm:
                        an = copy.deepcopy(anims[(tipo, nm)]); an["start"] = 0; an["duration"] = us(min(dur, (fim - ini) / 3)); lst.append(an)
                    elif tipo == "in":
                        avisos_anim.add(f"animação de texto '{nomes[0]}' não está no cache do CapCut: aplique uma vez em qualquer texto e exporte de novo")
                anim_mat = next(m for m in mats["material_animations"] if m["id"] in seg["extra_material_refs"])
                anim_mat["animations"] = lst
                for p in pistas_txt:   # um texto por faixa sem sobreposição
                    u = p[-1]["target_timerange"]
                    if u["start"] + u["duration"] <= seg["target_timerange"]["start"]:
                        p.append(seg); break
                else:
                    pistas_txt.append([seg])
                nativos_ok.append(g["tipo"])
            for p in pistas_txt:
                tt = copy.deepcopy(modelo["text_track"]); tt["id"] = _uid(); tt["segments"] = p; tracks.append(tt)
            avisos.extend(sorted(avisos_anim))
        props_g = {**props, "camada": "graficos", "barra_progresso": False, "grafismos": [g for g, _ in restantes]}
        if graf and not restantes:   # sem grafismo nenhum a Montagem desenharia as palavras-chave no lugar: não aqui
            props_g["palavras_chave"] = []
        pedacos = trechos_graficos(props_g, atraso, dur_v, total)
        if pedacos and renderizar:
            mov = acb.renderizar_remotion_alpha("Montagem", props_g, pasta / "grafismos.mov")
            mg = material(Path(mov), alfa=True)
            segs = [segmento(mg, a, z - a, a, render_index=11100 + i) for i, (a, z) in enumerate(pedacos)]
            tracks.append(trilha_video(segs, flag=2)); n_graf = len(segs)
        # ── legenda
        ass = d / "legenda.ass"; tc = grf.trechos_tela_cheia(graf)
        if legenda == "identica" and renderizar and (ass.exists() or props.get("legenda_cinetica")):
            if props.get("legenda_cinetica"):
                movl = acb.renderizar_remotion_alpha("Montagem", {**props, "camada": "legenda"}, pasta / "legenda.mov")
                trechos_leg = [(atraso + l["inicio"], atraso + l["fim"]) for l in props["legenda_cinetica"].get("linhas") or []]
            else:
                ass_usado = ass
                if tc:  # como na entrega: a legenda some onde o grafismo ocupa a tela
                    ass_usado = pasta / ".legenda-sem-tela-cheia.ass"; grf.ass_sem_trechos(ass, tc, ass_usado)
                esc = lambda s: str(s).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
                movl = pasta / "legenda.mov"
                rodar([FFMPEG, "-y", "-hide_banner", "-nostats", "-f", "lavfi", "-i", f"color=c=black@0.0:s={W}x{H}:r={fps:g}:d={total:.3f},format=rgba",
                       "-vf", f"subtitles='{esc(ass_usado)}':fontsdir='{esc(acb.RAIZ / 'fontes')}':alpha=1", "-c:v", "png", "-pix_fmt", "rgba", str(movl)])
                if ass_usado != ass:
                    Path(ass_usado).unlink(missing_ok=True)
                trechos_leg = [(f["inicio"], f["fim"]) for f in frases_ass(ass)]
            ml = material(Path(movl), alfa=True)
            segs = [segmento(ml, a, z - a, a, render_index=11200 + i) for i, (a, z) in enumerate(juntar(trechos_leg, folga=0.02)) if z - a > 0.04]
            tracks.append(trilha_video(segs, flag=2)); n_leg = len(segs)
        elif legenda in ("nativa", "nativa_destaque") and ass.exists():
            lc = legenda_capcut(ass, W, H); info_leg.update({k: lc[k] for k in ("nome_fonte", "tamanho", "cor", "destaque", "y")})
            fonte = _ligar(lc["fonte"], pasta_fontes()) if lc["fonte"] else None
            if not fonte:
                avisos.append(f"fonte da legenda '{lc['nome_fonte']}' não está em fontes/: o CapCut usa a fonte padrão")
            info_leg["fonte"] = fonte.name if fonte else None
            frases = [f for f in frases_ass(ass) if not any(a <= (f["inicio"] + f["fim"]) / 2 <= z for a, z in tc)]   # some onde o grafismo ocupa a tela
            if props.get("legenda_cinetica"):
                avisos.append("a entrega usa legenda cinética (Remotion): a nativa vem com o estilo do ASS, sem a animação")
            tt = copy.deepcopy(modelo["text_track"]); tt["id"] = _uid(); tt["segments"] = []
            def caixa_leg(texto, ini, fim, faixas, palavras_rel=None):
                tm = material_texto(modelo, texto, fonte, lc["tamanho"], lc["cor"], faixas=faixas, contorno=lc["contorno"], sombra=lc["sombra"], fundo=lc["fundo"],
                                    alinhamento=lc["alinhamento"], largura_max=lc["largura"], tipo="subtitle", ktv=lc["destaque"])
                if palavras_rel:
                    tm["words"] = palavras_rel
                mats["texts"].append(tm); tt["segments"].append(texto_seg(tm, ini, fim - ini, lc["y"], render_index=14000 + len(tt["segments"])))
            for i, f in enumerate(frases):
                fim = min(f["fim"], frases[i + 1]["inicio"]) if i + 1 < len(frases) else f["fim"]   # a mesma faixa não aceita caixas sobrepostas
                if fim - f["inicio"] < 0.04:
                    continue
                texto = " ".join(p["palavra"] for p in f["palavras"]) or f["texto"]
                if legenda == "nativa_destaque" and lc["destaque"]:   # como o \k do ASS: a palavra falada (e as anteriores) na cor de destaque
                    pos_p = []; c = 0
                    for p in f["palavras"]:
                        pos_p.append((c, c + len(p["palavra"]))); c += len(p["palavra"]) + 1
                    marcos = [f["inicio"]] + [max(f["inicio"], p["inicio"]) for p in f["palavras"][1:]] + [fim]
                    for k in range(len(f["palavras"])):
                        a_k, z_k = marcos[k], min(marcos[k + 1], fim)
                        if z_k - a_k > 0.02:
                            caixa_leg(texto, a_k, z_k, [(0, pos_p[k][1], lc["destaque"])])
                else:
                    st_ms, en_ms, txt = [], [], []
                    for j, p in enumerate(f["palavras"]):   # tempo por palavra (karaokê do CapCut): ms relativos à caixa, o espaço como "palavra" de duração zero
                        st_ms.append(int((p["inicio"] - f["inicio"]) * 1000)); en_ms.append(int((p["fim"] - f["inicio"]) * 1000)); txt.append(p["palavra"])
                        if j < len(f["palavras"]) - 1:
                            st_ms.append(en_ms[-1]); en_ms.append(en_ms[-1]); txt.append(" ")
                    caixa_leg(texto, f["inicio"], fim, None, {"start_time": st_ms, "end_time": en_ms, "text": txt})
            n_leg = len(tt["segments"]); tracks.append(tt)
        # ── efeitos sonoros: uma faixa por sobreposição
        pistas = []; sfx_dir = acb.REMOTION / "public" / "sfx"
        for e in sorted(props.get("sfx") or [], key=lambda x: x["inicio"]):
            arq = sfx_dir / e["arquivo"]
            if not arq.exists():
                avisos.append(f"efeito sonoro não encontrado: {e['arquivo']}"); continue
            loc = _ligar(arq, pasta); ini = atraso + float(e["inicio"])
            s = audio(loc, ini, min(info_midia(loc)["duracao_s"], 2.0), vol=float(e.get("volume", 1.0)))
            for p in pistas:
                u = p[-1]["target_timerange"]
                if u["start"] + u["duration"] <= us(ini):
                    p.append(s); break
            else:
                pistas.append([s])
        tracks += [trilha_audio(p) for p in pistas]; n_sfx = sum(len(p) for p in pistas)
        # ── trilha: repetida até o fim, volume da montagem, ducking por keyframes de volume sob a fala
        trilha = ac.get("trilha")
        if trilha and Path(trilha).exists():
            loc = _ligar(Path(trilha), pasta); dt = info_midia(loc)["duracao_s"]
            alto = 10 ** (float(ac.get("trilha_volume_db") or -18) / 20); baixo = alto * 0.35
            fala = juntar([(atraso + s["inicio"], atraso + s["fim"]) for s in props.get("segmentos") or []], folga=0.4)
            segs = []; cur = 0.0
            while cur < total - 0.05:
                dd = min(dt, total - cur)
                s = audio(loc, cur, dd, fade=(1.5 if cur == 0 else 0, 1.5 if cur + dd >= total - 0.05 else 0))
                pts = {0.0: alto, dd: alto}
                for a, z in fala:
                    if z >= cur and a <= cur + dd:
                        for off, v in ((a - cur - 0.15, alto), (a - cur, baixo), (z - cur, baixo), (z - cur + 0.15, alto)):
                            pts[round(min(dd, max(0.0, off)), 3)] = v
                keyframes(s, "KFTypeVolume", sorted(pts.items())); segs.append(s); cur += dd
            tracks.append(trilha_audio(segs))
        elif trilha:
            avisos.append(f"trilha do projeto não encontrada: {trilha}")
        elif not trilha and ac.get("trilha_volume_db") is not None and props.get("sfx") is not None:
            avisos.append("a trilha da entrega (se houve) não ficou registrada no projeto (montagens antes de 12/11 com trilha 'auto'): adicione a música no CapCut")
    finally:
        for l in links:
            l.unlink(missing_ok=True)
    doc["duration"] = us(total); doc["materials"] = mats; doc["tracks"] = tracks
    registrado = _gravar_rascunho(modelo, drafts, pasta, nome_pasta, doc, midias)
    res = {"versao": 3, "nome": nome_pasta, "projeto": _win(pasta), "criado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "n_segmentos": n_planos, "n_legendas": n_leg,
           "n_grafismos": n_graf, "n_textos_nativos": len(nativos_ok), "grafismos_nativos": nativos_ok, "barra_progresso": bool(n_barra), "n_sfx": n_sfx,
           "transicoes": transicoes, "legenda": legenda, "estilo_legenda": info_leg or None, "base": info_base, "avisos": avisos, "registrado_no_indice": registrado,
           "duracao_s": round(total, 2), "tempo_s": round(time.monotonic() - t0, 1),
           "como_abrir": "Abra o CapCut: o projeto aparece na lista de rascunhos (se ele já estava aberto, feche e abra de novo)."}
    if renderizar:
        try:
            (d.parent.parent / "capcut.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass
    return res


# ── captura por diff (12/11/2026): foto do rascunho antes e depois de o Raphael aplicar um recurso à mão no CapCut, e o que mudou
CAPTURAS = Path(__file__).resolve().parent / "modelos" / "capturas"


def _por_id(lista):
    return {x.get("id"): x for x in lista if isinstance(x, dict)}


def diff_rascunhos(antes: dict, depois: dict) -> dict:
    """Materiais novos e campos alterados (por id) entre duas fotos do draft_content.json; segmentos com campos alterados."""
    out = {"novos": {}, "alterados": {}, "segmentos": {}}
    ma, md = antes.get("materials", {}), depois.get("materials", {})
    for k in sorted(set(ma) | set(md)):
        a, d = _por_id(ma.get(k) or []), _por_id(md.get(k) or [])
        novos = [d[i] for i in d if i not in a]
        if novos:
            out["novos"][k] = novos
        for i in d:
            if i in a:
                mud = {c: {"antes": a[i].get(c), "depois": v} for c, v in d[i].items() if a[i].get(c) != v}
                if mud:
                    out["alterados"].setdefault(k, {})[i] = mud
    sa = {s["id"]: s for t in antes.get("tracks", []) for s in t.get("segments", [])}
    for t in depois.get("tracks", []):
        for s in t.get("segments", []):
            if s["id"] in sa:
                mud = {c: {"antes": sa[s["id"]].get(c), "depois": v} for c, v in s.items() if sa[s["id"]].get(c) != v}
                if mud:
                    out["segmentos"][s["id"]] = mud
            else:
                out["segmentos"][s["id"]] = {"novo": s}
    return out


def capturar(etapa: str, nome="Editor GS - referencia", drafts=None) -> dict:
    """etapa 'antes': guarda a foto do rascunho; 'depois': compara com a foto e grava modelos/capturas/<nome>-diff.json."""
    drafts = Path(drafts) if drafts else DRAFTS_PADRAO; arq = drafts / nome / "draft_content.json"
    CAPTURAS.mkdir(parents=True, exist_ok=True); foto = CAPTURAS / f"{nome}-antes.json"
    atual = json.loads(arq.read_text(encoding="utf-8"))
    if etapa == "antes":
        foto.write_text(json.dumps(atual, ensure_ascii=False), encoding="utf-8"); return {"foto": str(foto)}
    dif = diff_rascunhos(json.loads(foto.read_text(encoding="utf-8")), atual)
    saida = CAPTURAS / f"{nome}-diff.json"; saida.write_text(json.dumps(dif, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"diff": str(saida), "novos": {k: len(v) for k, v in dif["novos"].items()}, "alterados": {k: len(v) for k, v in dif["alterados"].items()},
            "segmentos": len(dif["segmentos"])}


if __name__ == "__main__":   # python -X utf8 -m editor_video.capcut_fiel antes|depois ["nome do rascunho"]  (rodar em mcp/editor-de-video)
    import sys
    print(json.dumps(capturar(sys.argv[1], *(sys.argv[2:3] or ["Editor GS - referencia"])), ensure_ascii=False, indent=1))
