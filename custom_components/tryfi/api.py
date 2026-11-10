"""Creating a session and a signed-in client for one TryFi account."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .client import (
    TryFiAuthError,
    TryFiClient,
    TryFiCommandError,
    TryFiConnectionError,
    TryFiError,
)

__all__ = [
    "TryFiAuthError",
    "TryFiClient",
    "TryFiCommandError",
    "TryFiConnectionError",
    "TryFiError",
    "async_connect",
]


async def async_connect(
    hass: HomeAssistant, username: str, password: str
) -> TryFiClient:
    """Sign in and read the account, on a session of the account's own.

    Its own rather than Home Assistant's shared one, because TryFi's sign-in
    is a cookie and the shared session's cookie jar is every integration's.
    The session is closed again if signing in or the first read fails.
    """
    session = async_create_clientsession(hass)
    client = TryFiClient(session, username, password)
    try:
        await client.async_login()
        await client.async_refresh()
    except BaseException:
        await session.close()
        raise
    return client
