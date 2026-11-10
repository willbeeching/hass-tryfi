"""The TryFi integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import TryFiAuthError, TryFiConnectionError, connect
from .const import CONF_PASSWORD, CONF_USERNAME, PLATFORMS
from .coordinator import TryFiConfigEntry, TryFiDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: TryFiConfigEntry) -> bool:
    try:
        tryfi = await hass.async_add_executor_job(
            connect, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    except TryFiAuthError as err:
        # Starts the re-authentication flow, so a changed password asks for the
        # new one instead of retrying the old one in the background for ever.
        raise ConfigEntryAuthFailed(str(err)) from err
    except TryFiConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = TryFiDataUpdateCoordinator(hass, entry, tryfi)
    # Signing in has just loaded every pet and base, so hand that over rather
    # than fetching the whole account a second time straight away.
    coordinator.async_set_updated_data(tryfi)
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_reload_on_change))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TryFiConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.tryfi.session.close()
    return unloaded


async def _async_reload_on_change(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply a new polling rate without a restart."""
    await hass.config_entries.async_reload(entry.entry_id)
