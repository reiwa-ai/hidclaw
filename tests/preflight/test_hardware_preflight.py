from __future__ import annotations

import pytest

from tests.helpers.environment import TestEnvironment, run_hardware_preflight


pytestmark = pytest.mark.pi_integration


def test_hardware_preflight(env: TestEnvironment) -> None:
    result = run_hardware_preflight(env)
    failed = [check for check in result.checks if not check.ok]
    assert result.ok, "\n".join(f"{check.name}: {check.message}" for check in failed)
