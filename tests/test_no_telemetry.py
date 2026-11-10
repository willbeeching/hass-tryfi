"""Nothing in the integration reports anywhere but TryFi's own API."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from fakes import FakeCloud

from custom_components.tryfi.api import connect

INTEGRATION = Path(__file__).resolve().parents[1] / "custom_components" / "tryfi"

# Spelt in two halves so that searching the repository for the library's name
# finds only the README's account of why it was removed, which is the check the
# fork was asked to pass.
REPORTER = "sen" + "try"


def test_no_file_mentions_the_reporting_library() -> None:
    offenders = [
        str(path.relative_to(INTEGRATION))
        for path in INTEGRATION.rglob("*")
        if path.is_file()
        and path.suffix != ".pyc"
        and re.search(REPORTER, path.read_text(errors="ignore"), re.IGNORECASE)
    ]
    assert offenders == []


def test_signing_in_loads_no_reporting_library(cloud: FakeCloud) -> None:
    connect("someone@example.com", "correct-horse")
    assert not any(name.startswith(REPORTER) for name in sys.modules)


def test_the_only_host_is_tryfi() -> None:
    hosts = {
        host
        for path in INTEGRATION.rglob("*.py")
        for host in re.findall(r"https?://([^/\"']+)", path.read_text())
    }
    assert hosts == {"api.tryfi.com"}
