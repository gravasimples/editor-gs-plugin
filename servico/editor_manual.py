"""Editor manual do app (12/11/2026): lê e regrava o projeto editável que `montar_remotion` deixa em saida/<slug>/_projeto/<final>/
(props da Montagem + mídias + legenda.ass) e refaz a entrega com o mesmo motor. O agente e a pessoa editam o mesmo projeto: não há segundo
modelo de dados. Cada renderização vira um arquivo novo (`final_..._editado_vN.mp4`); o original nunca é sobrescrito.

Legenda: as nossas ASS têm várias linhas por frase (destaque palavra a palavra). Corrigir texto troca palavra por palavra dentro da frase,
mantendo tempos e efeitos; mudar o número de palavras de uma frase não é aceito (aí o caminho é pedir ao Editor)."""
import json, re, shutil, sys, threading, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
TAG = re.compile(r"\{[^}]*\}")
_RODANDO: dict = {}


def projetos(pasta_saida: Path) -> list:
    out = []
    for pj in sorted((pasta_saida / "_projeto").glob("*/projeto.json")):
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        out.append({"nome": pj.parent.name, "video_final": d.get("video_final"), "formato": d.get("formato"), "criado": d.get("criado"),
                    "editado": d.get("editado"), "versoes": d.get("versoes") or [], "render": estado_render(pj.parent), "capcut": estado_capcut(pj.parent)})
    return out


def _tempo(t: str) -> float:
    h, m, s = t.split(":"); return int(h) * 3600 + int(m) * 60 + float(s)


def frases(ass: Path) -> list:
    """Agrupa as linhas Dialogue em frases (mesmo texto sem marcações, linhas seguidas)."""
    if not ass.exists():
        return []
    out = []
    for i, linha in enumerate(ass.read_text(encoding="utf-8-sig").splitlines()):
        if not linha.startswith("Dialogue:"):
            continue
        partes = linha.split(",", 9)
        texto = " ".join(TAG.sub("", partes[9]).replace("\\N", " ").split())
        ini, fim = _tempo(partes[1]), _tempo(partes[2])
        if out and out[-1]["texto"] == texto and abs(out[-1]["fim"] - ini) < 0.05:
            out[-1]["fim"] = fim; out[-1]["linhas"].append(i)
        else:
            out.append({"i": len(out), "texto": texto, "inicio": round(ini, 3), "fim": round(fim, 3), "linhas": [i]})
    for f in out:
        f["inicio"] = round(f["inicio"], 3); f["fim"] = round(f["fim"], 3)
    return out


def corrigir_legenda(ass: Path, correcoes: dict) -> int:
    """correcoes = {indice_da_frase: "texto novo"} com o mesmo número de palavras. Troca palavra a palavra nas linhas da frase."""
    fs = frases(ass); linhas = ass.read_text(encoding="utf-8-sig").splitlines(); n = 0
    for k, novo in correcoes.items():
        f = fs[int(k)]; velhas, novas = f["texto"].split(), str(novo).split()
        if velhas == novas:
            continue
        if len(velhas) != len(novas):
            raise ValueError(f"Frase {int(k) + 1}: mantenha {len(velhas)} palavras (veio {len(novas)}). Para reescrever a frase, peça ao Editor.")
        for li in f["linhas"]:
            partes = linhas[li].split(",", 9); cab, corpo = partes[:9], partes[9]
            # troca só fora das marcações {…}, na ordem das palavras
            pedacos = re.split(r"(\{[^}]*\})", corpo); w = 0
            for j, p in enumerate(pedacos):
                if p.startswith("{"):
                    continue
                def troca(m):
                    nonlocal w
                    r = novas[w] if w < len(novas) and m.group(0) == velhas[w] else m.group(0); w += 1; return r
                pedacos[j] = re.sub(r"\S+", troca, p)
            linhas[li] = ",".join(cab) + "," + "".join(pedacos)
        n += 1
    ass.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return n


def ler(pasta_proj: Path) -> dict:
    d = json.loads((pasta_proj / "projeto.json").read_text(encoding="utf-8"))
    est = estilo_legenda_atual(pasta_proj, d)
    return {**d, "frases": frases(pasta_proj / "legenda.ass"), "render": estado_render(pasta_proj), "capcut": estado_capcut(pasta_proj),
            "edl_info": edl_info(pasta_proj, d), "legenda_estilos": estilos_legenda(), "legenda_atual": {"id": est.get("id"), "modo": est["modo"], "legenda": est["legenda"]}}


def estado_render(pasta_proj: Path) -> dict | None:
    st = _RODANDO.get(str(pasta_proj))
    if st:
        return st
    f = pasta_proj / "ultimo_render.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except Exception:  # noqa: BLE001
        return None


def renderizar(pasta_proj: Path, props: dict, correcoes: dict | None = None, por: str = "", acabamento: dict | None = None,
               edl: list | None = None, legenda_estilo: str | None = None) -> dict:
    """Guarda a versão (props + legenda corrigida) e refaz o vídeo em segundo plano. Devolve o estado inicial; o app consulta `estado_render`.
    Fase 2: `edl` = trechos do bruto [{id, inicio, fim}] na ordem do vídeo (props já remapeadas pelo editor); `legenda_estilo` = id em estilos/legendas/.
    Mudou um dos dois: recorta o bruto e refaz a legenda antes do render (preparar_edl_e_legenda)."""
    chave = str(pasta_proj)
    if (_RODANDO.get(chave) or {}).get("estado") == "renderizando":
        raise ValueError("Já está renderizando este projeto.")
    proj = json.loads((pasta_proj / "projeto.json").read_text(encoding="utf-8"))
    hist = pasta_proj / "historico"; hist.mkdir(exist_ok=True)
    carimbo = time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(pasta_proj / "projeto.json", hist / f"projeto-{carimbo}.json")
    if (pasta_proj / "legenda.ass").exists():
        shutil.copy2(pasta_proj / "legenda.ass", hist / f"legenda-{carimbo}.ass")
    atual = estilo_legenda_atual(pasta_proj, proj)
    if legenda_estilo:
        _bloco_estilo(legenda_estilo)  # valida já (erro 400 em vez de falhar no meio)
    refazer = bool(edl and not _mesma_edl(edl, (proj.get("edl") or {}).get("manter") or [])) or bool(legenda_estilo and legenda_estilo != atual.get("id"))
    if edl and refazer and not edl_info(pasta_proj, proj).get("disponivel"):
        raise ValueError(edl_info(pasta_proj, proj).get("motivo") or "Aparar cortes não está disponível neste projeto.")
    if correcoes and not refazer:
        corrigir_legenda(pasta_proj / "legenda.ass", correcoes)
    versoes = proj.get("versoes") or []; n = len(versoes) + 1
    base = Path(proj["video_final"]).stem; nome_saida = f"{base}_editado_v{n}.mp4"
    if acabamento:  # só o que o editor mexe: volume da trilha e trilha ligada/desligada
        ac = proj.setdefault("acabamento", {})
        if "trilha_volume_db" in acabamento:
            ac["trilha_volume_db"] = max(-40.0, min(-6.0, float(acabamento["trilha_volume_db"])))
        if acabamento.get("sem_trilha"):
            ac["trilha_original"] = ac.get("trilha") or ac.get("trilha_original"); ac["trilha"] = None
        elif acabamento.get("sem_trilha") is False and ac.get("trilha_original"):
            ac["trilha"] = ac.pop("trilha_original")
    props = {k: v for k, v in props.items() if k != "previa_trechos"}  # só da prévia do editor
    proj.update(props=props, editado=time.strftime("%Y-%m-%dT%H:%M:%S"), editado_por=por)
    (pasta_proj / "projeto.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")
    saida = pasta_proj.parent.parent / nome_saida
    st = {"estado": "renderizando", "desde": time.strftime("%Y-%m-%dT%H:%M:%S"), "arquivo": nome_saida}
    _RODANDO[chave] = st

    def rodar():
        from editor_video import acabamento as a
        from editor_video.util import finalizar_audio
        try:
            pr, avisos = props, []
            if refazer:
                st["etapa"] = "recortando o bruto e refazendo a legenda"
                pr, avisos, feita = preparar_edl_e_legenda(pasta_proj, props, edl, legenda_estilo, correcoes)
                if correcoes and not feita:
                    corrigir_legenda(pasta_proj / "legenda.ass", correcoes)
            st["etapa"] = "renderizando"
            r = a.rerenderizar_projeto(pasta_proj, str(saida), props=pr)
            try:
                finalizar_audio(saida)
            except Exception:  # noqa: BLE001
                pass
            fim = {"estado": "pronto", "arquivo": nome_saida, "tempo_s": r.get("tempo_s"), "quando": time.strftime("%Y-%m-%dT%H:%M:%S"), **({"avisos": avisos} if avisos else {})}
            p2 = json.loads((pasta_proj / "projeto.json").read_text(encoding="utf-8"))
            p2["versoes"] = (p2.get("versoes") or []) + [{"arquivo": nome_saida, "quando": fim["quando"], "por": por}]
            (pasta_proj / "projeto.json").write_text(json.dumps(p2, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            fim = {"estado": "falhou", "erro": str(e)[-600:], "quando": time.strftime("%Y-%m-%dT%H:%M:%S")}
        (pasta_proj / "ultimo_render.json").write_text(json.dumps(fim, ensure_ascii=False), encoding="utf-8")
        _RODANDO.pop(chave, None)

    threading.Thread(target=rodar, daemon=True).start()
    return st


# CapCut fiel (12/11/2026): o mesmo projeto vira rascunho do CapCut (capcut_fiel.py), em segundo plano porque renderiza as camadas transparentes
_CAPCUT: dict = {}


def estado_capcut(pasta_proj: Path) -> dict | None:
    st = _CAPCUT.get(str(pasta_proj))
    if st:
        return st
    f = pasta_proj / "ultimo_capcut.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except Exception:  # noqa: BLE001
        return None


def exportar_capcut(pasta_proj: Path, legenda: str = "nativa") -> dict:
    chave = str(pasta_proj)
    if (_CAPCUT.get(chave) or {}).get("estado") == "exportando":
        raise ValueError("Já está mandando este projeto para o CapCut.")
    if legenda not in ("nativa", "nativa_destaque", "identica", "nenhuma"):   # 12/11/2026: nativa (texto editável no estilo da entrega) é o padrão
        raise ValueError("legenda: nativa, nativa_destaque, identica ou nenhuma")
    st = {"estado": "exportando", "desde": time.strftime("%Y-%m-%dT%H:%M:%S"), "legenda": legenda}
    _CAPCUT[chave] = st

    def rodar():
        from editor_video import capcut_fiel
        try:
            fim = {"estado": "pronto", **capcut_fiel.exportar_capcut_projeto(pasta_proj, legenda=legenda)}
        except Exception as e:  # noqa: BLE001
            fim = {"estado": "falhou", "erro": str(e)[-600:], "quando": time.strftime("%Y-%m-%dT%H:%M:%S")}
        (pasta_proj / "ultimo_capcut.json").write_text(json.dumps(fim, ensure_ascii=False), encoding="utf-8")
        _CAPCUT.pop(chave, None)

    threading.Thread(target=rodar, daemon=True).start()
    return st


# ---- Fase 2 (12/11/2026): aparar/mover cortes (EDL) e trocar o estilo da legenda -------------------------------------------------------------
# projeto.json ganha (só acréscimo): `edl` = {bruto, duracao_bruto_s, palavras ("palavras_bruto.json"), manter: [{id, inicio, fim}] no tempo do bruto,
# recuperada?} e `legenda_estilo` = {id, legenda}. As props continuam no tempo do vídeo cortado: o editor remapeia grafismos, SFX, planos etc.
# quando a EDL muda; o servidor recorta o bruto de novo (cortes.aplicar_cortes), refaz a legenda a partir das palavras do bruto e renderiza.
ESTILOS_LEG = RAIZ / "estilos" / "legendas"
CINETICAS = ("tipografica", "maquina", "onda")


def _local(p) -> Path | None:
    """Caminho gravado no tempo do WSL (/home/.../workspace/...) → o mesmo arquivo no workspace atual."""
    if not p:
        return None
    c = Path(str(p))
    if c.exists():
        return c
    s = str(p).replace("\\", "/")
    if "/workspace/" in s:
        try:
            from servico import caminhos as cam
            alt = cam.WORKSPACE / s.split("/workspace/", 1)[1]
            if alt.exists():
                return alt
        except Exception:  # noqa: BLE001
            pass
    return None


def _gravar(pasta_proj: Path, proj: dict):
    (pasta_proj / "projeto.json").write_text(json.dumps(proj, ensure_ascii=False, indent=1), encoding="utf-8")


def _recuperar_edl(pasta_proj: Path, proj: dict) -> dict | None:
    """Projetos de antes da fase 2 não guardaram a EDL: procura na pasta da entrega um edl*.json cujo total bata com a duração das props
    e cujo bruto ainda exista. Achou: grava em projeto.json (`recuperada`: nome do arquivo)."""
    dur = float(proj["props"].get("duracao_s") or 0)
    for f in sorted(pasta_proj.parent.parent.glob("edl*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
            tot = sum(float(m["fim"]) - float(m["inicio"]) for m in e.get("manter") or [])
        except Exception:  # noqa: BLE001
            continue
        bruto = _local(e.get("origem"))
        if not bruto or abs(tot - dur) > 0.12:
            continue
        pb = _local(e.get("palavras_json"))
        if pb:
            shutil.copy2(pb, pasta_proj / "palavras_bruto.json")
        proj["edl"] = {"bruto": str(bruto), "duracao_bruto_s": e.get("duracao_original_s"), "recuperada": f.name,
                       "palavras": "palavras_bruto.json" if pb else None,
                       "manter": [{"id": i, "inicio": float(m["inicio"]), "fim": float(m["fim"])} for i, m in enumerate(e["manter"])]}
        _gravar(pasta_proj, proj)
        return proj["edl"]
    return None


def edl_info(pasta_proj: Path, proj: dict) -> dict:
    """O que o editor precisa para aparar cortes, ou `disponivel: false` com o motivo."""
    e = proj.get("edl") or _recuperar_edl(pasta_proj, proj)
    if not e:
        return {"disponivel": False, "motivo": "Este projeto não guardou a EDL nem o bruto (montado sem cortes ou antes de 12/11): dá para editar tudo, menos aparar cortes."}
    bruto = _local(e.get("bruto"))
    if not bruto:
        return {"disponivel": False, "motivo": f"O bruto não está mais acessível ({e.get('bruto')})."}
    if (proj["props"].get("layout") or {}).get("blocos"):
        return {"disponivel": False, "motivo": "Vídeo com layout (tela/painel): aparar cortes ainda não está liberado (a gravação de tela precisaria dos mesmos cortes)."}
    dur_b = e.get("duracao_bruto_s")
    if not dur_b:
        try:
            from editor_video.util import info_midia
            dur_b = info_midia(bruto)["duracao_s"]
        except Exception:  # noqa: BLE001
            dur_b = max(float(m["fim"]) for m in e["manter"])
    return {"disponivel": True, "manter": e["manter"], "duracao_bruto_s": float(dur_b), "arquivo_bruto": bruto.name, "recuperada": e.get("recuperada"),
            "tem_palavras": bool(e.get("palavras") and (pasta_proj / e["palavras"]).exists())}


def caminho_bruto(pasta_proj: Path) -> Path | None:
    proj = json.loads((pasta_proj / "projeto.json").read_text(encoding="utf-8"))
    return _local((proj.get("edl") or {}).get("bruto"))


def estilos_legenda() -> list:
    out = []
    for f in sorted(ESTILOS_LEG.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        leg = d.get("legenda") or {}
        out.append({"id": f.stem, "nome": d.get("nome") or f.stem, "descricao": d.get("descricao", ""), "ordem": d.get("ordem", 99),
                    "cinetica": str(leg.get("animacao") or "").lower() in CINETICAS, "fora_da_marca": bool(d.get("fora_da_marca")), "legenda": leg})
    return sorted(out, key=lambda x: (x["ordem"], x["nome"]))


def _bloco_estilo(eid: str) -> dict:
    f = ESTILOS_LEG / f"{Path(str(eid)).name}.json"
    if not f.exists():
        raise ValueError(f"Estilo de legenda desconhecido: {eid}")
    return json.loads(f.read_text(encoding="utf-8"))["legenda"]


def estilo_legenda_atual(pasta_proj: Path, proj: dict) -> dict:
    """{id, legenda, modo}: o que o projeto guardou, ou o estilo da biblioteca cujo cabeçalho ASS bate com a legenda.ass (projetos antigos)."""
    from editor_video import legenda as lg
    cin = proj["props"].get("legenda_cinetica")
    guardado = proj.get("legenda_estilo") or {}
    ass = pasta_proj / "legenda.ass"
    modo = "cinetica" if cin else "ass" if ass.exists() else "nenhuma"
    if guardado.get("id"):
        return {"id": guardado["id"], "legenda": guardado.get("legenda") or _bloco_estilo(guardado["id"]), "modo": modo}
    if modo == "ass":
        linha = next((l for l in ass.read_text(encoding="utf-8-sig").splitlines() if l.startswith("Style:")), "")
        cands = [(e["id"], e["legenda"]) for e in estilos_legenda()] + ([("", guardado["legenda"])] if guardado.get("legenda") else [])
        for eid, leg in cands:
            cab, _ = lg._estilo_ass(leg, proj.get("formato") or "9x16")
            if next((l for l in cab.splitlines() if l.startswith("Style:")), None) == linha:
                return {"id": eid or None, "legenda": leg, "modo": modo}
    if modo == "cinetica":
        for e in estilos_legenda():
            if e["cinetica"] and e["legenda"].get("animacao") == cin.get("animacao"):
                return {"id": e["id"], "legenda": {**e["legenda"], "tremor": cin.get("tremor", False)}, "modo": modo}
    return {"id": None, "legenda": guardado.get("legenda") or {}, "modo": modo}


def _remapear(palavras: list, manter: list, durs: list | None = None) -> list:
    """Como cortes.remapear_palavras, mas aceita trechos fora de ordem (reordenados no editor): cada palavra vai para o trecho mantido onde tem
    mais fala (>= 50% ou >= 0,12 s), recortada a ele; o resultado sai na ordem do vídeo cortado, sem sobreposição."""
    durs = durs or [float(m["fim"]) - float(m["inicio"]) for m in manter]
    desl, acc = [], 0.0
    for m, d in zip(manter, durs):
        desl.append((float(m["inicio"]), float(m["fim"]), acc)); acc += d
    novas = []
    for p in palavras:
        i, f = float(p["inicio"]), float(p["fim"]); dur = f - i
        best, bo = None, 0.0
        for k, (a, z, _) in enumerate(desl):
            o = min(f, z) - max(i, a)
            if o > bo:
                best, bo = k, o
        if best is None and dur <= 0.001:
            best = next((k for k, (a, z, _) in enumerate(desl) if a <= i <= z), None); bo = dur
        if best is None or not (bo >= 0.5 * dur or bo >= 0.12):
            continue
        a, z, off = desl[best]
        ni, nf = round(off + max(i, a) - a, 3), round(off + min(f, z) - a, 3)
        novas.append({**p, "inicio": ni, "fim": max(nf, round(ni + 0.04, 3))})
    novas.sort(key=lambda w: w["inicio"])
    for x, y in zip(novas, novas[1:]):
        if y["inicio"] < x["fim"]:
            x["fim"] = max(x["inicio"], y["inicio"])
    return novas


def _palavras_ass(texto_ass: str) -> list:
    return [w for l in texto_ass.splitlines() if l.startswith("Dialogue:") for w in TAG.sub("", l.split(",", 9)[9]).replace("\\N", " ").split()]


def palavras_bruto(pasta_proj: Path, proj: dict, correcoes: dict | None = None) -> tuple:
    """Palavras do bruto com o texto que a legenda atual mostra (correções do editor, inclusive as ainda não renderizadas).
    Casa a legenda.ass com as palavras remapeadas pela EDL salva; se não bater (ASS feita de outra fonte), devolve as palavras do bruto e um aviso."""
    e = proj.get("edl") or {}
    f = pasta_proj / (e.get("palavras") or "palavras_bruto.json")
    if not f.exists():
        return [], "o projeto não tem as palavras do bruto: a legenda não acompanha o corte"
    brutas = [{**p, "_i": i} for i, p in enumerate(json.loads(f.read_text(encoding="utf-8")).get("palavras") or [])]
    ass = pasta_proj / "legenda.ass"
    if not ass.exists():
        return brutas, None
    texto = ass.read_text(encoding="utf-8-sig")
    if correcoes:  # aplica numa cópia (a legenda.ass só muda no render)
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "l.ass"; tmp.write_text(texto, encoding="utf-8"); corrigir_legenda(tmp, correcoes); texto = tmp.read_text(encoding="utf-8")
    vistas = _palavras_ass(texto); cortadas = _remapear(brutas, e.get("manter") or [])
    # alinha as duas listas (a ASS pode ter sido feita por um remapeamento antigo, com uma ou outra palavra a mais na borda do corte):
    # trechos trocados com o mesmo número de palavras = correção feita na legenda, que passa para as palavras do bruto
    import difflib
    sm = difflib.SequenceMatcher(a=[str(w["palavra"]).upper() for w in cortadas], b=[v.upper() for v in vistas], autojunk=False)
    perdidas = 0; maius = bool(estilo_legenda_atual(pasta_proj, proj)["legenda"].get("maiusculas"))
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" and not maius:  # só mudou maiúscula/minúscula (num estilo em maiúsculas isso é o próprio estilo)
            for w, v in zip(cortadas[i1:i2], vistas[j1:j2]):
                if v != w["palavra"]:
                    brutas[w["_i"]]["palavra"] = v
        elif op == "replace" and i2 - i1 == j2 - j1:
            for w, v in zip(cortadas[i1:i2], vistas[j1:j2]):
                brutas[w["_i"]]["palavra"] = v
        elif op in ("replace", "insert"):
            perdidas += j2 - j1
    return brutas, (f"{perdidas} palavra(s) da legenda atual não casaram com a transcrição do bruto (ficam como o Whisper ouviu)" if perdidas else None)


def _linhas_previa(palavras: list, leg: dict) -> list:
    from editor_video.legenda import _linhas
    ls = list(_linhas(palavras, max_palavras=int(leg.get("palavras_por_linha_max", 4)))); out = []
    for k, l in enumerate(ls):
        fim = l[-1]["fim"] + 0.12
        if k + 1 < len(ls):
            fim = max(min(fim, ls[k + 1][0]["inicio"] - 0.01), l[-1]["fim"])
        out.append({"inicio": l[0]["inicio"], "fim": round(fim, 3), "palavras": [{"texto": p["palavra"], "inicio": p["inicio"], "fim": p["fim"]} for p in l]})
    return out


def previa_legenda(pasta_proj: Path, manter: list | None = None, estilo: str | None = None, correcoes: dict | None = None) -> dict:
    """Legenda no tempo da EDL pedida e no estilo pedido, para a prévia: `linhas` (motor ASS: o editor desenha por cima do Player) ou
    `cinetica` (a prop legenda_cinetica que a Montagem desenha)."""
    proj = json.loads((pasta_proj / "projeto.json").read_text(encoding="utf-8"))
    atual = estilo_legenda_atual(pasta_proj, proj)
    leg = _bloco_estilo(estilo) if estilo else atual["legenda"]
    brutas, aviso = palavras_bruto(pasta_proj, proj, correcoes)
    e = proj.get("edl") or {}
    if not brutas or not e.get("manter"):
        return {"linhas": [], "cinetica": None, "estilo": leg, "aviso": aviso or "sem EDL/palavras do bruto: a prévia usa a legenda salva"}
    ws = _remapear(brutas, manter or e["manter"])
    p = proj["props"]
    if str(leg.get("animacao") or "").lower() in CINETICAS:
        from editor_video.acabamento import legenda_cinetica_props
        return {"linhas": [], "cinetica": legenda_cinetica_props(leg, {"palavras": ws}, proj.get("formato") or "9x16", p["largura"], p["altura"]), "estilo": leg, "aviso": aviso}
    if leg.get("maiusculas"):
        ws = [{**w, "palavra": str(w["palavra"]).upper()} for w in ws]
    return {"linhas": _linhas_previa(ws, leg), "cinetica": None, "estilo": leg, "aviso": aviso}


def _mesma_edl(a: list, b: list) -> bool:
    return len(a) == len(b) and all(abs(float(x["inicio"]) - float(y["inicio"])) < 1e-3 and abs(float(x["fim"]) - float(y["fim"])) < 1e-3 for x, y in zip(a, b))


def preparar_edl_e_legenda(pasta_proj: Path, props: dict, manter: list | None, estilo: str | None, correcoes: dict | None) -> tuple:
    """Antes do render: recorta o bruto se a EDL mudou (vídeo novo em midia/render, duração real, fundo desfocado) e refaz a legenda no estilo
    pedido (ASS ou cinética) a partir das palavras do bruto. Devolve (props, avisos, legenda_refeita). Atualiza projeto.json (edl, legenda_estilo, props)."""
    from editor_video import cortes as ct, legenda as lg
    from editor_video.acabamento import legenda_cinetica_props, fundo_desfocado
    from editor_video.util import info_midia
    proj = json.loads((pasta_proj / "projeto.json").read_text(encoding="utf-8")); e = proj.get("edl") or {}
    avisos = []; props = dict(props)
    mudou_edl = bool(manter) and not _mesma_edl(manter, e.get("manter") or [])
    atual = estilo_legenda_atual(pasta_proj, proj)
    mudou_estilo = bool(estilo) and estilo != atual.get("id")
    if not (mudou_edl or mudou_estilo):
        return props, avisos, False
    brutas, av = palavras_bruto(pasta_proj, proj, correcoes)
    if av:
        avisos.append(av)
    m_final = [{"id": int(m.get("id", i)), "inicio": round(float(m["inicio"]), 3), "fim": round(float(m["fim"]), 3)} for i, m in enumerate(manter or e.get("manter") or [])]
    durs = None
    if mudou_edl:
        bruto = _local(e.get("bruto"))
        if not bruto:
            raise ValueError("O bruto deste projeto não está acessível: não dá para aparar os cortes.")
        if any(m["fim"] - m["inicio"] < 0.1 for m in m_final):
            raise ValueError("Há trecho com menos de 0,1 s.")
        rid = time.strftime("%Y%m%d%H%M%S"); m_dir = pasta_proj / "midia" / "render"
        edl_tmp = pasta_proj / "edl_editada.json"
        edl_tmp.write_text(json.dumps({"manter": m_final}, ensure_ascii=False), encoding="utf-8")
        novo = m_dir / f"edl-{rid}.mp4"
        ct.aplicar_cortes(bruto, str(edl_tmp), str(novo))
        info = info_midia(novo); durs = ct.duracoes_reais(m_final, info_midia(bruto).get("fps") or props.get("fps") or 30)
        props["video"] = novo.name; props["duracao_s"] = info["duracao_s"]
        if props.get("video_fundo"):
            f = fundo_desfocado(novo, m_dir / f"edl-{rid}-fundo.mp4", props["largura"], props["altura"])
            if f:
                props["video_fundo"] = Path(f).name
            else:
                props.pop("video_fundo", None)
        e = {**e, "manter": m_final}; proj["edl"] = e
        if props.get("cortes_s") is not None and not props.get("camera"):  # clarão/whoosh do modo antigo
            acc, pts = 0.0, []
            for d_ in durs[:-1]:
                acc += d_; pts.append(round(acc, 3))
            props["cortes_s"] = pts
    refeita = False
    if brutas:
        ws = _remapear(brutas, m_final, durs)
        leg = _bloco_estilo(estilo) if mudou_estilo else atual["legenda"]
        eid = estilo if mudou_estilo else atual.get("id")
        tinha = atual["modo"] != "nenhuma" or mudou_estilo
        ass = pasta_proj / "legenda.ass"
        if tinha and str(leg.get("animacao") or "").lower() in CINETICAS:
            props["legenda_cinetica"] = legenda_cinetica_props(leg, {"palavras": ws}, proj.get("formato") or "9x16", props["largura"], props["altura"])
            if ass.exists():
                (pasta_proj / "historico").mkdir(exist_ok=True)
                ass.replace(pasta_proj / "historico" / f"legenda-antes-cinetica-{time.strftime('%Y%m%d-%H%M%S')}.ass")
            proj.setdefault("acabamento", {})["legenda"] = False; refeita = True
        elif tinha and leg:
            pj = pasta_proj / "palavras_cortado.json"
            pj.write_text(json.dumps({"palavras": ws}, ensure_ascii=False), encoding="utf-8")
            lg.gerar_legenda(str(pj), str(ass), {"legenda": leg}, formato=proj.get("formato") or "9x16")
            props.pop("legenda_cinetica", None); proj.setdefault("acabamento", {})["legenda"] = True; refeita = True
        if mudou_edl and props.get("segmentos"):  # zoom por frase (modo antigo): frases da transcrição no tempo novo
            pal = json.loads((pasta_proj / (e.get("palavras") or "palavras_bruto.json")).read_text(encoding="utf-8"))
            segs = []
            for s in pal.get("segmentos") or []:
                r = _remapear([{"palavra": s.get("texto", ""), "inicio": s["inicio"], "fim": s["fim"]}], m_final, durs)
                if r:
                    segs.append({"inicio": r[0]["inicio"], "fim": r[0]["fim"], "texto": s.get("texto", "")})
            props["segmentos"] = sorted(segs, key=lambda s: s["inicio"])
        # o texto corrigido fica nas palavras do bruto: as próximas trocas de estilo/corte já saem certas
        f = pasta_proj / (e.get("palavras") or "palavras_bruto.json")
        d = json.loads(f.read_text(encoding="utf-8")); d["palavras"] = [{k: v for k, v in w.items() if k != "_i"} for w in brutas]
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        proj["legenda_estilo"] = {"id": eid, "legenda": leg}
    elif mudou_estilo:
        avisos.append("sem as palavras do bruto não dá para trocar o estilo da legenda")
    proj["props"] = props
    _gravar(pasta_proj, proj)
    return props, avisos, refeita
