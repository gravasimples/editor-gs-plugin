"""Referências e concorrentes do Editor GS: vídeos ou links que a Grava Simples gostou e podem inspirar criativos.
Cada referência vive em workspace/referencias/<id>/ (referencia.json + arquivo de vídeo + analise.md escrita pelo Editor).
O gateway só guarda e baixa (yt-dlp); quem analisa e escreve a "versão do Thiago" é o Editor, por pedido humano."""
import json, re, shutil, subprocess, threading, unicodedata
from datetime import datetime
from pathlib import Path
from servico import plataforma

YTDLP = plataforma.exe_venv(plataforma.venv_editor_gs(), "yt-dlp")
NODE = plataforma.node()
COOKIES_DIR = Path(__file__).resolve().parents[1] / ".cookies"  # instagram.txt, youtube.txt… (fora do git; exportados do navegador do Raphael)


def cookies_para(url: str):
    """Arquivo de cookies (formato Netscape) para o domínio do link, se o Raphael exportou um."""
    plat = plataforma_de(url)
    for nome in (f"{plat}.txt", "cookies.txt"):
        p = COOKIES_DIR / nome
        if p.exists() and p.stat().st_size > 0:
            return p
    return None
FFPROBE = shutil.which("ffprobe") or "ffprobe"
URL_RE = re.compile(r"https?://[^\s<>\"]+", re.I)
PLATAFORMAS = (("instagram.com", "instagram"), ("tiktok.com", "tiktok"), ("youtu.be", "youtube"), ("youtube.com", "youtube"), ("facebook.com", "facebook"), ("fb.watch", "facebook"))


class ErroReferencia(Exception):
    pass


def plataforma_de(url: str):
    u = (url or "").lower()
    for dominio, nome in PLATAFORMAS:
        if dominio in u:
            return nome
    return "web" if u else "arquivo"


def _slug(texto, n=40):
    t = unicodedata.normalize("NFKD", (texto or "").lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n].strip("-")
    return t or "ref"


def _duracao(p: Path):
    try:
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=60)
        return round(float(r.stdout.strip()), 1) if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


class Referencias:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz); self.raiz.mkdir(parents=True, exist_ok=True)

    # --- leitura ---------------------------------------------------------------------------------
    def _pasta(self, rid: str):
        if not re.match(r"^[a-z0-9\-]{3,80}$", rid or ""):
            raise ErroReferencia("id inválido")
        return self.raiz / rid

    def ler(self, rid: str):
        pasta = self._pasta(rid); meta = pasta / "referencia.json"
        if not meta.exists():
            raise ErroReferencia(f"Referência não encontrada: {rid}")
        d = json.loads(meta.read_text(encoding="utf-8"))
        analise = pasta / "analise.md"
        d["analise"] = analise.read_text(encoding="utf-8") if analise.exists() else None
        d["arquivos"] = [p.name for p in sorted(pasta.iterdir()) if p.is_file() and p.name not in ("referencia.json",)]
        return d

    def listar(self):
        out = []
        for p in self.raiz.iterdir():
            if p.is_dir() and (p / "referencia.json").exists():
                try:
                    out.append(self.ler(p.name))
                except ErroReferencia:
                    pass
        return sorted(out, key=lambda d: d.get("criado", ""), reverse=True)

    def _gravar(self, d: dict):
        (self.raiz / d["id"] / "referencia.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return d

    # --- escrita ---------------------------------------------------------------------------------
    def criar(self, texto: str = "", url: str = "", arquivos_salvos: list[str] | None = None, por: str = "app"):
        """Cria a referência a partir de um link e/ou arquivos já gravados em uma pasta temporária (lista de caminhos)."""
        texto = (texto or "").strip(); url = (url or "").strip()
        if not url:
            m = URL_RE.search(texto)
            if m:
                url = m.group(0); texto = (texto[:m.start()] + texto[m.end():]).strip()
        if not url and not arquivos_salvos:
            raise ErroReferencia("Cole um link (Instagram, TikTok, YouTube) ou anexe um vídeo.")
        base = texto or (Path(arquivos_salvos[0]).stem if arquivos_salvos else url.rstrip("/").rsplit("/", 1)[-1])
        rid = f"{datetime.now():%Y-%m-%d}-{_slug(base)}"
        i = 2
        while (self.raiz / rid).exists():
            rid = f"{datetime.now():%Y-%m-%d}-{_slug(base)}-{i}"; i += 1
        pasta = self.raiz / rid; pasta.mkdir()
        nomes = []
        for a in arquivos_salvos or []:
            a = Path(a); destino = pasta / re.sub(r"[^\w.\-]+", "_", a.name)
            shutil.move(str(a), str(destino)); nomes.append(destino.name)
        video = next((n for n in nomes if n.lower().endswith((".mp4", ".mov", ".webm", ".mkv"))), None)
        d = {"id": rid, "criado": datetime.now().isoformat(timespec="seconds"), "por": por, "nota": texto, "url": url,
             "plataforma": plataforma_de(url) if url else "arquivo", "status": "pronto" if not url else "baixando",
             "titulo": texto[:80] or (video or url), "autor": None, "duracao_s": _duracao(pasta / video) if video else None,
             "video": video, "capa": None, "erro": None, "pedidos": []}
        return self._gravar(d)

    def baixar(self, rid: str):
        """Baixa o vídeo do link com yt-dlp (metadados + mp4 até 1080p + capa). Síncrono; o gateway chama numa thread."""
        d = self.ler(rid); pasta = self.raiz / rid
        if not d.get("url"):
            return d
        if not YTDLP.exists():
            d.update(status="erro", erro="yt-dlp não instalado no venv do editor-gs"); return self._gravar(d)
        cmd = [str(YTDLP), "--no-playlist", "--no-warnings", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4",
               "--write-thumbnail", "--convert-thumbnails", "jpg", "--print-json", "--no-simulate", "-o", str(pasta / "referencia.%(ext)s"), d["url"]]
        if NODE.exists():
            cmd[1:1] = ["--js-runtimes", f"node:{NODE}"]
        ck = cookies_para(d["url"])
        if ck:
            cmd[1:1] = ["--cookies", str(ck)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            d.update(status="erro", erro="download passou de 15 min"); return self._gravar(d)
        if r.returncode != 0:
            msg = (r.stderr or r.stdout).strip()[-400:] or "yt-dlp falhou"
            if "instagram" in d["url"].lower() and ("empty media response" in msg or "login" in msg.lower() or "cookies" in msg.lower()):
                msg += " | Instagram exige login: exporte os cookies do Chrome para .cookies/instagram.txt (ver Ajuda → Referências do Instagram)."
            d.update(status="erro", erro=msg); return self._gravar(d)
        info = {}
        for linha in r.stdout.splitlines():
            if linha.startswith("{"):
                try:
                    info = json.loads(linha)
                except Exception:
                    pass
        video = next((p.name for p in pasta.iterdir() if p.name.startswith("referencia.") and p.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov")), None)
        capa = next((p.name for p in pasta.iterdir() if p.name.startswith("referencia.") and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")), None)
        d.update(status="pronto" if video else "erro", erro=None if video else "yt-dlp não gerou vídeo", video=video, capa=capa,
                 titulo=(info.get("title") or d["titulo"])[:120], autor=info.get("uploader") or info.get("channel") or info.get("uploader_id"),
                 duracao_s=info.get("duration") or (_duracao(pasta / video) if video else None), plataforma=info.get("extractor_key", d["plataforma"]).lower().replace("youtubetab", "youtube"),
                 descricao_origem=(info.get("description") or "")[:1500], visualizacoes=info.get("view_count"), curtidas=info.get("like_count"), publicado=info.get("upload_date"))
        return self._gravar(d)

    def baixar_em_segundo_plano(self, rid: str):
        t = threading.Thread(target=self.baixar, args=(rid,), daemon=True); t.start(); return t

    def anotar_pedido(self, rid: str, issue: dict, tipo: str):
        d = self.ler(rid); d.setdefault("pedidos", []).append({"tipo": tipo, "issue_id": issue.get("id"), "codigo": issue.get("identifier"), "quando": datetime.now().isoformat(timespec="seconds")})
        d.pop("analise", None); d.pop("arquivos", None); return self._gravar(d)

    def atualizar(self, rid: str, **campos):
        d = self.ler(rid); d.pop("analise", None); d.pop("arquivos", None)
        for k, v in campos.items():
            if k in ("nota", "titulo", "status") and v is not None:
                d[k] = v
        return self._gravar(d)

    def apagar(self, rid: str):
        pasta = self._pasta(rid)
        if not (pasta / "referencia.json").exists():
            raise ErroReferencia(f"Referência não encontrada: {rid}")
        shutil.rmtree(pasta); return {"ok": True}


def pedido_analise(ref: dict):
    """Texto do pedido que manda o Editor analisar a referência (sem produzir vídeo)."""
    origem = f"link {ref['url']}" if ref.get("url") else "vídeo anexado"
    partes = [f"Analise esta referência ({origem}) com o fluxo referencia-analise.",
              f"Arquivos em `referencias/{ref['id']}/` (vídeo: `{ref.get('video') or 'ainda baixando'}`)."]
    if ref.get("nota"):
        partes.append(f"O que gostamos: {ref['nota']}")
    partes.append(f"Escreva `referencias/{ref['id']}/analise.md` e não edite nem publique nada.")
    return " ".join(partes)


def pedido_minha_versao(ref: dict):
    partes = [f"Quero a minha versão desta referência com o fluxo minha-versao: `referencias/{ref['id']}/` ({ref.get('titulo') or ref.get('url')})."]
    if ref.get("nota"):
        partes.append(f"O que gostamos nela: {ref['nota']}")
    partes.append("Primeiro o roteiro na voz do Thiago, com gancho, estrutura e texto na tela; se eu anexar vídeo bruto, edite com o reels-padrao depois do roteiro aprovado.")
    return " ".join(partes)
