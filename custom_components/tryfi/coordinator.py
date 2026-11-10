"""Polling TryFi on a timer."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TryFiAuthError, TryFiConnectionError, relogin
from .const import CONF_POLLING_RATE, DEFAULT_POLLING_RATE, DOMAIN, MIN_POLLING_RATE
from .pytryfi import PyTryFi

LOGGER = logging.getLogger(__package__)

TryFiConfigEntry: TypeAlias = ConfigEntry["TryFiDataUpdateCoordinator"]


def polling_rate(entry: ConfigEntry[Any]) -> int:
    """Seconds between refreshes: the options, then the entry, then the default.

    Upstream only ever read entry.data, so the options form saved a value
    nothing looked at. Its form also stored the number as text, and entries
    from it may still hold "10"; anything below the floor is raised to it.
    """
    raw = entry.options.get(
        CONF_POLLING_RATE, entry.data.get(CONF_POLLING_RATE, DEFAULT_POLLING_RATE)
    )
    try:
        rate = int(float(raw))
    except (TypeError, ValueError):
        rate = DEFAULT_POLLING_RATE
    return max(rate, MIN_POLLING_RATE)


class TryFiDataUpdateCoordinator(DataUpdateCoordinator[PyTryFi]):
    """Refreshes every pet and base on the account."""

    config_entry: TryFiConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: TryFiConfigEntry, tryfi: PyTryFi
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=polling_rate(entry)),
        )
        self.tryfi = tryfi

    async def _async_update_data(self) -> PyTryFi:
        try:
            await self.hass.async_add_executor_job(self.tryfi.update)
        except Exception as first:
            LOGGER.debug("TryFi refresh failed (%s); signing in again", first)
        else:
            return self.tryfi

        # Once per failed poll, never in a loop: an outage costs one sign-in a
        # poll interval, not a burst of them.
        try:
            await self.hass.async_add_executor_job(relogin, self.tryfi)
        except TryFiAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TryFiConnectionError as err:
            raise UpdateFailed(f"Error updating TryFi data: {err}") from err
        try:
            await self.hass.async_add_executor_job(self.tryfi.update)
        except Exception as err:
            # The coordinator logs this once when updates start failing and
            # once when they recover, rather than on every poll.
            raise UpdateFailed(f"Error updating TryFi data: {err}") from err
        return self.tryfi
