"""Signing in through the real vendored pytryfi, against the fake cloud."""

from __future__ import annotations

import logging
import sys
import types

import pytest
from fakes import PET_ID, FakeCloud

from custom_components.tryfi.api import (
    TryFiAuthError,
    TryFiConnectionError,
    connect,
)


def test_a_good_sign_in_loads_the_whole_account(cloud: FakeCloud) -> None:
    tryfi = connect("someone@example.com", "correct-horse")

    assert [pet.petId for pet in tryfi.pets] == [PET_ID]
    assert [base.name for base in tryfi.bases] == ["Kitchen Base"]
    assert tryfi.currentUser.email == "someone@example.com"


def test_a_wrong_password_is_an_auth_error(cloud: FakeCloud) -> None:
    with pytest.raises(TryFiAuthError):
        connect("someone@example.com", "wrong")


def test_a_rejection_in_the_body_is_an_auth_error(cloud: FakeCloud) -> None:
    # pytryfi's own path for a 200 that carries an error message.
    cloud.login_mode = "reject_body"
    with pytest.raises(TryFiAuthError):
        connect("someone@example.com", "correct-horse")


def test_an_unreachable_cloud_is_a_connection_error(cloud: FakeCloud) -> None:
    cloud.login_mode = "unreachable"
    with pytest.raises(TryFiConnectionError):
        connect("someone@example.com", "correct-horse")


def test_a_server_error_is_a_connection_error(cloud: FakeCloud) -> None:
    cloud.login_mode = "error_500"
    with pytest.raises(TryFiConnectionError):
        connect("someone@example.com", "correct-horse")


def test_a_failure_that_clears_on_the_second_try_is_a_connection_error(
    cloud: FakeCloud,
) -> None:
    # The account was never loaded, so there is nothing to hand back, but the
    # password is not the problem and must not be reported as one.
    cloud.login_mode = "flaky"
    with pytest.raises(TryFiConnectionError):
        connect("someone@example.com", "correct-horse")
    assert cloud.requests.count("login") == 2


def test_signed_in_but_unable_to_load_is_a_connection_error(
    cloud: FakeCloud,
) -> None:
    cloud.graphql_down = True
    with pytest.raises(TryFiConnectionError):
        connect("someone@example.com", "correct-horse")
    # Signed in fine, so there is no second attempt to classify.
    assert cloud.requests.count("login") == 1


def test_an_unexpected_login_failure_is_not_blamed_on_the_password(
    cloud: FakeCloud,
) -> None:
    # A 200 whose body is not JSON: pytryfi fails reading userId out of it.
    cloud.login_mode = "garbage"
    original = cloud.login

    def garbage(data: dict[str, str]) -> object:
        response = original({"password": "correct-horse"})
        response._body = ValueError("not json")
        return response

    cloud.login = garbage  # type: ignore[method-assign]
    with pytest.raises(TryFiConnectionError):
        connect("someone@example.com", "correct-horse")


def test_swallowed_exceptions_reach_the_debug_log(
    cloud: FakeCloud, caplog: pytest.LogCaptureFixture
) -> None:
    cloud.graphql_down = True
    with (
        caplog.at_level(logging.DEBUG, logger="custom_components.tryfi.pytryfi"),
        pytest.raises(TryFiConnectionError),
    ):
        connect("someone@example.com", "correct-horse")
    assert any(
        "graphql unreachable" in record.getMessage() and record.levelno == logging.DEBUG
        for record in caplog.records
    )


def test_the_vendored_copy_is_used_even_with_pytryfi_installed(
    cloud: FakeCloud, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Anyone upgrading from upstream still has pytryfi 0.0.21 in site-packages,
    # and that one reports to a third party the moment it is constructed. An
    # absolute import anywhere in the vendored code would pick it up.
    trap = types.ModuleType("pytryfi")

    def __getattr__(name: str) -> object:
        raise AssertionError(f"the installed pytryfi was used for {name}")

    trap.__getattr__ = __getattr__  # type: ignore[method-assign]
    monkeypatch.setitem(sys.modules, "pytryfi", trap)
    for name in list(sys.modules):
        if name.startswith("custom_components.tryfi"):
            monkeypatch.delitem(sys.modules, name)

    from custom_components.tryfi.api import connect as fresh_connect

    assert fresh_connect("someone@example.com", "correct-horse").pets
