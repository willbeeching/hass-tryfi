"""The TryFi integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import TryFiAuthError, TryFiConnectionError, connect
from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN, PLATFORMS, account_id
from .coordinator import TryFiConfigEntry, TryFiDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: TryFiConfigEntry) -> bool:
    _async_adopt_unique_id(hass, entry)
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


def _async_adopt_unique_id(hass: HomeAssistant, entry: TryFiConfigEntry) -> None:
    """Give an entry made by upstream, which set none, its account's unique id.

    So the config flow can refuse a second entry for the same account. Left
    alone if another entry already holds that id, which only a duplicate made
    before this fork could.
    """
    if entry.unique_id is not None:
        return
    unique_id = account_id(entry.data[CONF_USERNAME])
    if hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, unique_id):
        return
    hass.config_entries.async_update_entry(entry, unique_id=unique_id)


async def _async_reload_on_change(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply a new polling rate without a restart."""
    await hass.config_entries.async_reload(entry.entry_id)
