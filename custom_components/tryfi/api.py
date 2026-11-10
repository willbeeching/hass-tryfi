"""Signing in to TryFi, and telling a wrong password from an unreachable cloud.

pytryfi catches every exception raised while it signs in and loads the account,
so a wrong password and a network failure both come back as a PyTryFi object
that is simply missing attributes. Upstream only ever checked for one of them,
so a bad password was accepted by the config flow and the entry then retried
for ever.
"""

from __future__ import annotations

import requests

from .pytryfi import PyTryFi

# HTTP statuses TryFi's login endpoint could plausibly use for rejected
# credentials. pytryfi raises on any non-2xx before it reads the body.
_AUTH_STATUSES = frozenset({400, 401, 403})


class TryFiAuthError(Exception):
    """TryFi refused the email and password."""


class TryFiConnectionError(Exception):
    """TryFi could not be reached, or did not return the account."""


def connect(username: str, password: str) -> PyTryFi:
    """Sign in and load the account. Blocking: run it in the executor."""
    tryfi = PyTryFi(username, password)
    # _bases is the last thing PyTryFi.__init__ assigns, so its presence means
    # the whole load ran. _userId is assigned by a successful login.
    if hasattr(tryfi, "_bases"):
        return tryfi
    if hasattr(tryfi, "_userId"):
        raise TryFiConnectionError("signed in, but loading the pets and bases failed")
    # Run the login once more, outside pytryfi's catch-all, to see why it
    # failed. One extra request, and only on the failure path.
    _login(tryfi)
    # The second attempt worked, so the first failure was transient.
    raise TryFiConnectionError("sign-in failed once, then succeeded")


def relogin(tryfi: PyTryFi) -> None:
    """Sign in again on a fresh session. Blocking: run it in the executor.

    For a refresh that failed. TryFi's session can lapse, and the connection
    under it can die, and upstream had no way back from either short of a
    reload (upstream #56, #91, #104).
    """
    _login(tryfi)
    tryfi.setHeaders()


def _login(tryfi: PyTryFi) -> None:
    # A new session every time: the old one may be the dead connection, and
    # it carries the JSON content type pytryfi sets after signing in, which the
    # form-encoded login request cannot be sent with.
    tryfi.session.close()
    tryfi._session = requests.Session()
    try:
        tryfi.login()
    except requests.HTTPError as err:
        status = err.response.status_code if err.response is not None else None
        if status in _AUTH_STATUSES:
            raise TryFiAuthError(f"TryFi refused the sign-in ({status})") from err
        raise TryFiConnectionError(f"TryFi answered {status}") from err
    except requests.RequestException as err:
        raise TryFiConnectionError(str(err)) from err
    except Exception as err:
        # pytryfi raises this exact message when TryFi answers 200 with an
        # error body, which is how it reports a wrong password.
        if str(err) == "TryFiLoginError":
            raise TryFiAuthError("TryFi refused the email and password") from err
        raise TryFiConnectionError(str(err)) from err
