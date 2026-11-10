"""Shared fixtures: TryFi's cloud, replaced at the requests.Session level."""

from __future__ import annotations

import pytest
import requests
from fakes import FakeCloud, make_session


@pytest.fixture
def cloud(monkeypatch: pytest.MonkeyPatch) -> FakeCloud:
    """Every requests.Session pytryfi opens talks to this instead of TryFi."""
    fake = FakeCloud()
    monkeypatch.setattr(requests, "Session", make_session(fake))
    return fake
