from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import time


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    exit_code: int
    stdout: str
    stderr: str
    elapsed_sec: float

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def run_local(args: list[str], *, cwd: Path, timeout_sec: int = 60) -> CommandResult:
    start = time.monotonic()
    completed = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
        check=False,
    )
    return CommandResult(
        args=list(args),
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        elapsed_sec=time.monotonic() - start,
    )


def _ssh_executable() -> str:
    return shutil.which("ssh.exe") or shutil.which("ssh") or "ssh"


def _scp_executable() -> str:
    return shutil.which("scp.exe") or shutil.which("scp") or "scp"


def _ssh_base_args(env: object) -> list[str]:
    key = Path(getattr(env, "ssh_key"))
    return [
        _ssh_executable(),
        "-i",
        str(key),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-l",
        str(getattr(env, "pi_user")),
        str(getattr(env, "pi_host")),
    ]


def run_ssh(env: object, command: str, *, timeout_sec: int = 60) -> CommandResult:
    args = [*_ssh_base_args(env), command]
    return run_local(args, cwd=Path.cwd(), timeout_sec=timeout_sec)


def copy_pi_sources(env: object, *, source_dir: Path = Path("pi"), timeout_sec: int = 120) -> CommandResult:
    remote_parent = PurePosixPath(str(getattr(env, "remote_pi_dir"))).parent
    remote = f"{getattr(env, 'pi_user')}@{getattr(env, 'pi_host')}:{remote_parent}/"
    args = [
        _scp_executable(),
        "-i",
        str(Path(getattr(env, "ssh_key"))),
        "-r",
        str(source_dir),
        remote,
    ]
    return run_local(args, cwd=Path.cwd(), timeout_sec=timeout_sec)
