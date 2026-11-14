#!/usr/bin/env python3
"""Importa um banco de referências em lote (10/11/2026) para o repertório do Editor GS.

O Raphael entrega uma lista (txt, csv ou md) com um link por linha; o script registra cada um como candidato
(`workspace/repertorio/candidatos.json`, fonte `lote-<arquivo>`) e, com `--aprovar --por Raphael`, baixa o vídeo
(yt-dlp; Instagram só com `.cookies/instagram.txt`), mede e cria a ficha; a decupagem (Gemini assiste) pode ficar
para depois, em lotes (`decupar --max 20`), porque cada vídeo gasta cota do Gemini.

Formato da lista (uma referência por linha; `#` comenta):
    https://www.instagram.com/reel/XXXX/ | fala_tela | nota livre (criador, por que gostou)
    https://youtube.com/shorts/YYYY | anuncio
    https://www.tiktok.com/@perfil/video/123          ← sem formato: usa --formato
CSV com cabeçalho também vale: url,formato,nota

Uso (na raiz do editor-gs, com o venv):
    ~/.venvs/editor-gs/bin/python scripts/referencias_lote.py importar lista.txt --formato fala_tela
    ~/.venvs/editor-gs/bin/python scripts/referencias_lote.py importar lista.txt --aprovar --por Raphael --sem-decupar
    ~/.venvs/editor-gs/bin/python scripts/referencias_lote.py decupar --max 20
    ~/.venvs/editor-gs/bin/python scripts/referencias_lote.py status

Nada entra no repertório sem `--por <humano>`: a lista é a decisão do Raphael. Referência é estudo, nunca material de entrega.
"""
import argparse, csv, json, re, sys, time
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "mcp" / "editor-de-video"))
from editor_video import garimpo, repertorio  # noqa: E402
from editor_video.util import ErroFerramenta, ler_json, salvar_json  # noqa: E402

URL_RE = re.compile(r"https?://[^\s|,;\"']+", re.I)


def ler_lista(arquivo: Path, formato_padrao: str):
    """Devolve (itens, problemas). Cada item: {url, formato, notas}."""
    texto = arquivo.read_text(encoding="utf-8-sig")
    itens, problemas, vistos = [], [], set()
    linhas = [l for l in texto.splitlines()]
    csv_header = linhas and "url" in linhas[0].lower() and "," in linhas[0]
    registros = []
    if csv_header:
        for r in csv.DictReader(linhas):
            registros.append(((r.get("url") or "").strip(), (r.get("formato") or "").strip(), (r.get("nota") or r.get("notas") or r.get("criador") or "").strip(), r))
    else:
        for n, l in enumerate(linhas, 1):
            l = l.strip()
            if not l or l.startswith("#"):
                continue
            partes = [p.strip() for p in re.split(r"\s*\|\s*", l)]
            m = URL_RE.search(partes[0])
            if not m:
                problemas.append(f"linha {n}: sem link ({l[:60]})"); continue
            url = m.group(0).rstrip(".,)")
            resto = [p for p in partes[1:]]
            fmt = next((p for p in resto if p in repertorio.FORMATOS), "")
            nota = " ".join(p for p in resto if p != fmt).strip()
            registros.append((url, fmt, nota, n))
    for url, fmt, nota, ref in registros:
        if not URL_RE.match(url):
            problemas.append(f"{ref}: link inválido ({url[:60]})"); continue
        fmt = fmt or formato_padrao
        if fmt and fmt not in repertorio.FORMATOS:
            problemas.append(f"{ref}: formato '{fmt}' não existe (use um de: {', '.join(repertorio.FORMATOS)})"); continue
        cid = garimpo._id(url)
        if cid in vistos:
            problemas.append(f"{ref}: repetido na lista ({cid})"); continue
        vistos.add(cid)
        itens.append({"url": url, "formato_visto": fmt, "notas": nota, "titulo": nota[:80] or cid, "criador": _criador(url)})
    return itens, problemas


def _criador(url):
    m = re.search(r"instagram\.com/([\w.]+)/(?:reels?|p)/", url) or re.search(r"tiktok\.com/@([\w.]+)/", url) or re.search(r"youtube\.com/@([\w.-]+)", url)
    return m.group(1) if m else ""


def _log(nome, dados):
    p = repertorio.WORKSPACE / "repertorio" / "lotes"; p.mkdir(parents=True, exist_ok=True)
    a = p / f"{nome}.json"; salvar_json(a, dados); return a


def importar(args):
    arquivo = Path(args.lista).expanduser()
    if not arquivo.exists():
        sys.exit(f"lista não encontrada: {arquivo}")
    itens, problemas = ler_lista(arquivo, args.formato or "")
    fonte = f"lote-{re.sub(r'[^a-z0-9]+', '-', arquivo.stem.lower()).strip('-')}"
    s = garimpo.salvar_candidatos(itens, fonte, busca=str(arquivo.name))
    print(f"Lista: {len(itens)} link(s) válido(s), {len(problemas)} problema(s). Candidatos novos: {len(s['novos'])}; já existiam: {len(s['ja_tinha'])}.")
    for p in problemas:
        print("  !", p)
    resultado = {"arquivo": str(arquivo), "fonte": fonte, "quando": datetime.now().isoformat(timespec="seconds"), "novos": s["novos"], "ja_tinha": s["ja_tinha"],
                 "problemas": problemas, "aprovados": [], "erros": []}
    if not args.aprovar:
        print("Sem --aprovar: ficam como candidatos 'aguardando' (listar_candidatos_referencia no MCP ou `status` aqui).")
        print("Log:", _log(f"{fonte}-{datetime.now():%Y%m%d-%H%M}", resultado)); return
    if not (args.por or "").strip():
        sys.exit("--aprovar exige --por <quem decidiu> (a lista é decisão humana)")
    base = garimpo._ler(); por_id = {c["id"]: c for c in base["candidatos"]}
    alvo = [cid for cid in s["novos"] + s["ja_tinha"] if por_id.get(cid, {}).get("estado") in (("aguardando", "erro") if args.refazer else ("aguardando",))]
    if args.max:
        alvo = alvo[: args.max]
    print(f"Aprovando {len(alvo)} candidato(s) por {args.por} (decupar={'não' if args.sem_decupar else 'sim'})…")
    for i, cid in enumerate(alvo, 1):
        c = por_id[cid]; fmt = c.get("formato_visto") or args.formato
        if not fmt:
            resultado["erros"].append({"id": cid, "erro": "sem formato (na linha ou em --formato)"}); print(f"  [{i}/{len(alvo)}] {cid}: sem formato"); continue
        t0 = time.time()
        try:
            r = garimpo.decidir_candidato(cid, "aprovar", args.por, formato=fmt, motivo=f"lote {arquivo.name}", decupar=not args.sem_decupar)
            resultado["aprovados"].append({"id": cid, "ficha": r.get("ficha"), "s": round(time.time() - t0)})
            print(f"  [{i}/{len(alvo)}] {cid} → ficha {r.get('ficha')} ({round(time.time() - t0)} s)")
        except ErroFerramenta as e:
            resultado["erros"].append({"id": cid, "url": c["url"], "erro": str(e)[:300]})
            print(f"  [{i}/{len(alvo)}] {cid}: ERRO {str(e)[:160]}")
        except Exception as e:  # noqa: BLE001
            resultado["erros"].append({"id": cid, "url": c["url"], "erro": f"{type(e).__name__}: {e}"[:300]})
            print(f"  [{i}/{len(alvo)}] {cid}: ERRO {type(e).__name__}: {str(e)[:140]}")
    print(f"Fichas criadas: {len(resultado['aprovados'])}; erros: {len(resultado['erros'])}.")
    ig = [e for e in resultado["erros"] if "instagram" in (e.get("url") or "") and "login" in e["erro"].lower()]
    if ig:
        print(f"  {len(ig)} do Instagram pediram login: exporte os cookies para .cookies/instagram.txt (docs/INSTAGRAM-COOKIES.md) e rode de novo com --refazer.")
    print("Log:", _log(f"{fonte}-{datetime.now():%Y%m%d-%H%M}", resultado))


def decupar(args):
    fichas = [ler_json(p) for p in sorted(repertorio._dir().glob("*/ficha.json"))]
    pend = [f for f in fichas if not f.get("decupagem") and (f.get("arquivos") or {}).get("video") and Path(f["arquivos"]["video"]).exists()]
    if args.max:
        pend = pend[: args.max]
    print(f"{len(pend)} ficha(s) para decupar (Gemini assiste ao vídeo; cada uma gasta cota).")
    feitas, erros = [], []
    for i, f in enumerate(pend, 1):
        t0 = time.time()
        try:
            r = repertorio.decupar_ficha(f["id"], video=f["arquivos"]["video"])
            feitas.append(f["id"]); print(f"  [{i}/{len(pend)}] {f['id']}: ok ({round(time.time() - t0)} s) padrões={json.dumps((r or {}).get('padroes', {}).get('tipos_grafismo', {}), ensure_ascii=False)[:80]}")
        except Exception as e:  # noqa: BLE001
            erros.append({"id": f["id"], "erro": str(e)[:300]}); print(f"  [{i}/{len(pend)}] {f['id']}: ERRO {str(e)[:160]}")
            if "429" in str(e) or "quota" in str(e).lower():
                print("  cota do Gemini: parando; rode de novo mais tarde."); break
        if args.pausa_s:
            time.sleep(args.pausa_s)
    print(f"Decupadas: {len(feitas)}; erros: {len(erros)}.")
    print("Log:", _log(f"decupagem-{datetime.now():%Y%m%d-%H%M}", {"feitas": feitas, "erros": erros}))


def status(_args):
    cs = garimpo._ler()["candidatos"]
    print(f"Candidatos: {len(cs)} — por estado: {dict(Counter(c['estado'] for c in cs))}")
    print(f"  por fonte: {dict(Counter(c.get('fonte') for c in cs))}")
    fichas = [ler_json(p) for p in sorted(repertorio._dir().glob("*/ficha.json"))]
    dec = [f for f in fichas if f.get("decupagem")]
    print(f"Fichas: {len(fichas)} (decupadas {len(dec)}) — por formato: {dict(Counter(f.get('formato') for f in fichas))}; por origem: {dict(Counter(f.get('origem') for f in fichas))}")
    erros = [c for c in cs if c["estado"] == "erro"]
    if erros:
        print(f"Com erro ({len(erros)}):")
        for c in erros[:15]:
            print(f"  - {c['id']}: {c.get('erro', '')[:120]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("importar", help="registra a lista como candidatos; com --aprovar baixa e cria as fichas")
    i.add_argument("lista"); i.add_argument("--formato", default="", help=f"formato padrão para linhas sem formato: {', '.join(repertorio.FORMATOS)}")
    i.add_argument("--aprovar", action="store_true"); i.add_argument("--por", default="", help="quem decidiu (ex.: Raphael)")
    i.add_argument("--sem-decupar", action="store_true", help="só baixa e mede; decupagem depois com `decupar`")
    i.add_argument("--refazer", action="store_true", help="tenta de novo os que ficaram em erro"); i.add_argument("--max", type=int, default=0)
    i.set_defaults(fn=importar)
    d = sub.add_parser("decupar", help="decupa (Gemini) as fichas ainda sem decupagem, em lotes")
    d.add_argument("--max", type=int, default=20); d.add_argument("--pausa-s", type=float, default=2.0); d.set_defaults(fn=decupar)
    s = sub.add_parser("status"); s.set_defaults(fn=status)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
