from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAL_PI_DIR = ROOT_DIR / "pi"

for candidate in (LOCAL_PI_DIR, ROOT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--call-only", action="store_true", help="Verify test invocation without hardware/API effects.")
    parser.addoption("--run-pi-integration", action="store_true", help="Run tests that access the Raspberry Pi 5.")
    parser.addoption("--run-hardware-e2e", action="store_true", help="Run full hardware E2E scenarios.")
    parser.addoption("--pi-host", default="192.168.11.6")
    parser.addoption("--pi-user", default="nama")
    parser.addoption("--ssh-key", default="id_rsa")
    parser.addoption("--remote-pi-dir", default="/home/nama/pi")
    parser.addoption("--webui-port", type=int, default=18080)
    parser.addoption("--e2e-stage", action="append", help="Run only E2E cases in the given stage.")
    parser.addoption("--e2e-case", action="append", help="Run only the named E2E case.")


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--call-only"):
        os.environ["PICO_HID_TEST_CALL_ONLY"] = "1"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    call_only = config.getoption("--call-only")
    run_pi = config.getoption("--run-pi-integration")
    run_e2e = config.getoption("--run-hardware-e2e")
    selected_stages = set(config.getoption("--e2e-stage") or [])
    selected_cases = set(config.getoption("--e2e-case") or [])

    skip_pi = pytest.mark.skip(reason="requires --run-pi-integration or --call-only")
    skip_e2e = pytest.mark.skip(reason="requires --run-hardware-e2e or --call-only")
    skip_filter = pytest.mark.skip(reason="not selected by E2E filter")

    try:
        from pico_hid_bridge.e2e.cases import CASES
    except Exception:
        CASES = {}

    for item in items:
        if "pi_integration" in item.keywords and not (run_pi or call_only):
            item.add_marker(skip_pi)
        if "hardware_e2e" in item.keywords and not (run_e2e or call_only):
            item.add_marker(skip_e2e)
        if "hardware_e2e" in item.keywords and (selected_stages or selected_cases):
            case_name = item.name.removeprefix("test_")
            test_case = CASES.get(case_name)
            if selected_cases and case_name not in selected_cases:
                item.add_marker(skip_filter)
            if selected_stages and (test_case is None or test_case.stage not in selected_stages):
                item.add_marker(skip_filter)


@pytest.fixture
def env(pytestconfig: pytest.Config):
    from tests.helpers.environment import load_test_environment

    return load_test_environment(
        pi_host=pytestconfig.getoption("--pi-host"),
        pi_user=pytestconfig.getoption("--pi-user"),
        ssh_key=Path(pytestconfig.getoption("--ssh-key")),
        remote_pi_dir=pytestconfig.getoption("--remote-pi-dir"),
        webui_port=pytestconfig.getoption("--webui-port"),
    )
