from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import shutil

from .remote import run_local


@dataclass(frozen=True)
class TestResult:
    __test__ = False

    case_name: str
    stage: str
    status: str
    expected_result: str
    failure_domain: str | None
    exit_code: int
    artifacts_dir: str
    result_json: str
    message: str


def create_artifact_dir(*, root: Path, case_name: str, timestamp: str | None = None) -> Path:
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = root / f"{case_name}_{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_result_json(result: TestResult, *, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect_remote_artifacts(env: object, remote_artifacts_dir: str, local_artifacts_dir: Path) -> None:
    local_artifacts_dir.mkdir(parents=True, exist_ok=True)
    remote = f"{getattr(env, 'pi_user')}@{getattr(env, 'pi_host')}:{remote_artifacts_dir}/"
    scp = shutil.which("scp.exe") or shutil.which("scp") or "scp"
    result = run_local(
        [scp, "-i", str(getattr(env, "ssh_key")), "-r", remote, str(local_artifacts_dir)],
        cwd=Path.cwd(),
        timeout_sec=120,
    )
    if not result.ok:
        raise RuntimeError(result.stderr or result.stdout or "artifact collection failed")
