"""Exporta projeto editável para o CapCut (Windows, versão 9.x): cortes como segmentos e legendas como camada de texto."""
import copy, json, os, re, shutil, time, uuid
from pathlib import Path
from .util import caminho, ler_json, info_midia, ErroFerramenta

MODELO = Path(__file__).resolve().parent / "modelos" / "capcut-9.6.json"
DRAFTS_PADRAO = Path("/mnt/c/Users/rapha/AppData/Local/CapCut/User Data/Projects/com.lveditor.draft")
US = 1_000_000


def _uid():
    return str(uuid.uuid4()).upper()


def _win(p):
    p = str(Path(p).resolve())
    m = re.match(r"^/mnt/([a-z])/(.*)$", p)
    return f"{m.group(1).upper()}:/{m.group(2)}" if m else p


def _linhas_legenda(palavras, max_palavras=4, max_chars=22, max_gap_s=0.6, max_dur_s=2.5):
    linhas, atual = [], []
    for p in palavras:
        if atual:
            chars = len(" ".join(x["palavra"] for x in atual + [p]))
            if len(atual) >= max_palavras or chars > max_chars or p["inicio"] - atual[-1]["fim"] > max_gap_s or p["fim"] - atual[0]["inicio"] > max_dur_s:
                linhas.append(atual); atual = []
        atual.append(p)
    if atual:
        linhas.append(atual)
    return linhas


def exportar_capcut(video, nome, edl_json=None, palavras_json=None, pasta_drafts=None, copiar_video=True, legenda=True, cor_destaque="#F79615", tamanho_texto=None):
    """Cria a pasta do projeto no CapCut. video = ORIGINAL (bruto); edl_json = trechos mantidos (tempo do original). palavras_json = transcrição do original
    (ou do cortado, se não houver EDL). Sem EDL: um segmento com o vídeo inteiro. Devolve o caminho do projeto; abrir o CapCut e o projeto aparece na lista."""
    v = caminho(video); info = info_midia(v)
    modelo = json.loads(MODELO.read_text(encoding="utf-8"))
    drafts = Path(pasta_drafts) if pasta_drafts else DRAFTS_PADRAO
    if not drafts.exists():
        raise ErroFerramenta(f"Pasta de projetos do CapCut não encontrada: {drafts}")
    nome_pasta = re.sub(r"[^\w\- ]+", "", nome).strip() or "EditorGS"
    pasta = drafts / nome_pasta
    if pasta.exists():
        nome_pasta = f"{nome_pasta} {time.strftime('%H%M%S')}"; pasta = drafts / nome_pasta
    pasta.mkdir(parents=True)
    # vídeo de origem
    if copiar_video:
        destino = pasta / v.name
        try:
            os.link(v, destino)
        except OSError:
            shutil.copy2(v, destino)
        caminho_video = _win(destino)
    else:
        caminho_video = _win(v)
    W, H = info["largura"], info["altura"]; fps = info["fps"] or 30.0
    edl = ler_json(edl_json) if edl_json else None
    manter = [(m["inicio"], m["fim"]) for m in edl["manter"]] if edl else [(0.0, info["duracao_s"])]
    doc = copy.deepcopy(modelo["doc"]); doc["id"] = _uid(); doc["name"] = nome_pasta; doc["fps"] = float(fps)
    doc["canvas_config"] = {"ratio": "original", "width": W, "height": H, "background": None}
    agora = int(time.time()); doc["create_time"] = agora; doc["update_time"] = agora
    mats = copy.deepcopy(modelo["materials_vazios"])
    # material de vídeo
    vm = copy.deepcopy(modelo["video_material"]); vm["id"] = _uid(); vm["path"] = caminho_video; vm["material_name"] = v.name
    vm["duration"] = int(info["duracao_s"] * US); vm["width"] = W; vm["height"] = H; vm["has_audio"] = bool(info["tem_audio"])
    mats["videos"].append(vm)
    vt = copy.deepcopy(modelo["video_track"]); vt["id"] = _uid(); vt["segments"] = []
    cursor = 0
    for a, z in manter:
        seg = copy.deepcopy(modelo["video_segment"]); seg["id"] = _uid(); seg["material_id"] = vm["id"]
        dur = int(round((z - a) * US))
        seg["source_timerange"] = {"start": int(round(a * US)), "duration": dur}; seg["target_timerange"] = {"start": cursor, "duration": dur}
        refs = []
        for k, m in modelo["video_extras"].items():
            mm = copy.deepcopy(m); mm["id"] = _uid(); mats.setdefault(k, []).append(mm); refs.append(mm["id"])
        seg["extra_material_refs"] = refs; vt["segments"].append(seg); cursor += dur
    doc["duration"] = cursor
    tracks = [vt]
    n_leg = 0
    if legenda and palavras_json:
        d = ler_json(palavras_json); palavras = d["palavras"]
        # se as palavras estão no tempo do original e há EDL, remapeia para o tempo da linha do tempo
        def remap(t):
            acc = 0.0
            for a, z in manter:
                if a <= t <= z:
                    return acc + (t - a)
                acc += z - a
            return None
        if edl and "origem_edl" not in d:
            novas = []
            for p in palavras:
                ni, nf = remap(p["inicio"]), remap(p["fim"])
                if ni is None and nf is None:
                    continue
                novas.append({**p, "inicio": ni if ni is not None else nf, "fim": nf if nf is not None else ni})
            palavras = novas
        tt = copy.deepcopy(modelo["text_track"]); tt["id"] = _uid(); tt["segments"] = []
        for linha in _linhas_legenda(palavras):
            texto = " ".join(p["palavra"] for p in linha); ini = linha[0]["inicio"]; fim = linha[-1]["fim"] + 0.12
            tm = copy.deepcopy(modelo["text_material"]); tm["id"] = _uid(); tm["name"] = _uid()
            c = json.loads(tm["content"]); c["text"] = texto
            for st in c["styles"]:
                st["range"] = [0, len(texto)]
                if tamanho_texto:
                    st["size"] = tamanho_texto
            tm["content"] = json.dumps(c, ensure_ascii=False); tm["recognize_text"] = texto
            # tempos por palavra (karaokê do CapCut usa ms relativos ao segmento)
            st_ms, en_ms, txt = [], [], []
            for i, p in enumerate(linha):
                st_ms.append(int((p["inicio"] - ini) * 1000)); en_ms.append(int((p["fim"] - ini) * 1000)); txt.append(p["palavra"])
                if i < len(linha) - 1:
                    st_ms.append(en_ms[-1]); en_ms.append(en_ms[-1]); txt.append(" ")
            tm["words"] = {"start_time": st_ms, "end_time": en_ms, "text": txt}
            mats["texts"].append(tm)
            seg = copy.deepcopy(modelo["text_segment"]); seg["id"] = _uid(); seg["material_id"] = tm["id"]
            seg["target_timerange"] = {"start": int(round(ini * US)), "duration": max(1, int(round((fim - ini) * US)))}
            refs = []
            for k, m in modelo["text_extras"].items():
                mm = copy.deepcopy(m); mm["id"] = _uid(); mats.setdefault(k, []).append(mm); refs.append(mm["id"])
            seg["extra_material_refs"] = refs; tt["segments"].append(seg); n_leg += 1
        tracks.append(tt)
    doc["materials"] = mats; doc["tracks"] = tracks
    (pasta / "draft_content.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    meta = copy.deepcopy(modelo["meta"]); meta["draft_id"] = doc["id"]; meta["draft_name"] = nome_pasta
    meta["draft_fold_path"] = _win(pasta); meta["draft_root_path"] = _win(drafts); meta["draft_timeline_materials_size_"] = 0
    for k in ("tm_draft_create", "tm_draft_modified"):
        meta[k] = int(time.time() * US)
    meta["tm_duration"] = cursor
    meta["draft_materials"] = [{"type": 0, "value": [{"ai_group_type": "", "create_time": agora, "duration": vm["duration"], "enter_from": 0, "extra_info": v.name,
                                                        "file_Path": caminho_video, "height": H, "id": str(uuid.uuid4()), "import_time": agora, "import_time_ms": int(time.time() * US),
                                                        "item_source": 1, "md5": "", "metetype": "video", "roughcut_time_range": {"duration": -1, "start": -1}, "sub_time_range": {"duration": -1, "start": -1},
                                                        "type": 0, "width": W}]}]
    (pasta / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    # índice de rascunhos do CapCut (root_meta_info.json): acrescenta a entrada, com cópia de segurança
    idx = drafts / "root_meta_info.json"
    if idx.exists() and modelo.get("root_entry"):
        try:
            root = json.loads(idx.read_text(encoding="utf-8")); shutil.copy2(idx, drafts / "root_meta_info.json.editor-gs.bak")
            ent = copy.deepcopy(modelo["root_entry"]); ent.update({"draft_id": doc["id"], "draft_name": nome_pasta, "draft_fold_path": _win(pasta), "draft_root_path": _win(drafts),
                                                                    "draft_json_file": _win(pasta) + "/draft_content.json", "draft_cover": "", "draft_timeline_materials_size_": 0,
                                                                    "tm_draft_create": meta["tm_draft_create"], "tm_draft_modified": meta["tm_draft_modified"], "tm_duration": cursor})
            root.setdefault("all_draft_store", []).insert(0, ent); root.setdefault("draft_ids", []).append(doc["id"]) if isinstance(root.get("draft_ids"), list) else None
            idx.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8"); registrado = True
        except Exception:
            registrado = False
    else:
        registrado = False
    res_registro = {"nome": nome_pasta, "projeto": _win(pasta), "pasta_wsl": str(pasta), "criado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "n_segmentos": len(manter), "n_legendas": n_leg}
    try:
        base = Path(edl_json).resolve().parent if edl_json else (Path(palavras_json).resolve().parent if palavras_json else None)
        if base and "entrada" not in base.parts:
            (base / "capcut.json").write_text(json.dumps(res_registro, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return {"registrado_no_indice": registrado, "projeto": _win(pasta), "pasta_wsl": str(pasta), "n_segmentos": len(manter), "n_legendas": n_leg, "duracao_s": round(cursor / US, 3), "video": caminho_video,
            "como_abrir": "Abra o CapCut (Windows); o projeto aparece na lista de rascunhos com esse nome."}
