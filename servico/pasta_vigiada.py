"""Pasta vigiada do Drive (03/11/2026): gravação nova numa pasta do Drive vira pedido no Editor GS sozinha.

O Thiago (ou quem gravar) solta o vídeo em `10. Mídias/Materiais para Editar` (ou noutra pasta do .env `DRIVE_PARA_EDITAR`).
A cada volta do laço das automações o app lista a pasta pelo rclone, espera o arquivo terminar de subir (tamanho igual em
duas leituras e 3+ min sem mudar), baixa a cópia para `entrada/_recebidos/<token>/` e abre o pedido. A subpasta escolhe o tipo:
"Kit" → kit de derivação, "Cortes"/"Live" → Clipador, "Profissional"/"Lista"/"Tutorial"/"Bastidor"/"POV"/"Opinião" → estilo do
Reel, raiz → Reel no estilo padrão (vídeo acima de 8 min vai para o Clipador). Um `.txt` com o mesmo nome do vídeo (ou
`pedido.txt` na pasta) entra como instrução do pedido.

Só lê o Drive: nada é movido, renomeado ou apagado lá. O estado (o que já virou pedido) fica em `servico/pasta_vigiada_estado.json`.
Na primeira leitura, arquivos com mais de 24 h ficam marcados como "já estavam" e não viram pedido."""
import json, os, re, secrets, subprocess, unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
from servico import caminhos as _cam
ESTADO = _cam.estado("pasta_vigiada_estado.json")
PADRAO = "gs:Grava Simples - Central/10. Mídias/Materiais para Editar"
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
EXT_TXT = {".txt", ".md"}
CONFIG = {"estavel_min": 3, "max_por_dia": 6, "longo_min": 8}
# subpasta (sem acento, minúscula) → como vira pedido
REGRAS = [("kit", {"modo": "kit"}), ("corte", {"modo": "clipador"}), ("live", {"modo": "clipador"}), ("longo", {"modo": "clipador"}),
          ("profissional", {"modo": "reel", "estilo": "profissional"}), ("lista", {"modo": "reel", "estilo": "lista"}),
          ("tutorial", {"modo": "reel", "estilo": "tutorial"}), ("bastidor", {"modo": "reel", "estilo": "bastidor"}),
          ("pov", {"modo": "reel", "estilo": "pov"}), ("opiniao", {"modo": "reel", "estilo": "opiniao"}),
          ("legendar", {"modo": "legendar"})]


def origem():
    return (os.environ.get("DRIVE_PARA_EDITAR") or "").strip() or PADRAO


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def regra_da_pasta(caminho: str):
    """Tipo do pedido pela primeira subpasta do caminho relativo ("Kit/aula.mp4" → kit). Raiz = Reel padrão."""
    partes = caminho.split("/")[:-1]
    for parte in partes:
        n = _norm(parte)
        for chave, regra in REGRAS:
            if chave in n:
                return {**regra, "pasta": parte}
    return {"modo": "reel", "estilo": "padrao", "pasta": partes[0] if partes else ""}


def estado(arq: Path = None):
    try:
        return json.loads((arq or ESTADO).read_text(encoding="utf-8"))
    except Exception:  # noqa
        return {}


def gravar(est: dict, arq: Path = None):
    (arq or ESTADO).write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")


def listar(rclone: str, raiz: str = None):
    """Arquivos da pasta (recursivo) pelo `rclone lsjson`. Erro do rclone vira exceção com a mensagem."""
    r = subprocess.run([rclone, "lsjson", "-R", "--files-only", raiz or origem()], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "rclone lsjson falhou").strip()[-300:])
    return json.loads(r.stdout or "[]")


def _chave(it):
    return it.get("ID") or it["Path"]


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:  # noqa
        return None


def prontos(itens: list, est: dict, agora: datetime = None, cfg: dict = None):
    """Decide o que vira pedido nesta leitura. Devolve (prontos, est atualizado). Atualiza `tamanhos` (para a regra das duas leituras)
    e, na primeira leitura, marca como `ja_estavam` os vídeos com mais de 24 h."""
    cfg = {**CONFIG, **(cfg or {})}; agora = agora or datetime.now(timezone.utc)
    vistos = est.setdefault("vistos", {}); tam = est.get("tamanhos") or {}; novo_tam = {}
    primeira = not est.get("primeira_leitura")
    textos = {it["Path"].rsplit(".", 1)[0].lower(): it for it in itens if Path(it["Path"]).suffix.lower() in EXT_TXT}
    saida = []
    for it in itens:
        if Path(it["Path"]).suffix.lower() not in EXT_VIDEO:
            continue
        k = _chave(it)
        if k in vistos:
            continue
        mod = _dt(it.get("ModTime")) or agora
        if primeira and agora - mod > timedelta(hours=24):
            vistos[k] = {"caminho": it["Path"], "estado": "ja_estavam", "quando": agora.isoformat(timespec="minutes")}; continue
        novo_tam[k] = it.get("Size")
        if tam.get(k) != it.get("Size") or agora - mod < timedelta(minutes=cfg["estavel_min"]):
            continue  # ainda subindo (ou primeira vez que vemos este tamanho)
        pasta = it["Path"].rsplit("/", 1)[0] if "/" in it["Path"] else ""
        txt = textos.get(it["Path"].rsplit(".", 1)[0].lower()) or textos.get(((pasta + "/") if pasta else "") + "pedido")
        saida.append({**it, "chave": k, "regra": regra_da_pasta(it["Path"]), "instrucao_arquivo": txt["Path"] if txt else None})
    est["tamanhos"] = novo_tam; est["primeira_leitura"] = est.get("primeira_leitura") or agora.isoformat(timespec="minutes")
    hoje = agora.astimezone(timezone(timedelta(hours=-3))).date().isoformat()
    feitos_hoje = sum(1 for v in vistos.values() if v.get("estado") == "pedido" and (v.get("quando") or "").startswith(hoje))
    return saida[:max(0, cfg["max_por_dia"] - feitos_hoje)], est


def baixar(rclone: str, caminho: str, destino: Path, raiz: str = None):
    destino.mkdir(parents=True, exist_ok=True)
    nome = caminho.rsplit("/", 1)[-1]
    r = subprocess.run([rclone, "copyto", f"{raiz or origem()}/{caminho}", str(destino / nome)], capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "rclone copyto falhou").strip()[-300:])
    return destino / nome


def ler_texto(rclone: str, caminho: str, raiz: str = None):
    r = subprocess.run([rclone, "cat", f"{raiz or origem()}/{caminho}"], capture_output=True, text=True, timeout=120)
    return (r.stdout or "").strip()[:2000] if r.returncode == 0 else ""


def novo_token():
    return "drive-" + secrets.token_hex(6)


def texto_pedido(item: dict, instrucao: str = "", duracao_s: float | None = None, cfg: dict = None):
    """Texto do pedido e o modo final (vídeo longo na raiz vai para o Clipador)."""
    cfg = {**CONFIG, **(cfg or {})}; regra = dict(item["regra"]); nome = item["Path"].rsplit("/", 1)[-1]
    if regra["modo"] == "reel" and not regra.get("pasta") and duracao_s and duracao_s > cfg["longo_min"] * 60:
        regra = {"modo": "clipador", "pasta": ""}
    origem_txt = f"Gravação nova na pasta do Drive \"{origem().split('/')[-1]}{('/' + regra['pasta']) if regra.get('pasta') else ''}\": `{nome}`."
    extra = f" Instrução de quem gravou: {instrucao}" if instrucao else ""
    if regra["modo"] == "legendar":
        texto = f"{origem_txt} Transcreva e legende este vídeo no estilo padrão, sem cortar nada. Entregue 9:16 com legenda queimada e o SRT separado.{extra}"
    elif regra["modo"] == "reel":
        texto = f"{origem_txt} Edite este vídeo com corte dinâmico, legenda no estilo {regra.get('estilo', 'padrao')} e entrega em 9:16 (e 16:9 se o vídeo for horizontal).{extra}"
    else:
        texto = (origem_txt + " " + instrucao).strip()
    return texto, regra
