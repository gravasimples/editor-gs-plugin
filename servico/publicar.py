"""Publicar e guardar entregas do Editor GS: Publora (rascunho ou agendamento) e Google Drive (rclone).
Nada aqui roda sozinho: só o gateway chama, e só quando o Raphael clica no app.
Credenciais: PUBLORA_API_KEY (gerar em publora.com → API) e DRIVE_DESTINO (ex.: "gs:10. Mídias/Editor GS", remote do rclone)."""
import json, os, shutil, subprocess
from datetime import datetime
from pathlib import Path
import httpx

PUBLORA_BASE = "https://api.publora.com/api/v1"
RCLONE = shutil.which("rclone") or os.path.expanduser("~/.local/bin/rclone")


class ErroPublicacao(Exception):
    pass


def _chave():
    return os.environ.get("PUBLORA_API_KEY", "").strip()


class Publora:
    def __init__(self, chave: str | None = None, transport=None):
        self.chave = chave if chave is not None else _chave()
        if not self.chave:
            raise ErroPublicacao("Falta PUBLORA_API_KEY no .env (publora.com → API → Generate).")
        self.c = httpx.Client(base_url=PUBLORA_BASE, headers={"x-publora-key": self.chave}, timeout=60, transport=transport)
        self.transport = transport

    def _j(self, r: httpx.Response):
        if r.status_code >= 400:
            raise ErroPublicacao(f"Publora {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def contas(self):
        d = self._j(self.c.get("/platform-connections"))
        out = []
        for x in d.get("connections", []):
            pid = x.get("platformId", "")
            out.append({"platformId": pid, "plataforma": pid.split("-", 1)[0], "usuario": x.get("username"), "nome": x.get("displayName"),
                        "status": x.get("connectionStatus"), "token": x.get("tokenStatus")})
        return out

    def publicar(self, video: Path, legenda: str, plataformas: list[str], quando: str | None = None, titulo: str | None = None, capa: Path | None = None, tipo_instagram: str = "REELS"):
        """create-post (rascunho) → upload do vídeo → (opcional) capa do Reels → (opcional) agendar. Devolve o estado do post group.
        tipo_instagram: REELS (padrão) ou STORIES (docs.publora.com/platforms/instagram: `videoType: "STORIES"`; Story vai como vídeo de 3 s ou mais)."""
        video = Path(video)
        if not video.exists():
            raise ErroPublicacao(f"Vídeo não encontrado: {video}")
        if not plataformas:
            raise ErroPublicacao("Escolha pelo menos uma conta.")
        tipos = {p.split("-", 1)[0] for p in plataformas}
        settings = {}
        if "instagram" in tipos:
            settings["instagram"] = {"videoType": "STORIES" if (tipo_instagram or "").upper() == "STORIES" else "REELS"}
        if "youtube" in tipos:
            settings["youtube"] = {"title": (titulo or legenda.splitlines()[0] if legenda else video.stem)[:100], "privacy": "public", "madeForKids": False}
        corpo = {"content": legenda, "platforms": plataformas}
        if settings:
            corpo["platformSettings"] = settings
        criado = self._j(self.c.post("/create-post", json=corpo))
        pg = criado.get("postGroupId")
        if not pg:
            raise ErroPublicacao(f"create-post sem postGroupId: {json.dumps(criado)[:200]}")
        up = self._j(self.c.post("/get-upload-url", json={"fileName": video.name, "contentType": "video/mp4", "type": "video", "postGroupId": pg}))
        url, media_id = up.get("uploadUrl"), up.get("mediaId")
        if not url:
            raise ErroPublicacao(f"get-upload-url sem uploadUrl: {json.dumps(up)[:200]}")
        with video.open("rb") as f:
            r = httpx.Client(timeout=1800, transport=self.transport).put(url, content=f, headers={"Content-Type": "video/mp4"})
        if r.status_code >= 400:
            raise ErroPublicacao(f"Upload para o armazenamento da Publora falhou ({r.status_code}): {r.text[:200]}")
        if media_id:
            rc = self.c.post(f"/complete-media/{media_id}")
            if rc.status_code >= 400 and rc.status_code != 404:
                raise ErroPublicacao(f"complete-media {rc.status_code}: {rc.text[:200]}")
        resultado = {"postGroupId": pg, "status": "draft", "scheduledTime": None, "mediaId": media_id}
        if capa and "instagram" in tipos and settings["instagram"]["videoType"] == "REELS":
            resultado["capa"] = self.capa_reels(pg, Path(capa))
        if quando:
            ag = self._j(self.c.put(f"/update-post/{pg}", json={"status": "scheduled", "scheduledTime": quando}, headers={"Idempotency-Key": f"gs-agendar-{pg}"}))
            resultado.update({"status": "scheduled", "scheduledTime": ag.get("scheduledTime") or quando, "avisos": ag.get("warnings")})
        try:
            est = self.estado(pg)
            resultado["status"] = est.get("status") or resultado["status"]; resultado["posts"] = est.get("posts", [])
            if est.get("scheduledTime"):
                resultado["scheduledTime"] = est["scheduledTime"]
        except ErroPublicacao:
            pass
        return resultado

    def capa_reels(self, post_group_id: str, capa: Path):
        """Sobe a imagem como capa do Reels (multipart em /upload-instagram-cover) e prende ao post por update-post → platformSettings.instagram.coverUrl.
        Só vale para Reels; PNG/WebP viram JPEG na Publora; limite 8 MB."""
        if not capa.exists():
            raise ErroPublicacao(f"Capa não encontrada: {capa}")
        if capa.stat().st_size > 8 * 1024 * 1024:
            raise ErroPublicacao("Capa acima de 8 MB: reduza a imagem.")
        tipo = {".png": "image/png", ".webp": "image/webp"}.get(capa.suffix.lower(), "image/jpeg")
        with capa.open("rb") as f:
            rc = self._j(self.c.post("/upload-instagram-cover", data={"postGroupId": post_group_id}, files={"cover": (capa.name, f, tipo)}))
        url = (rc.get("cover") or {}).get("url")
        if not url:
            raise ErroPublicacao(f"upload-instagram-cover sem cover.url: {json.dumps(rc)[:200]}")
        self._j(self.c.put(f"/update-post/{post_group_id}", json={"platformSettings": {"instagram": {"videoType": "REELS", "coverUrl": url}}}, headers={"Idempotency-Key": f"gs-capa-{post_group_id}"}))
        return url

    def estado(self, post_group_id: str):
        d = self._j(self.c.get(f"/get-post/{post_group_id}"))
        posts = [{"plataforma": p.get("platform"), "platformId": p.get("platformId"), "status": p.get("status"), "postedId": p.get("postedId"),
                  "permalink": p.get("permalink"), "erro": (p.get("error") or {}).get("message")} for p in d.get("posts", [])]
        return {"postGroupId": post_group_id, "status": d.get("status"), "scheduledTime": d.get("scheduledTime"), "posts": posts}

    def apagar(self, post_group_id: str):
        return self._j(self.c.delete(f"/delete-post/{post_group_id}"))


# --- Google Drive via rclone ---------------------------------------------------------------------

def drive_destino():
    return os.environ.get("DRIVE_DESTINO", "").strip()


def drive_estado():
    tem_rclone = Path(RCLONE).exists()
    destino = drive_destino()
    remoto = destino.split(":", 1)[0] if ":" in destino else ""
    remoto_ok = False
    if tem_rclone and remoto:
        r = subprocess.run([RCLONE, "listremotes"], capture_output=True, text=True)
        remoto_ok = f"{remoto}:" in r.stdout.split()
    pendencias = []
    if not tem_rclone:
        pendencias.append("rclone não instalado (ver docs/PUBLICAR.md)")
    if not destino:
        pendencias.append("DRIVE_DESTINO vazio no .env (ex.: gs:10. Mídias/Editor GS)")
    elif tem_rclone and not remoto_ok:
        pendencias.append(f"remote '{remoto}' não configurado no rclone (rclone config)")
    return {"configurado": tem_rclone and bool(destino) and remoto_ok, "destino": destino, "pendencias": pendencias}


def salvar_drive(pasta: Path, slug: str, nomes: list[str]):
    est = drive_estado()
    if not est["configurado"]:
        raise ErroPublicacao("Drive não configurado: " + "; ".join(est["pendencias"]))
    destino = f"{est['destino'].rstrip('/')}/{slug}"
    enviados = []
    for nome in nomes:
        p = pasta / nome
        if not p.exists() or not p.is_file():
            raise ErroPublicacao(f"Arquivo não encontrado na entrega: {nome}")
        r = subprocess.run([RCLONE, "copyto", str(p), f"{destino}/{nome}"], capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            raise ErroPublicacao(f"rclone falhou em {nome}: {r.stderr[-300:]}")
        enviados.append(nome)
    return {"destino": destino, "arquivos": enviados, "link": link_privado(destino)}


def link_privado(destino: str):
    """Link da pasta no Drive SEM mudar permissão (só quem já tem acesso abre). Usa o ID da pasta via `rclone lsjson`;
    nunca `rclone link`, que tornaria a pasta pública para quem tiver o endereço."""
    pai, _, nome = destino.rpartition("/")
    r = subprocess.run([RCLONE, "lsjson", "--dirs-only", pai], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None
    try:
        for it in json.loads(r.stdout or "[]"):
            if it.get("Name") == nome and it.get("ID"):
                return f"https://drive.google.com/drive/folders/{it['ID']}"
    except json.JSONDecodeError:
        pass
    return None


# --- registro por entrega -------------------------------------------------------------------------

def registrar(pasta: Path, item: dict):
    """Acrescenta um registro em saida/<slug>/publicacoes.json (quem, quando, o quê)."""
    arq = pasta / "publicacoes.json"
    lista = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    lista.append({"quando": datetime.now().isoformat(timespec="seconds"), **item})
    arq.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    return lista


def registros(pasta: Path):
    arq = pasta / "publicacoes.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
