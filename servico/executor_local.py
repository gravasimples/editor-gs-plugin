"""Executor local do Editor GS (10/11/2026): substitui o Paperclip.

O gateway falava com o Paperclip por uma dúzia de rotas (issues, comments, runs, interactions, agents, heartbeat-runs). Este
módulo oferece as MESMAS rotas e os mesmos campos, guardando tudo em SQLite (`workspace/executor/executor.db`) e rodando o
agente direto pelo `claude -p` (stream-json), com o `workspace/AGENTS.md` como system prompt e o MCP `editor-de-video`.
Assim o gateway (`servico/api.py`) e o `AGENTS.md` continuam iguais; só muda quem atende.

Duas portas de entrada para o mesmo núcleo:
  - em processo: `Executor.chamar(metodo, url, json=...)` (o `_pc` do gateway usa isto no modo local);
  - HTTP: `rotas(executor)` devolve um APIRouter com as rotas `/api/...` (o agente usa por curl, como fazia com o Paperclip;
    `PAPERCLIP_API_URL` aponta para o próprio gateway). Comentário que chega por HTTP enquanto a issue tem rodada ativa é do
    agente (`authorAgentId`); o que chega em processo é do app/pessoa.

Estados da issue: todo (fila) → in_progress (rodando, ou aguardando decisão humana com interaction pendente) → in_review
(entregue) → done; blocked = pausado pelo app ou falha depois das tentativas; cancelled = lixeira.
Rodada: running → succeeded | failed | cancelled | timed_out.
"""
import asyncio, json, logging, os, re, signal, sqlite3, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from servico import plataforma

from fastapi import APIRouter, HTTPException, Request

log = logging.getLogger("editor-gs.executor")

ATIVOS = ("running", "queued", "pending", "starting")
FINAIS_HUMANO = ("done", "cancelled")
# Limite de uso/cota da conta (Claude: "session limit", "usage limit reached"; Codex/ChatGPT: "usage limit", "rate_limit_exceeded", 429,
# "insufficient_quota"): repetir no mesmo agente não adianta; o pedido troca na hora para o próximo da lista do fluxo (11/11/2026).
LIMITE_DE_USO = re.compile(r"session limit|usage limit|weekly limit|limit reached|rate[ _-]?limit|too many requests|\b429\b|quota|credit balance is too low|"
                           r"limite de uso|cota (do \w+ )?(esgotad|excedid|atingid)", re.I)


def limite_de_uso(*textos) -> bool:
    return any(t and LIMITE_DE_USO.search(str(t)) for t in textos)


# Vigia de ferramenta travada (11/11/2026, GRA-66 ficou 3 h numa chamada do MCP sem resposta): limite em minutos de uma chamada de
# ferramenta do MCP sem tool_result. Render e transcrição crescem com a duração do vídeo e têm folga larga; o resto responde em segundos.
# Ferramentas do próprio Claude (Bash, Read…) ficam de fora: têm timeout próprio.
VIGIA_PADRAO = {"padrao_min": 20, "graca_min": 3, "intervalo_s": 30,
                "por_ferramenta": {"montar_remotion": 90, "montar": 60, "montar_pip": 90, "montar_dividido": 90, "montar_antes_depois": 90, "montar_react": 90,
                                   "montar_locucao": 90, "animar_carrossel": 60, "narrar": 90, "dublar": 90, "transcrever": 90, "baixar_video": 60,
                                   "cortar_e_legendar": 45, "reenquadrar": 45, "reenquadrar_falante": 45, "encurtar_pausas": 45}}


def eventos_ferramenta(ev: dict):
    """Do stream-json do Claude: [('inicio', id, nome)] para cada tool_use do MCP e [('fim', id, None)] para cada tool_result."""
    out = []
    tipo = ev.get("type")
    if tipo not in ("assistant", "user"):
        return out
    for c in (ev.get("message") or {}).get("content") or []:
        if not isinstance(c, dict):
            continue
        if tipo == "assistant" and c.get("type") == "tool_use" and str(c.get("name", "")).startswith("mcp__"):
            out.append(("inicio", c.get("id"), str(c["name"]).rsplit("__", 1)[-1]))
        elif tipo == "user" and c.get("type") == "tool_result":
            out.append(("fim", c.get("tool_use_id"), None))
    return out


def ferramenta_travada(pendentes: dict, agora: float, cfg: dict | None = None):
    """pendentes = {tool_use_id: (nome, inicio_monotonic)}. Devolve (id, nome, minutos) da chamada mais antiga acima do limite, ou None."""
    cfg = {**VIGIA_PADRAO, **(cfg or {})}
    lim = {**VIGIA_PADRAO["por_ferramenta"], **(cfg.get("por_ferramenta") or {})}
    pior = None
    for tid, (nome, t0) in pendentes.items():
        idade = (agora - t0) / 60
        if idade > float(lim.get(nome, cfg["padrao_min"])) and (pior is None or idade > pior[2]):
            pior = (tid, nome, round(idade, 1))
    return pior


def trabalhadores_do_mcp(arvore: list) -> list:
    """Na árvore abaixo do `claude` (plataforma.descendentes), os processos de trabalho abertos pelos servidores MCP (ffmpeg, node do
    Remotion, python de worker…): é o que segura a ferramenta. O próprio servidor MCP não entra (sem ele o agente perde as ferramentas).
    No Windows o python.exe do venv é um lançador que abre o python real como filho: os dois contam como servidor. conhost fica de fora."""
    eh_servidor = lambda p: re.search(r"servidor\.py|[\\/]mcp[\\/]", p.get("cmd") or "", re.I)
    servidores = {p["pid"] for p in arvore if eh_servidor(p)}
    return [p for p in arvore if p["ppid"] in servidores and p["pid"] not in servidores and "conhost" not in (p.get("cmd") or "").lower()]


def _agora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _novo_id():
    return str(uuid.uuid4())


class Executor:
    def __init__(self, raiz: Path, cfg: dict, porta: int = 3200, workspace: Path | None = None):
        self.raiz = Path(raiz)
        self.cfg = cfg or {}
        self.porta = porta
        self.workspace = Path(workspace) if workspace else self.raiz / "workspace"
        pasta = self.cfg.get("pasta") or "workspace/executor"
        self.pasta = Path(pasta) if Path(pasta).is_absolute() else self.raiz / pasta
        self.logs = self.pasta / "run-logs"
        self.prefixo = self.cfg.get("prefixo", "GRA")
        self.company_id = self.cfg.get("company_id") or "local"
        self.max_simultaneos = int(self.cfg.get("max_simultaneos", 1))
        self.tentativas = int(self.cfg.get("tentativas", 2))
        self.timeout_s = int(self.cfg.get("timeout_s", 3 * 3600))
        self.intervalo_s = float(self.cfg.get("intervalo_s", 2))
        self.espera_pos_result_s = float(self.cfg.get("espera_pos_result_s", 60))  # depois do `result` no stream, quanto o processo tem para fechar
        self.vigia_orfas_s = float(self.cfg.get("vigia_orfas_s", 60))  # de quanto em quanto tempo o laço procura rodadas `running` sem dono
        vf = self.cfg.get("vigia_ferramenta")  # false desliga; dict sobrepõe VIGIA_PADRAO
        self.vigia_ferramenta = None if vf is False else {**VIGIA_PADRAO, **(vf if isinstance(vf, dict) else {})}
        self.minhas: set[str] = set()  # rodadas disparadas por ESTA instância e ainda não concluídas
        self._trava = None  # arquivo executor.lock travado: só um processo roda a fila deste banco
        self.processos: dict[str, asyncio.subprocess.Process] = {}  # run_id → processo
        self.cancelados: set[str] = set()
        self.tarefas: set[asyncio.Task] = set()  # rodadas em andamento (referência viva; os testes esperam por elas)
        self._db = None
        self._laco_task = None
        self.antes_da_rodada = None  # gancho do gateway: f(issue, run, numero_rodada) antes de disparar (checkpoint da pasta de entrega)
        self.ao_limite_de_uso = None  # gancho do gateway: f(issue, agente, motivo) → id do próximo agente da lista do fluxo, ou None (todos já tentados)

    # ---------------------------------------------------------------- banco
    def db(self):
        if self._db is None:
            self.pasta.mkdir(parents=True, exist_ok=True); self.logs.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self.pasta / "executor.db", check_same_thread=False, isolation_level=None)
            self._db.row_factory = sqlite3.Row
            self._db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS issues (id TEXT PRIMARY KEY, numero INTEGER, identifier TEXT, status TEXT, assignee TEXT, created_at TEXT, updated_at TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS comments (id TEXT PRIMARY KEY, issue_id TEXT, created_at TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, issue_id TEXT, agent_id TEXT, status TEXT, created_at TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS interactions (id TEXT PRIMARY KEY, issue_id TEXT, status TEXT, created_at TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS contadores (nome TEXT PRIMARY KEY, valor INTEGER);
            CREATE INDEX IF NOT EXISTS ix_comments_issue ON comments(issue_id, created_at);
            CREATE INDEX IF NOT EXISTS ix_runs_issue ON runs(issue_id, created_at);
            CREATE INDEX IF NOT EXISTS ix_inter_issue ON interactions(issue_id, created_at);
            """)
        return self._db

    def _proximo_numero(self):
        db = self.db()
        row = db.execute("SELECT valor FROM contadores WHERE nome='issue'").fetchone()
        n = (row["valor"] if row else 0) + 1
        db.execute("INSERT OR REPLACE INTO contadores(nome, valor) VALUES('issue', ?)", (n,))
        return n

    def _issue_row(self, iid):
        return self.db().execute("SELECT data FROM issues WHERE id=?", (iid,)).fetchone()

    def _issue(self, iid, obrigatorio=True):
        r = self._issue_row(iid)
        if not r:
            if obrigatorio:
                raise HTTPException(404, f"Issue {iid} não encontrada")
            return None
        return self._com_run(json.loads(r["data"]))

    def _com_run(self, issue):
        """`activeRun` como o Paperclip devolvia: a rodada em andamento desta issue (ou None)."""
        r = self.db().execute("SELECT data FROM runs WHERE issue_id=? AND status IN ('running','queued') ORDER BY created_at DESC LIMIT 1", (issue["id"],)).fetchone()
        issue["activeRun"] = ({"id": json.loads(r["data"])["id"]} if r else None)
        return issue

    def _gravar_issue(self, issue):
        issue = {k: v for k, v in issue.items() if k != "activeRun"}
        self.db().execute("INSERT OR REPLACE INTO issues(id, numero, identifier, status, assignee, created_at, updated_at, data) VALUES(?,?,?,?,?,?,?,?)",
                          (issue["id"], issue.get("numero"), issue.get("identifier"), issue.get("status"), issue.get("assigneeAgentId"), issue.get("createdAt"), issue.get("updatedAt"), json.dumps(issue, ensure_ascii=False)))
        return issue

    def _atualizar_issue(self, iid, **campos):
        issue = self._issue(iid)
        issue.update({k: v for k, v in campos.items()})
        issue["updatedAt"] = _agora()
        return self._com_run(self._gravar_issue(issue))

    def _comments(self, iid):
        return [json.loads(r["data"]) for r in self.db().execute("SELECT data FROM comments WHERE issue_id=? ORDER BY created_at", (iid,))]

    def _novo_comment(self, iid, body, autor_agente=None, autor_usuario=None):
        c = {"id": _novo_id(), "issueId": iid, "body": body or "", "createdAt": _agora(), "authorAgentId": autor_agente, "authorUserId": autor_usuario}
        self.db().execute("INSERT INTO comments(id, issue_id, created_at, data) VALUES(?,?,?,?)", (c["id"], iid, c["createdAt"], json.dumps(c, ensure_ascii=False)))
        self._atualizar_issue(iid)
        return c

    def _runs(self, iid):
        return [json.loads(r["data"]) for r in self.db().execute("SELECT data FROM runs WHERE issue_id=? ORDER BY created_at", (iid,))]

    def _run(self, rid):
        r = self.db().execute("SELECT data FROM runs WHERE id=?", (rid,)).fetchone()
        if not r:
            raise HTTPException(404, f"Rodada {rid} não encontrada")
        return json.loads(r["data"])

    def _gravar_run(self, run):
        self.db().execute("INSERT OR REPLACE INTO runs(id, issue_id, agent_id, status, created_at, data) VALUES(?,?,?,?,?,?)",
                          (run["id"], run["issueId"], run.get("agentId"), run["status"], run["createdAt"], json.dumps(run, ensure_ascii=False)))
        return run

    def _interactions(self, iid):
        return [json.loads(r["data"]) for r in self.db().execute("SELECT data FROM interactions WHERE issue_id=? ORDER BY created_at", (iid,))]

    def _gravar_interaction(self, it):
        self.db().execute("INSERT OR REPLACE INTO interactions(id, issue_id, status, created_at, data) VALUES(?,?,?,?,?)",
                          (it["id"], it["issueId"], it["status"], it["createdAt"], json.dumps(it, ensure_ascii=False)))
        return it

    def pendentes(self, iid):
        return [i for i in self._interactions(iid) if i.get("status") == "pending"]

    # ---------------------------------------------------------------- agentes
    def agentes(self):
        out = []
        for a in self.cfg.get("agentes") or []:
            rodando = any(r["agent_id"] == a["id"] for r in self.db().execute("SELECT agent_id FROM runs WHERE status='running'"))
            out.append({"id": a["id"], "name": a.get("nome") or a["id"], "status": "running" if rodando else ("paused" if a.get("desligado") else "idle"),
                        "adapterType": f"{a.get('motor', 'claude')}_local",
                        "adapterConfig": {"model": a.get("modelo"), "effort": a.get("effort"), "cwd": str(self.workspace), "instructionsFilePath": str(self.workspace / "AGENTS.md"), "env": a.get("env") or {}}})
        return out

    def agente(self, aid):
        return next((a for a in (self.cfg.get("agentes") or []) if a["id"] == aid), None)

    # ---------------------------------------------------------------- API (em processo)
    async def chamar(self, metodo, url, json=None, **_):
        """Mesmo contrato do `_pc` do gateway: devolve dicionários/listas ou levanta HTTPException."""
        m = metodo.upper(); body = json or {}
        if url == "/api/health":
            return {"status": "ok", "version": "executor-local 1.0", "motor": "local"}
        r = re.match(r"^/api/companies/([^/]+)/(issues|agents)$", url)
        if r:
            if r.group(2) == "agents":
                return self.agentes()
            if m == "GET":
                return [self._com_run(json_loads(x["data"])) for x in self.db().execute("SELECT data FROM issues ORDER BY numero")]
            if m == "POST":
                return self.criar_issue(body)
        r = re.match(r"^/api/issues/([^/]+)$", url)
        if r:
            if m == "GET":
                return self._issue(r.group(1))
            if m == "PATCH":
                return self.patch_issue(r.group(1), body, por_agente=False)
        r = re.match(r"^/api/issues/([^/]+)/comments$", url)
        if r:
            if m == "GET":
                return self._comments(r.group(1))
            if m == "POST":
                self._issue(r.group(1))
                return self._novo_comment(r.group(1), body.get("body", ""), autor_usuario="app")
        r = re.match(r"^/api/issues/([^/]+)/runs$", url)
        if r and m == "GET":
            return self._runs(r.group(1))
        r = re.match(r"^/api/issues/([^/]+)/interactions$", url)
        if r:
            if m == "GET":
                return self._interactions(r.group(1))
            if m == "POST":
                return self.criar_interaction(r.group(1), body)
        r = re.match(r"^/api/issues/([^/]+)/interactions/([^/]+)/(accept|reject|respond)$", url)
        if r and m == "POST":
            return self.resolver_interaction(r.group(1), r.group(2), r.group(3), body)
        r = re.match(r"^/api/heartbeat-runs/([^/]+)/cancel$", url)
        if r and m == "POST":
            return await self.cancelar_run(r.group(1))
        r = re.match(r"^/api/heartbeat-runs/([^/]+)/log$", url)
        if r and m == "GET":
            run = self._run(r.group(1))
            return {"runId": run["id"], "logRef": run.get("logRef"), "content": None}
        raise HTTPException(404, f"Executor local: rota não existe ({m} {url})")

    def criar_issue(self, body):
        n = self._proximo_numero(); agora = _agora()
        issue = {"id": _novo_id(), "numero": n, "identifier": f"{self.prefixo}-{n}", "title": (body.get("title") or "Pedido")[:200], "description": body.get("description") or "",
                 "status": body.get("status") or "todo", "priority": body.get("priority") or "medium", "assigneeAgentId": body.get("assigneeAgentId"), "projectId": body.get("projectId"),
                 "companyId": self.company_id, "createdAt": agora, "updatedAt": agora, "startedAt": None, "completedAt": None, "tentativas": 0}
        return self._com_run(self._gravar_issue(issue))

    def patch_issue(self, iid, body, por_agente=False):
        issue = self._issue(iid); campos = {}
        for k in ("title", "description", "priority", "assigneeAgentId", "projectId"):
            if k in body:
                campos[k] = body[k]
        novo = body.get("status")
        if novo:
            campos["status"] = novo
            if novo == "done" and not issue.get("completedAt"):
                campos["completedAt"] = _agora()
            if novo == "todo":
                campos["tentativas"] = 0 if not por_agente else issue.get("tentativas", 0)
        if body.get("comment"):
            self._novo_comment(iid, body["comment"], autor_usuario=None if por_agente else "app", autor_agente=(issue.get("assigneeAgentId") if por_agente else None))
        return self._atualizar_issue(iid, **campos)

    def criar_interaction(self, iid, body, por_agente=True):
        issue = self._issue(iid)
        it = {"id": _novo_id(), "issueId": iid, "kind": body.get("kind") or "request_confirmation", "title": (body.get("title") or "Decisão")[:160], "summary": body.get("summary") or "",
              "payload": body.get("payload") or {}, "resolverPolicy": body.get("resolverPolicy") or "human_only", "continuationPolicy": body.get("continuationPolicy") or "wake_assignee",
              "status": "pending", "createdAt": _agora(), "resolvedAt": None, "resolution": None, "requesterAgentId": issue.get("assigneeAgentId") if por_agente else None}
        self._gravar_interaction(it); self._atualizar_issue(iid)
        return it

    def resolver_interaction(self, iid, itid, acao, body):
        it = next((x for x in self._interactions(iid) if x["id"] == itid), None)
        if not it:
            raise HTTPException(404, "Interaction não encontrada")
        if it.get("status") != "pending":
            raise HTTPException(409, "Interaction já resolvida")
        it["status"] = {"accept": "accepted", "reject": "rejected", "respond": "responded"}[acao]; it["resolvedAt"] = _agora(); it["resolution"] = body or {}
        self._gravar_interaction(it)
        titulo = it.get("title") or "decisão"
        if acao == "accept":
            texto = f"✅ Aprovado: {titulo}." + (f" {body.get('comment')}" if body.get("comment") else "")
        elif acao == "reject":
            texto = f"❌ Recusado: {titulo}." + (f" Motivo: {body.get('reason') or body.get('comment')}" if (body.get("reason") or body.get("comment")) else "")
        else:
            resp = body.get("response")
            if resp is None and body.get("answers"):
                resp = "; ".join(str(a.get("otherText") or ",".join(a.get("optionIds") or [])) for a in body["answers"])
            texto = f"💬 Resposta sobre \"{titulo}\": {resp or ''}"
        self._novo_comment(iid, texto, autor_usuario="voce")
        issue = self._issue(iid)
        if it.get("continuationPolicy", "wake_assignee") == "wake_assignee" and issue.get("status") in ("in_progress", "blocked", "in_review") and not issue.get("activeRun"):
            self._atualizar_issue(iid, status="todo", tentativas=0)
        return {"ok": True, "interaction": it}

    async def cancelar_run(self, rid):
        run = self._run(rid)
        proc = self.processos.get(rid)
        self.cancelados.add(rid)
        if proc and proc.returncode is None:
            try:
                plataforma.matar_arvore(proc.pid)
            except ProcessLookupError:
                pass
            except Exception as e:  # noqa: BLE001
                log.warning("cancelar %s: %s", rid, e)
            await asyncio.sleep(0)
        elif run["status"] in ATIVOS:  # rodada órfã (gateway reiniciou no meio)
            run.update({"status": "cancelled", "finishedAt": _agora(), "error": "cancelada"}); self._gravar_run(run)
        return {"status": "cancelled"}

    # ---------------------------------------------------------------- fila e execução
    def pausada(self):
        return (self.pasta / "PAUSA").exists()

    def pausar(self, motivo="", por=""):
        self.pasta.mkdir(parents=True, exist_ok=True)
        (self.pasta / "PAUSA").write_text(json.dumps({"desde": _agora(), "motivo": motivo, "por": por}, ensure_ascii=False), encoding="utf-8")

    def retomar(self):
        (self.pasta / "PAUSA").unlink(missing_ok=True)

    def rodando(self):
        return [json.loads(r["data"]) for r in self.db().execute("SELECT data FROM runs WHERE status='running'")]

    def proxima(self):
        """Issue mais antiga na fila (todo) com agente configurado; respeita `max_simultaneos` e um pedido por agente.
        Arquivo `PAUSA` na pasta do executor segura a fila: o pedido em andamento termina, nenhum novo começa."""
        if self.pausada():
            return None
        ativos = self.rodando()
        if len(ativos) >= self.max_simultaneos:
            return None
        ocupados = {r["agentId"] for r in ativos}
        for row in self.db().execute("SELECT data FROM issues WHERE status='todo' ORDER BY updated_at"):
            issue = json.loads(row["data"]); a = self.agente(issue.get("assigneeAgentId"))
            if a and not a.get("desligado") and a["id"] not in ocupados:
                return issue
        return None

    def result_do_log(self, run):
        """Último evento `type=result` gravado no ndjson da rodada (ou None). Serve para não jogar fora uma rodada que terminou
        mas não foi concluída (processo morto antes do fechamento, ou o gateway caiu entre o `result` e o fim do processo)."""
        ref = run.get("logRef")
        arq = self.logs / ref if ref else None
        if not arq or not arq.is_file():
            return None
        achado = None
        try:
            with arq.open(encoding="utf-8", errors="replace") as f:
                for linha in f:
                    if '\\"result\\"' not in linha and '"result"' not in linha:
                        continue
                    try:
                        chunk = json.loads(linha).get("chunk")
                        ev = json.loads(chunk) if isinstance(chunk, str) else None
                    except Exception:  # noqa: BLE001
                        continue
                    if isinstance(ev, dict) and ev.get("type") == "result":
                        achado = ev
        except OSError:
            return None
        return achado

    def recuperar_rodada(self, run, motivo="o gateway reiniciou durante a rodada"):
        """Fecha uma rodada `running` que nenhum processo vivo vai concluir. Com `result` no ndjson: conclui como se o processo
        tivesse fechado (entrega vira comentário, issue in_review; sem reexecutar). Sem `result`: falha e a issue volta à fila."""
        res = self.result_do_log(run)
        issue = self._issue(run["issueId"], obrigatorio=False)
        agente = self.agente(run.get("agentId")) or {"id": run.get("agentId"), "nome": run.get("agentId")}
        if res is not None:
            run["recuperada"] = True
            self._concluir(run["issueId"], run, agente, res, None, [], 0)
            log.info("rodada %s (%s) recuperada do log: %s", run["id"][:8], (issue or {}).get("identifier"), run.get("status"))
            return run.get("status")
        run.update({"status": "failed", "finishedAt": _agora(), "error": motivo}); self._gravar_run(run)
        if issue and issue.get("status") == "in_progress":
            self._atualizar_issue(issue["id"], status="todo")
            log.info("rodada órfã %s: %s de volta à fila", run["id"][:8], issue.get("identifier"))
        return "failed"

    def recuperar_orfas(self, motivo="o gateway reiniciou durante a rodada"):
        """Rodadas `running` que não são desta instância não têm mais processo (só o dono da trava roda a fila): recupera cada uma."""
        feitas = []
        for run in self.rodando():
            if run["id"] in self.minhas:
                continue
            feitas.append((run["id"], self.recuperar_rodada(run, motivo)))
        return feitas

    def _travar(self):
        """Trava exclusiva em `executor.lock` (o sistema solta quando o processo morre). 11/11/2026 (GRA-62): um teste com
        `with TestClient(api.app)` subiu um segundo executor no banco real, que marcou a rodada do gateway como órfã, disparou outra
        e morreu deixando-a `running` para sempre. Agora só quem tem a trava roda a fila e recupera órfãs."""
        if self._trava is not None:
            return True
        self.pasta.mkdir(parents=True, exist_ok=True)
        f = open(self.pasta / "executor.lock", "a+b")
        try:
            f.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        self._trava = f
        return True

    def soltar_trava(self):
        if self._trava is not None:
            try:
                self._trava.close()
            finally:
                self._trava = None

    async def laco(self):
        self.recuperar_orfas()
        ultima_vigia = time.monotonic()
        while True:
            try:
                if time.monotonic() - ultima_vigia >= self.vigia_orfas_s:
                    ultima_vigia = time.monotonic()
                    self.recuperar_orfas("rodada sem processo (outro executor a deixou running)")
                await self.rodar_uma_vez()
            except Exception as e:  # noqa: BLE001
                log.warning("laço do executor: %s", e)
            await asyncio.sleep(self.intervalo_s)

    def iniciar(self):
        if self._laco_task is None:
            if not self._travar():
                log.warning("executor: outro processo já roda a fila de %s; esta instância não executa nem recupera rodadas", self.pasta)
                return False
            self._laco_task = asyncio.get_running_loop().create_task(self.laco())
        return True

    async def rodar_uma_vez(self, esperar=False):
        """Pega a próxima da fila e dispara a rodada (em segundo plano, ou esperando o fim com `esperar=True`, para testes)."""
        issue = self.proxima()
        if not issue:
            return None
        agente = self.agente(issue["assigneeAgentId"])
        run = {"id": _novo_id(), "runId": None, "issueId": issue["id"], "agentId": agente["id"], "status": "running", "createdAt": _agora(), "startedAt": _agora(),
               "finishedAt": None, "error": None, "exitCode": None, "logRef": None, "model": agente.get("modelo"), "costUsd": None, "usage": None, "sessionId": None, "numTurns": None}
        run["runId"] = run["id"]; run["logRef"] = f"{run['id']}.ndjson"; run["donoPid"] = os.getpid()
        self.minhas.add(run["id"])
        if self.antes_da_rodada:
            try:
                self.antes_da_rodada(issue, run, len(self._runs(issue["id"])) + 1)
            except Exception as e:  # noqa: BLE001
                log.warning("antes da rodada (%s): %s", issue.get("identifier"), e)
        self._gravar_run(run)
        self._atualizar_issue(issue["id"], status="in_progress", startedAt=issue.get("startedAt") or _agora(), tentativas=int(issue.get("tentativas") or 0) + 1)
        tarefa = asyncio.ensure_future(self._executar(issue["id"], run, agente)); self.tarefas.add(tarefa); tarefa.add_done_callback(self.tarefas.discard)
        if esperar:
            await tarefa
        return run

    # ---- prompt e comando
    def api_url(self):
        return f"http://127.0.0.1:{self.porta}"

    def prompt(self, issue, agente, run):
        coments = self._comments(issue["id"])
        pend = self.pendentes(issue["id"])
        motivo = "novo pedido" if len(self._runs(issue["id"])) <= 1 else "nova mensagem, decisão ou retomada (leia a conversa inteira; o que já está em saida/ pode ser reaproveitado)"
        linhas = [f"Você é o agente {agente.get('nome') or agente['id']} (id {agente['id']}) do Editor GS. Esta rodada é sobre o pedido {issue.get('identifier')} (issue {issue['id']}).",
                  f"API local do Editor GS (faz o papel da API do Paperclip, sem autenticação): {self.api_url()}. Use-a como o AGENTS.md manda: "
                  f"`POST /api/issues/{issue['id']}/comments` (JSON {{\"body\": ...}}) para o plano e avisos curtos; `POST /api/issues/{issue['id']}/interactions` para pedir aprovação; "
                  f"`GET /api/issues/{issue['id']}` e `.../comments` para reler. Não mude o status da issue: o app cuida disso.",
                  f"Motivo da rodada: {motivo}.", "",
                  f"## Pedido {issue.get('identifier')}: {issue.get('title')}", issue.get("description") or "", ""]
        if coments:
            linhas.append("## Conversa até agora (em ordem)")
            for c in coments:
                quem = "editor (você)" if c.get("authorAgentId") else ("app" if c.get("authorUserId") == "app" else "pessoa")
                linhas.append(f"[{quem} · {(c.get('createdAt') or '')[:16]}]\n{c.get('body') or ''}\n")
        if pend:
            linhas.append("## Decisões ainda pendentes (não repita o pedido; aguarde)")
            linhas += [f"- {p.get('title')}: {p.get('summary')}" for p in pend]
            linhas.append("")
        linhas += ["## Como terminar a rodada",
                   "- Entrega: sua MENSAGEM FINAL é a entrega (seções `## Resumo`, `## Arquivos`, e as demais que o fluxo pedir). O app grava essa mensagem final na conversa e marca o pedido como entregue. Não precisa repetir a entrega em comentário.",
                   "- Precisa de decisão humana: crie a interaction e termine a rodada com uma mensagem curta dizendo o que aguarda. O app pausa o pedido e te acorda com a resposta na conversa.",
                   "- Não conseguiu concluir: diga o motivo na mensagem final, em uma frase objetiva.",
                   "- Nada roda em segundo plano: espere cada ferramenta devolver o JSON."]
        return "\n".join(linhas)

    def comando(self, agente, system_prompt_path: Path, run: dict | None = None):
        motor = agente.get("motor", "claude")
        if motor == "codex":
            # Codex CLI: lê o AGENTS.md da pasta de trabalho sozinho; eventos JSONL (item.completed/agent_message, turn.completed, turn.failed);
            # a mensagem final também vai para um arquivo (-o), que é o que o executor usa como entrega.
            cmd = [agente.get("comando") or plataforma.programa("codex"), "exec", "--json", "--skip-git-repo-check", "--dangerously-bypass-approvals-and-sandbox", "-C", str(self.workspace)]
            if run is not None:
                cmd += ["-o", str(self.logs / f"{run['id']}.ultima.txt")]
            if agente.get("modelo"):
                cmd += ["-m", agente["modelo"]]
            mcp = self.workspace / ".mcp.json"
            try:  # o mesmo MCP do Claude, passado por -c (não depende do ~/.codex/config.toml da máquina)
                for nome, cfg in (json.loads(mcp.read_text(encoding="utf-8")).get("mcpServers") or {}).items():
                    # json.dumps = string TOML válida: no Windows o caminho C:\Users\... entre aspas cruas virava escape \U inválido (11/11)
                    cmd += ["-c", f"mcp_servers.{nome}.command={json.dumps(str(cfg.get('command')))}"]
                    if cfg.get("args"):
                        cmd += ["-c", f"mcp_servers.{nome}.args={json.dumps(cfg['args'])}"]
            except Exception:  # noqa: BLE001
                pass
            for extra in (self.cfg.get("args_extras") or []) + (agente.get("args_extras") or []):
                cmd.append(str(extra))
            return cmd
        if motor != "claude":
            raise RuntimeError(f"motor {motor!r} ainda não disponível no executor local")
        cmd = [agente.get("comando") or plataforma.programa("claude"), "--print", "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions",
               "--append-system-prompt-file", str(system_prompt_path)]
        if agente.get("modelo"):
            cmd += ["--model", agente["modelo"]]
        if agente.get("effort"):
            cmd += ["--effort", str(agente["effort"])]
        mcp = self.workspace / ".mcp.json"
        if mcp.is_file():
            cmd += ["--mcp-config", str(mcp), "--strict-mcp-config"]
        for extra in (self.cfg.get("args_extras") or []) + (agente.get("args_extras") or []):
            cmd.append(str(extra))
        return cmd

    def ambiente(self, issue, run, agente):
        env = dict(os.environ)
        env.pop("CLAUDECODE", None); env.pop("CLAUDE_CODE_ENTRYPOINT", None)  # rodada nova, não "sessão dentro de sessão"
        env.update({"PAPERCLIP_API_URL": self.api_url(), "PAPERCLIP_API_KEY": "local", "PAPERCLIP_RUN_ID": run["id"], "PAPERCLIP_ISSUE_ID": issue["id"],
                    "PAPERCLIP_AGENT_ID": agente["id"], "EDITOR_GS_RAIZ": str(self.raiz), "EDITOR_GS_WORKSPACE": str(self.workspace)})
        for k, v in (agente.get("env") or {}).items():
            env[k] = os.path.expanduser(str(v))
        return env

    async def _executar(self, iid, run, agente):
        issue = self._issue(iid)
        arquivo_log = self.logs / run["logRef"]
        resultado, erro, stderr_fim, codigo = None, None, [], None
        try:
            prompt = self.prompt(issue, agente, run)
            # 13/11/2026: sem a cópia no workspace (instalação limpa), usa a do código em vez de o claude -p morrer com "file not found"
            sp = self.workspace / "AGENTS.md"
            cmd = self.comando(agente, sp if sp.is_file() else self.raiz / "workspace" / "AGENTS.md", run)
            env = self.ambiente(issue, run, agente)
            with arquivo_log.open("a", encoding="utf-8") as lg:
                lg.write(json.dumps({"ts": _agora(), "meta": {"cmd": cmd[:1] + [a for a in cmd[1:] if not a.startswith("/")], "model": agente.get("modelo"), "issue": issue.get("identifier"), "prompt_chars": len(prompt)}}) + "\n")
                proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(self.workspace), env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=256 * 1024 * 1024, **plataforma.flags_processo_proprio())  # linhas do stream-json podem passar de 64 KB (tool_result grande): o limite padrão do StreamReader derrubava a rodada (GRA-52, 10/11)
                self.processos[run["id"]] = proc
                proc.stdin.write(prompt.encode("utf-8")); await proc.stdin.drain(); proc.stdin.close()

                ultimo_texto, uso_codex, falha_codex = None, None, None
                viu_result = asyncio.Event(); encerrado_pos_result = False
                pendentes = {}  # tool_use_id → (ferramenta do MCP, início): o vigia olha as que não responderam
                travou = None  # mensagem do vigia quando ele encerrou a rodada

                async def ler_stdout():
                    nonlocal resultado, ultimo_texto, uso_codex, falha_codex
                    while True:
                        linha = await proc.stdout.readline()
                        if not linha:
                            break
                        t = linha.decode("utf-8", "replace").rstrip("\n")
                        lg.write(json.dumps({"ts": _agora(), "chunk": t}, ensure_ascii=False) + "\n"); lg.flush()
                        try:
                            ev = json.loads(t)
                        except Exception:
                            continue
                        if not isinstance(ev, dict):
                            continue
                        for qual, tid, nome in eventos_ferramenta(ev):
                            if qual == "inicio":
                                pendentes[tid] = (nome, time.monotonic())
                            else:
                                pendentes.pop(tid, None)
                        if ev.get("type") == "result":
                            resultado = ev; viu_result.set()
                        elif ev.get("type") == "item.completed" and (ev.get("item") or {}).get("type") == "agent_message":
                            ultimo_texto = (ev["item"].get("text") or "")
                        elif ev.get("type") == "turn.completed":
                            uso_codex = ev.get("usage")
                        elif ev.get("type") in ("turn.failed", "error"):
                            falha_codex = (ev.get("error") or {}).get("message") if isinstance(ev.get("error"), dict) else (ev.get("error") or ev.get("message") or "turn.failed")

                async def ler_stderr():
                    while True:
                        linha = await proc.stderr.readline()
                        if not linha:
                            break
                        t = linha.decode("utf-8", "replace").rstrip("\n")
                        stderr_fim.append(t); del stderr_fim[:-30]
                        lg.write(json.dumps({"ts": _agora(), "stderr": t}, ensure_ascii=False) + "\n")

                fim = asyncio.ensure_future(asyncio.gather(ler_stdout(), ler_stderr(), proc.wait()))
                sinal = asyncio.ensure_future(viu_result.wait())

                async def vigiar():
                    """Ferramenta do MCP sem resposta acima do limite: 1º encerra os processos de trabalho dela (a ferramenta devolve erro e o
                    agente segue ou tenta de novo); se em `graca_min` ela ainda não respondeu, encerra a rodada, que volta à fila pela tentativa."""
                    nonlocal travou
                    cfg = self.vigia_ferramenta; destravada = {}  # tool_use_id → instante do 1º passo
                    while not fim.done() and not viu_result.is_set():
                        await asyncio.sleep(float(cfg["intervalo_s"]))
                        t = ferramenta_travada(pendentes, time.monotonic(), cfg)
                        if not t or fim.done() or viu_result.is_set():
                            continue
                        tid, nome, minutos = t
                        if tid not in destravada:
                            arvore = await asyncio.to_thread(plataforma.descendentes, proc.pid)
                            alvos = trabalhadores_do_mcp(arvore)
                            for p in alvos:
                                try:
                                    await asyncio.to_thread(plataforma.matar_arvore, p["pid"], True)
                                except Exception:  # noqa: BLE001
                                    pass
                            destravada[tid] = time.monotonic()
                            msg = f"vigia: {nome} sem resposta há {minutos:.0f} min; {len(alvos)} processo(s) de trabalho encerrado(s)"
                            log.warning("rodada %s (%s): %s", run["id"][:8], issue.get("identifier"), msg)
                            lg.write(json.dumps({"ts": _agora(), "aviso": msg, "vigia": {"ferramenta": nome, "minutos": minutos, "encerrados": [p["pid"] for p in alvos]}}, ensure_ascii=False) + "\n"); lg.flush()
                            if alvos:
                                continue
                        elif time.monotonic() - destravada[tid] < float(cfg["graca_min"]) * 60:
                            continue
                        travou = f"a ferramenta {nome} travou ({minutos:.0f} min sem resposta)"
                        lg.write(json.dumps({"ts": _agora(), "aviso": f"vigia: {travou}; rodada encerrada"}, ensure_ascii=False) + "\n"); lg.flush()
                        self._novo_comment(iid, f"🔧 {travou[0].upper() + travou[1:]}. Encerrei esta rodada; o pedido volta à fila e continua do que já está em `saida/`.", autor_usuario="app")
                        await self._encerrar(proc, fim)
                        return

                vigia = asyncio.ensure_future(vigiar()) if self.vigia_ferramenta and agente.get("motor", "claude") == "claude" else None
                try:
                    await asyncio.wait({fim, sinal}, timeout=self.timeout_s, return_when=asyncio.FIRST_COMPLETED)
                    if travou and vigia is not None:
                        await asyncio.gather(vigia, return_exceptions=True)  # o vigia termina de encerrar a árvore
                    if not fim.done() and viu_result.is_set():
                        # o `result` já veio: o processo tem `espera_pos_result_s` para fechar; um neto (MCP, ffmpeg) segurando o pipe
                        # ou um processo que não sai não pode deixar a rodada `running` para sempre
                        await asyncio.wait({fim}, timeout=self.espera_pos_result_s)
                        if not fim.done():
                            log.warning("rodada %s: result recebido mas o processo não fechou em %.0f s; encerrando a árvore", run["id"][:8], self.espera_pos_result_s)
                            lg.write(json.dumps({"ts": _agora(), "aviso": f"processo não fechou {self.espera_pos_result_s:.0f} s depois do result; árvore encerrada"}) + "\n")
                            await self._encerrar(proc, fim); encerrado_pos_result = True
                    elif not fim.done():
                        erro = f"tempo esgotado ({self.timeout_s // 60} min)"
                        await self._encerrar(proc, fim)
                    exc = fim.exception() if fim.done() and not fim.cancelled() else None
                    if exc is not None and not isinstance(exc, asyncio.CancelledError):  # CancelledError = leitura cancelada por _encerrar
                        raise exc
                finally:
                    sinal.cancel()
                    if vigia is not None:
                        vigia.cancel()
                codigo = proc.returncode
                if travou:
                    erro = travou
                if encerrado_pos_result:
                    codigo = 0  # encerrado por nós depois do `result`: vale o que o result diz (sucesso ou is_error), não o código do kill
                if resultado is None and agente.get("motor") == "codex":  # monta o `result` no formato do Claude
                    arq = self.logs / f"{run['id']}.ultima.txt"
                    texto = arq.read_text(encoding="utf-8").strip() if arq.is_file() else (ultimo_texto or "")
                    if falha_codex or codigo != 0:
                        resultado = {"type": "result", "subtype": "error", "is_error": True, "result": falha_codex or texto or f"codex saiu com {codigo}", "usage": uso_codex}
                    else:
                        resultado = {"type": "result", "subtype": "success", "is_error": False, "result": texto, "usage": uso_codex}
        except Exception as e:  # noqa: BLE001
            erro = f"{type(e).__name__}: {e}"
            log.warning("rodada %s (%s): %s", run["id"][:8], issue.get("identifier"), erro)
        finally:
            self.processos.pop(run["id"], None)
        try:
            await self._concluir_rodada(iid, run, agente, resultado, erro, stderr_fim, codigo)
        except Exception as e:  # noqa: BLE001 (antes, uma exceção aqui sumia na tarefa e a rodada ficava running)
            log.exception("concluir rodada %s (%s): %s", run["id"][:8], issue.get("identifier"), e)
            if run.get("status") == "running":
                run.update({"status": "failed", "finishedAt": _agora(), "error": f"erro ao concluir: {type(e).__name__}: {e}"[:600]}); self._gravar_run(run)
        finally:
            self.minhas.discard(run["id"])

    async def _encerrar(self, proc, fim):
        """Mata a árvore do processo e espera os leitores; se um neto ainda segura os pipes, cancela a leitura e segue."""
        try:
            plataforma.matar_arvore(proc.pid, forcar=True)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.wait({fim}, timeout=min(10.0, max(1.0, self.espera_pos_result_s)))
        if not fim.done():
            fim.cancel()
            await asyncio.gather(fim, return_exceptions=True)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:  # noqa: BLE001
            pass

    async def _concluir_rodada(self, iid, run, agente, resultado, erro, stderr_fim, codigo):
        return self._concluir(iid, run, agente, resultado, erro, stderr_fim, codigo)

    def _concluir(self, iid, run, agente, resultado, erro, stderr_fim, codigo):
        cancelada = run["id"] in self.cancelados
        self.cancelados.discard(run["id"])
        texto = (resultado or {}).get("result") if isinstance((resultado or {}).get("result"), str) else None
        is_error = bool((resultado or {}).get("is_error")) or (resultado or {}).get("subtype", "success") not in ("success",)
        run.update({"finishedAt": _agora(), "exitCode": codigo, "costUsd": (resultado or {}).get("total_cost_usd"), "usage": (resultado or {}).get("usage"),
                    "sessionId": (resultado or {}).get("session_id"), "numTurns": (resultado or {}).get("num_turns"), "durationMs": (resultado or {}).get("duration_ms")})
        if cancelada:
            run.update({"status": "cancelled", "error": "cancelada pelo app"}); self._gravar_run(run)
            return
        if erro and erro.startswith("tempo esgotado"):
            run.update({"status": "timed_out", "error": erro})
        elif erro or codigo not in (0, None) or resultado is None or is_error:
            detalhe = erro or (texto if is_error and texto else None) or (resultado or {}).get("error") or ("; ".join(stderr_fim[-3:]) if stderr_fim else None) or f"saída {codigo}"
            run.update({"status": "failed", "error": str(detalhe)[:600]})
        else:
            run["status"] = "succeeded"
        self._gravar_run(run)
        issue = self._issue(iid, obrigatorio=False)
        if not issue or issue.get("status") != "in_progress":
            return  # o app (ou o agente) já mudou o estado durante a rodada: respeita
        if run["status"] == "succeeded":
            if texto and texto.strip():
                ja = any((c.get("authorAgentId") and _mesmo_texto(c.get("body"), texto)) for c in self._comments(iid)[-5:])
                if not ja:
                    self._novo_comment(iid, texto.strip(), autor_agente=agente["id"])
            if self.pendentes(iid):
                self._atualizar_issue(iid, tentativas=0)  # aguardando decisão humana: fica in_progress sem rodada
            else:
                self._atualizar_issue(iid, status="in_review", tentativas=0)
            return
        # limite de uso/cota: troca já para o próximo agente da lista do fluxo (sem gastar a 2ª tentativa nem esperar a reserva de 180 s)
        if run["status"] == "failed" and self.ao_limite_de_uso and limite_de_uso(run.get("error"), texto, *stderr_fim[-5:]):
            motivo = str(run.get("error") or "limite de uso")[:200]
            try:
                novo_id = self.ao_limite_de_uso(issue, agente, motivo)
            except Exception as e:  # noqa: BLE001
                log.warning("troca por limite de uso (%s): %s", issue.get("identifier"), e); novo_id = None
            novo = self.agente(novo_id) if novo_id else None
            de = agente.get("nome") or agente["id"]
            if novo and novo["id"] != agente["id"]:
                para = novo.get("nome") or novo["id"]
                run.update({"limiteDeUso": True, "trocadoPara": novo["id"]}); self._gravar_run(run)
                self._novo_comment(iid, f"⚡ Limite de uso: o {de} estourou a cota ({motivo}). Passando o pedido já para o {para}: leia a conversa inteira e os arquivos já em `saida/` antes de continuar; não repita o que já está bom.", autor_usuario="app")
                self._atualizar_issue(iid, status="todo", assigneeAgentId=novo["id"], tentativas=0)
                log.info("limite de uso: %s %s → %s (%s)", issue.get("identifier"), de, para, motivo)
                return
            run.update({"limiteDeUso": True}); self._gravar_run(run)
            self._novo_comment(iid, f"⚠ Limite de uso: o {de} estourou a cota ({motivo}) e não há outro agente livre na lista deste pedido. Retome quando a cota voltar ou troque o modelo.", autor_usuario="app")
            self._atualizar_issue(iid, status="blocked")
            log.info("limite de uso: %s %s sem próximo agente; bloqueado", issue.get("identifier"), de)
            return
        # falha ou tempo esgotado
        if int(issue.get("tentativas") or 0) < self.tentativas:
            log.info("rodada %s falhou (%s); %s volta à fila (tentativa %s de %s)", run["id"][:8], run.get("error"), issue.get("identifier"), issue.get("tentativas"), self.tentativas)
            self._atualizar_issue(iid, status="todo")
        else:
            self._novo_comment(iid, f"⚠ O agente não conseguiu concluir depois de {issue.get('tentativas')} tentativa(s): {run.get('error')}", autor_usuario="app")
            self._atualizar_issue(iid, status="blocked")

    # ---------------------------------------------------------------- importação do Paperclip
    def importar_paperclip(self, url_base: str, company_id: str, run_logs_dir: Path | None = None):
        """Copia issues, comentários, rodadas e interactions do Paperclip (API local) para o banco do executor. Idempotente: regrava pelo id.
        O contador de números continua do maior identifier importado."""
        import httpx
        cli = httpx.Client(base_url=url_base, timeout=60)
        issues = cli.get(f"/api/companies/{company_id}/issues").json()
        issues = issues if isinstance(issues, list) else issues.get("issues", issues.get("items", []))
        maior = 0; n_c = n_r = n_i = 0
        for i in issues:
            num = None
            m = re.match(rf"^{re.escape(self.prefixo)}-(\d+)$", i.get("identifier") or "")
            if m:
                num = int(m.group(1)); maior = max(maior, num)
            issue = {"id": i["id"], "numero": num, "identifier": i.get("identifier"), "title": i.get("title"), "description": i.get("description") or "", "status": i.get("status"),
                     "priority": i.get("priority"), "assigneeAgentId": i.get("assigneeAgentId"), "projectId": i.get("projectId"), "companyId": self.company_id,
                     "createdAt": i.get("createdAt"), "updatedAt": i.get("updatedAt"), "startedAt": i.get("startedAt"), "completedAt": i.get("completedAt"), "tentativas": 0, "importadoDe": "paperclip"}
            if issue["status"] == "in_progress":
                try:  # aguardando decisão humana (interaction pendente) continua in_progress; rodada interrompida volta à fila
                    its0 = cli.get(f"/api/issues/{i['id']}/interactions").json(); its0 = its0 if isinstance(its0, list) else its0.get("interactions", its0.get("items", []))
                    pend = any((x.get("status") or "pending") in ("pending", "open", "waiting") and not x.get("resolvedAt") for x in its0)
                except Exception:  # noqa: BLE001
                    pend = False
                if not pend:
                    issue["status"] = "todo"  # nenhuma rodada do Paperclip continua aqui
            self._gravar_issue(issue)
            try:
                cm = cli.get(f"/api/issues/{i['id']}/comments").json(); cm = cm if isinstance(cm, list) else cm.get("comments", cm.get("items", []))
                for c in cm:
                    self.db().execute("INSERT OR REPLACE INTO comments(id, issue_id, created_at, data) VALUES(?,?,?,?)", (c["id"], i["id"], c.get("createdAt"), json.dumps(
                        {"id": c["id"], "issueId": i["id"], "body": c.get("body") or "", "createdAt": c.get("createdAt"), "authorAgentId": c.get("authorAgentId"), "authorUserId": c.get("authorUserId") or ("app" if not c.get("authorAgentId") else None)}, ensure_ascii=False)))
                    n_c += 1
            except Exception as e:  # noqa: BLE001
                log.warning("importar comentários de %s: %s", i.get("identifier"), e)
            try:
                rs = cli.get(f"/api/issues/{i['id']}/runs").json(); rs = rs if isinstance(rs, list) else rs.get("runs", rs.get("items", []))
                for r in rs:
                    rid = r.get("runId") or r.get("id")
                    ref = None
                    if run_logs_dir:
                        for cand in run_logs_dir.rglob(f"{rid}*"):
                            ref = str(cand); break
                    st = r.get("status")
                    if st in ATIVOS:
                        st = "failed"
                    self._gravar_run({"id": rid, "runId": rid, "issueId": i["id"], "agentId": r.get("agentId"), "status": st, "createdAt": r.get("createdAt") or r.get("startedAt") or _agora(),
                                      "startedAt": r.get("startedAt"), "finishedAt": r.get("finishedAt"), "error": r.get("error") or r.get("errorCode"), "exitCode": None, "logRef": ref,
                                      "model": None, "costUsd": r.get("costUsd") or (r.get("usage") or {}).get("costUsd"), "usage": r.get("usage"), "sessionId": None, "numTurns": None, "importadoDe": "paperclip"})
                    n_r += 1
            except Exception as e:  # noqa: BLE001
                log.warning("importar rodadas de %s: %s", i.get("identifier"), e)
            try:
                its = cli.get(f"/api/issues/{i['id']}/interactions").json(); its = its if isinstance(its, list) else its.get("interactions", its.get("items", []))
                for it in its:
                    st = it.get("status") or "pending"
                    if st in ("open", "waiting"):
                        st = "pending"
                    self._gravar_interaction({"id": it["id"], "issueId": i["id"], "kind": it.get("kind"), "title": it.get("title"), "summary": it.get("summary"), "payload": it.get("payload") or {},
                                              "resolverPolicy": it.get("resolverPolicy"), "continuationPolicy": it.get("continuationPolicy"), "status": st, "createdAt": it.get("createdAt") or _agora(),
                                              "resolvedAt": it.get("resolvedAt"), "resolution": None, "requesterAgentId": it.get("requesterAgentId"), "importadoDe": "paperclip"})
                    n_i += 1
            except Exception as e:  # noqa: BLE001
                log.warning("importar interactions de %s: %s", i.get("identifier"), e)
        row = self.db().execute("SELECT valor FROM contadores WHERE nome='issue'").fetchone()
        if not row or row["valor"] < maior:
            self.db().execute("INSERT OR REPLACE INTO contadores(nome, valor) VALUES('issue', ?)", (maior,))
        return {"issues": len(issues), "comentarios": n_c, "rodadas": n_r, "interactions": n_i, "proximo_numero": maior + 1}

    def status(self):
        db = self.db()
        por = {r["status"]: r["n"] for r in db.execute("SELECT status, n FROM (SELECT status, COUNT(*) n FROM issues GROUP BY status)")}
        return {"modo": "local", "banco": str(self.pasta / "executor.db"), "issues": por, "rodando": [{"run": r["id"][:8], "issue": r["issueId"], "desde": r.get("startedAt")} for r in self.rodando()],
                "agentes": [{"id": a["id"][:8], "nome": a["name"], "modelo": a["adapterConfig"]["model"], "status": a["status"]} for a in self.agentes()], "proximo_numero": (db.execute("SELECT valor FROM contadores WHERE nome='issue'").fetchone() or {"valor": 0})["valor"] + 1}


def json_loads(s):
    return json.loads(s)


def _mesmo_texto(a, b):
    n = lambda t: re.sub(r"\s+", " ", (t or "")).strip()[:400]
    return n(a) == n(b)


# -------------------------------------------------------------------- rotas HTTP (o agente usa por curl)
def rotas(ex: Executor) -> APIRouter:
    r = APIRouter()

    async def _json(req: Request):
        try:
            return await req.json() if (await req.body()) else {}
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "JSON inválido")

    @r.get("/api/health")
    async def health():
        return await ex.chamar("GET", "/api/health")

    @r.get("/api/companies/{cid}/agents")
    async def agents(cid: str):
        return ex.agentes()

    @r.get("/api/companies/{cid}/issues")
    async def issues(cid: str):
        return await ex.chamar("GET", f"/api/companies/{cid}/issues")

    @r.post("/api/companies/{cid}/issues")
    async def issue_nova(cid: str, req: Request):
        return ex.criar_issue(await _json(req))

    @r.get("/api/issues/{iid}")
    async def issue(iid: str):
        return ex._issue(iid)

    @r.patch("/api/issues/{iid}")
    async def issue_patch(iid: str, req: Request):
        return ex.patch_issue(iid, await _json(req), por_agente=bool(ex._issue(iid).get("activeRun")))

    @r.get("/api/issues/{iid}/comments")
    async def comments(iid: str):
        return ex._comments(iid)

    @r.post("/api/issues/{iid}/comments")
    async def comment_novo(iid: str, req: Request):
        issue = ex._issue(iid); b = await _json(req)
        if issue.get("activeRun"):
            run = ex._run(issue["activeRun"]["id"])
            return ex._novo_comment(iid, b.get("body", ""), autor_agente=run.get("agentId"))
        return ex._novo_comment(iid, b.get("body", ""), autor_usuario="app")

    @r.get("/api/issues/{iid}/runs")
    async def runs(iid: str):
        return ex._runs(iid)

    @r.get("/api/issues/{iid}/interactions")
    async def interactions(iid: str):
        return ex._interactions(iid)

    @r.post("/api/issues/{iid}/interactions")
    async def interaction_nova(iid: str, req: Request):
        return ex.criar_interaction(iid, await _json(req), por_agente=True)

    @r.post("/api/issues/{iid}/interactions/{itid}/{acao}")
    async def interaction_resolver(iid: str, itid: str, acao: str, req: Request):
        if acao not in ("accept", "reject", "respond"):
            raise HTTPException(404, "ação desconhecida")
        return ex.resolver_interaction(iid, itid, acao, await _json(req))

    @r.post("/api/heartbeat-runs/{rid}/cancel")
    async def run_cancel(rid: str):
        return await ex.cancelar_run(rid)

    @r.get("/api/heartbeat-runs/{rid}/log")
    async def run_log(rid: str):
        return await ex.chamar("GET", f"/api/heartbeat-runs/{rid}/log")

    return r


# -------------------------------------------------------------------- linha de comando
def _processo_vivo(pid: int) -> bool:
    try:
        if os.name == "nt":
            import subprocess
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=15)
            return f'"{pid}"' in r.stdout
        os.kill(pid, 0); return True
    except Exception:  # noqa: BLE001
        return False


def _main(argv):
    import argparse
    from servico import caminhos as cam
    raiz = Path(__file__).resolve().parents[1]
    cfg = cam.config()  # config.json + config.local.json, e o MESMO banco do gateway (workspace da instalação), como em servico/api.py
    ecfg = dict(cfg.get("executor") or {}); pasta = ecfg.get("pasta") or ""
    ecfg["pasta"] = pasta if pasta and Path(pasta).is_absolute() else str(cam.WORKSPACE / "executor")
    ex = Executor(raiz, ecfg, porta=int(cfg.get("porta", 3200)), workspace=cam.WORKSPACE)
    p = argparse.ArgumentParser(description="Executor local do Editor GS")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    x = sub.add_parser("importar", help="copia issues/comentários/rodadas do Paperclip (precisa dele no ar)")
    x.add_argument("--url", default=cfg.get("paperclip_url", "http://localhost:3100")); x.add_argument("--company", default=cfg.get("company_id"))
    x.add_argument("--run-logs", default=str(Path.home() / ".paperclip" / "instances" / "default" / "data" / "run-logs"))
    sub.add_parser("fila")
    r = sub.add_parser("recuperar", help="fecha UMA rodada running sem processo: com result no ndjson conclui como sucesso (sem reexecutar); sem result, falha")
    r.add_argument("run_id"); r.add_argument("--forcar", action="store_true", help="mesmo se o processo dono da rodada parecer vivo")
    a = p.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(ex.status(), ensure_ascii=False, indent=1))
    elif a.cmd == "importar":
        print(json.dumps(ex.importar_paperclip(a.url, a.company, Path(a.run_logs) if a.run_logs else None), ensure_ascii=False, indent=1))
    elif a.cmd == "recuperar":
        run = ex._run(a.run_id)
        if run.get("status") != "running":
            print(f"rodada {a.run_id[:8]} já está {run.get('status')}; nada a fazer"); return
        dono = run.get("donoPid")
        if dono and not a.forcar and _processo_vivo(int(dono)):
            print(f"o processo {dono} que disparou a rodada ainda existe; não mexo (use --forcar se tiver certeza)"); return
        print(json.dumps({"run": a.run_id, "status": ex.recuperar_rodada(run, "rodada sem processo (recuperada pela linha de comando)"),
                          "issue": {k: ex._issue(run["issueId"]).get(k) for k in ("identifier", "status")}}, ensure_ascii=False))
    elif a.cmd == "fila":
        for row in ex.db().execute("SELECT identifier, status, assignee, updated_at, data FROM issues WHERE status IN ('todo','in_progress','blocked') ORDER BY updated_at"):
            d = json.loads(row["data"]); print(f"{row['identifier']:8} {row['status']:12} {(row['assignee'] or '')[:8]} {row['updated_at'][:16]} {d.get('title', '')[:60]}")


if __name__ == "__main__":
    import sys
    _main(sys.argv[1:])
