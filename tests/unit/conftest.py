from __future__ import annotations

import pytest

from tests.unit.test_action_executor import FakeSleep, FakeTransport


@pytest.fixture
def fake_transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def fake_sleep() -> FakeSleep:
    return FakeSleep()
