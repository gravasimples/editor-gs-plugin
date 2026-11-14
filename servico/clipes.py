"""Clipador do Editor GS: vídeo longo (live, aula, YouTube, call, mentoria) → cortes propostos pelo Editor → um pedido de edição por corte aprovado.
Pasta clipes/<id>/ guarda origem.mp4 (quando baixado de link) e clipe.json; os cortes propostos ficam em saida/<slug>/cortes.json."""
import json, re, shutil
from datetime import datetime
from pathlib import Path
from servico import referencias as refs

TIPOS = ("live", "youtube", "call", "aula", "outro")


class ErroClipe(Exception):
    pass


def ler_cortes(pasta_saida: Path):
    arq = pasta_saida / "cortes.json"
    if not arq.exists():
        return None
    d = json.loads(arq.read_text(encoding="utf-8"))
    # O fluxo de Reels também grava um cortes.json (silêncios removidos), sem a lista "cortes": não é proposta do Clipador.
    if not isinstance(d, dict) or not isinstance(d.get("cortes"), list):
        return None
    for i, c in enumerate(d["cortes"]):
        c.setdefault("id", f"c{i + 1:02d}")
        c.setdefault("duracao", round(float(c.get("fim", 0)) - float(c.get("inicio", 0)), 2))
    return d


def ler_estado(pasta_saida: Path):
    arq = pasta_saida / "clipes_estado.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"editados": {}}


def gravar_estado(pasta_saida: Path, estado: dict):
    (pasta_saida / "clipes_estado.json").write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")


def pedido_propor(origem_rel: str, tipo_origem: str, nota: str, n: int = 10):
    partes = [f"Clipador: proponha os melhores cortes deste vídeo longo (`{origem_rel}`, origem: {tipo_origem}) com o fluxo cortes-longos, fase PROPOR, entre 6 e {max(6, n)} cortes."]
    if nota:
        partes.append(f"O que buscamos: {nota}")
    partes.append("Grave `cortes.json` na pasta de saída; resumo e pendências vão na mensagem final (`## Resumo`, `## Pendências`), sem relatorio.md. Não extraia nem edite nada; eu escolho os cortes no app.")
    return " ".join(partes)


def pedido_kit(origem_rel: str, tipo_origem: str, nota: str, n_reels: int = 3, pecas=("reels", "carrossel", "stories", "youtube")):
    """Kit de derivação (03/11/2026): a gravação longa vira um pacote de mídias num pedido só (fluxo kit-derivacao)."""
    n_reels = max(1, min(5, int(n_reels or 3)))
    nomes = {"reels": f"{n_reels} Reels prontos dos melhores trechos", "carrossel": "carrossel com os pontos principais", "stories": "3 telas de Stories", "youtube": "descrição e capítulos do YouTube (se a origem for vídeo longo horizontal)"}
    lista = [nomes[x] for x in ("reels", "carrossel", "stories", "youtube") if x in pecas]
    partes = [f"Kit de derivação: transforme este vídeo longo (`{origem_rel}`, origem: {tipo_origem}) num pacote de mídias com o fluxo kit-derivacao: " + "; ".join(lista) + "."]
    fora = [x for x in ("carrossel", "stories", "youtube") if x not in pecas]
    if fora:
        partes.append("Não faça: " + ", ".join(fora) + ".")
    if nota:
        partes.append(f"O que buscamos: {nota}")
    partes.append("Tudo na mesma pasta de saída, entregas e textos na mensagem final (seções `## ` do fluxo). Não publique nada.")
    return " ".join(partes)


def pedido_editar(origem_rel: str, transcricao_rel: str | None, corte: dict, tipo_origem: str):
    c = corte
    partes = [f"Clipador, fase EDITAR: extraia o corte {c['id']} de `{origem_rel}` (de {c['inicio']} s a {c['fim']} s, {c.get('titulo', '')}) com `extrair_trecho`"
              + (f" usando `{transcricao_rel}` para as palavras" if transcricao_rel else "") + " e siga o fluxo reels-padrao do passo 3 em diante, com o Revisor."]
    partes.append(f"Frase de impacto: \"{c.get('gancho', '')}\" (destaque: {c.get('destaque', '')}). Tema: {c.get('tema', '')}. Motivo: {c.get('motivo', '')}.")
    if tipo_origem == "call" or c.get("pessoas"):
        partes.append(f"Origem é call/mentoria; pessoas além do Thiago: {c.get('pessoas') or 'não informado'}. Aplique as regras de call do fluxo cortes-longos (sem dados pessoais; registre quem aparece; a publicação depende de autorização).")
    partes.append("Pode aplicar os cortes sem aprovação. Entregue 9:16 e 16:9, capa e CapCut; legenda do post, hashtags, título, gancho e pendências na mensagem final (seções `## `).")
    return " ".join(partes)


def slug_corte(slug_base: str, corte: dict):
    t = refs._slug(corte.get("titulo") or corte["id"], 30)
    return f"{slug_base[:40].rstrip('-')}-{corte['id']}-{t}"[:80]
