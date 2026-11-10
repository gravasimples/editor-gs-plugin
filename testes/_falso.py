"""Executável falso nos testes (rclone, yt-dlp, claude, agy...). No POSIX o script com shebang já é executável; no Windows o CreateProcess não lê
shebang, então um `.cmd` ao lado chama o bash do Git (scripts sh) ou este Python (scripts python). Devolve o caminho a usar.
Cuidado do Windows: ao rodar um `.cmd`, o cmd.exe re-interpreta argumentos com `<`, `>`, `&`, `|`. Onde o código sob teste passa argumentos
assim (ex.: `-f bv*[height<=1080]` do yt-dlp), troque o `subprocess` do módulo por `subprocess_seguro()`, que cita cada argumento."""
import subprocess, sys, types
from pathlib import Path


def executavel(caminho: Path) -> Path:
    caminho = Path(caminho)
    if sys.platform != "win32":
        return caminho
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from servico import plataforma
    primeira = (caminho.read_text(encoding="utf-8").splitlines() or [""])[0]
    if "python" in primeira:
        interp = f'"{sys.executable}" -X utf8'
    else:
        b = plataforma.bash_bin()
        if not b:
            raise RuntimeError("bash do Git não encontrado (instale o Git portátil em ~/EditorGS/bin/git)")
        interp = f'"{b}"'
    cmd = caminho.with_name(caminho.name + ".cmd")
    cmd.write_text(f'@{interp} "{caminho}" %*\r\n', encoding="utf-8")
    return cmd


class _SubprocessSeguro(types.ModuleType):
    """Igual ao `subprocess`, mas `run`/`Popen` com alvo .cmd/.bat recebem a linha já citada argumento a argumento."""

    def __getattr__(self, nome):
        return getattr(subprocess, nome)

    @staticmethod
    def _linha(args):
        if sys.platform == "win32" and isinstance(args, (list, tuple)) and str(args[0]).lower().endswith((".cmd", ".bat")):
            return " ".join('"' + str(a).replace('"', '\\"') + '"' for a in args)
        return args

    def run(self, args, **k):
        return subprocess.run(self._linha(args), **k)

    def Popen(self, args, **k):  # noqa: N802
        return subprocess.Popen(self._linha(args), **k)


def subprocess_seguro():
    return _SubprocessSeguro("subprocess")
