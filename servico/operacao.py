"""Painel Operação (espelho do painel do operador do Máquina, só o que faz sentido num app de uma pessoa): placa de vídeo (VRAM, uso), disco,
CPU/RAM, processos da voz clonada, Paperclip (saúde, agentes, pedidos em andamento/fila), gateway (tempo no ar) e versão do Claude Code.
Só leitura; sem custo; nada aqui muda estado."""
import os, shutil, subprocess, time
from pathlib import Path
from servico import plataforma

RAIZ = Path(__file__).resolve().parents[1]
INICIO = time.time()


def gpu():
    """nvidia-smi em CSV; None se não houver placa ou driver."""
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        nome, usado, total, util, temp = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        usado, total = int(float(usado)), int(float(total))
        return {"nome": nome, "vram_usada_mb": usado, "vram_total_mb": total, "vram_pct": round(100 * usado / max(1, total)), "uso_pct": int(float(util)) if util.replace(".", "").isdigit() else None, "temperatura_c": int(float(temp)) if temp.replace(".", "").isdigit() else None}
    except Exception:  # noqa
        return None


def disco(workspace: Path):
    try:
        t = shutil.disk_usage(workspace)
        return {"total_gb": round(t.total / 1e9, 1), "livre_gb": round(t.free / 1e9, 1), "usado_pct": round(100 * (t.total - t.free) / max(1, t.total))}
    except Exception:  # noqa
        return None


def cpu_ram():
    out = {}
    try:
        carga = os.getloadavg(); out["carga_1m"] = round(carga[0], 2); out["nucleos"] = os.cpu_count()
    except Exception:  # noqa
        pass
    out.update(plataforma.memoria())
    return out


def processos():
    """Processos de interesse: workers da voz (Qwen/Chatterbox), MCP editor-de-video, Paperclip, Remotion/ffmpeg em andamento."""
    padroes = {"voz_qwen": "voz_qwen_worker.py", "voz_chatterbox": "voz_clonada_worker.py", "mcp_editor": "editor-de-video/servidor.py", "paperclip": "paperclipai", "ffmpeg": "ffmpeg", "remotion": "remotion"}
    return plataforma.processos_com(padroes)


def claude_cli():
    try:
        exe = plataforma.claude_bin()
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
        return {"versao": (r.stdout or r.stderr).strip()[:60], "caminho": exe}
    except Exception as e:  # noqa
        return {"versao": None, "erro": str(e)[:80]}


def resumo(workspace: Path, paperclip: dict = None, pedidos: dict = None):
    """Junta tudo; `paperclip` e `pedidos` vêm do gateway (já lidos), para o módulo não depender de rede."""
    g = gpu()
    avisos = []
    if g and g["vram_pct"] >= 90:
        avisos.append("VRAM quase cheia: a voz clonada e a transcrição em GPU não cabem juntas; espere o worker descarregar (10 min ocioso) ou feche o que está usando a placa.")
    d = disco(workspace)
    if d and d["livre_gb"] < 10:
        avisos.append(f"Disco com só {d['livre_gb']} GB livres: limpe o trabalho na Biblioteca.")
    pr = processos()
    if pr["voz_qwen"] and pr["voz_chatterbox"]:
        avisos.append("Os dois motores da voz estão carregados ao mesmo tempo; a placa não cabe os dois.")
    return {"quando": time.strftime("%Y-%m-%dT%H:%M:%S"), "gateway": {"no_ar_desde": time.strftime("%Y-%m-%dT%H:%M", time.localtime(INICIO)), "no_ar_min": round((time.time() - INICIO) / 60)},
            "gpu": g, "disco": d, **cpu_ram(), "processos": pr, "claude": claude_cli(), "paperclip": paperclip, "pedidos": pedidos, "avisos": avisos}
