from __future__ import annotations

from collections.abc import Callable

import pytest

from pico_hid_bridge.e2e.cases import ALL_CASES
from tests.helpers.e2e_runner import assert_e2e_passed, run_e2e_case_by_name
from tests.helpers.environment import TestEnvironment


pytestmark = pytest.mark.hardware_e2e


def _make_test(case_name: str, expected_failure: bool) -> Callable[[TestEnvironment], None]:
    def test_case(env: TestEnvironment) -> None:
        result = run_e2e_case_by_name(env, case_name, expected_failure=expected_failure)
        assert_e2e_passed(result)

    test_case.__name__ = f"test_{case_name}"
    test_case.__qualname__ = test_case.__name__
    test_case.__doc__ = f"Run E2E scenario {case_name}."
    if expected_failure:
        test_case = pytest.mark.expected_failure(test_case)  # type: ignore[assignment]
    return test_case


for _case in ALL_CASES:
    globals()[f"test_{_case.name}"] = _make_test(_case.name, "expected_failure" in _case.name)


del _case
