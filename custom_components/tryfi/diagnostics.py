"""Diagnostics download: what the integration sees, with nothing personal in it.

Upstream's issues mostly stalled at "please post debug logs". This is the
answer to that: the shape of what TryFi returned for each pet and base, with
every credential, name, place and coordinate removed, so it can be pasted into
a public issue as it is.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, CONF_USERNAME
from .coordinator import TryFiConfigEntry, polling_rate

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TryFiConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    tryfi = coordinator.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
            "polling_seconds": polling_rate(entry),
        },
        "last_update_success": coordinator.last_update_success,
        "pets": [_pet(index, pet) for index, pet in enumerate(tryfi.pets)],
        "bases": [
            {
                "index": index,
                "online": base.online,
                "online_quality": base.onlineQuality,
                "has_position": base.latitude is not None,
            }
            for index, base in enumerate(tryfi.bases)
        ],
    }


def _pet(index: int, pet: Any) -> dict[str, Any]:
    device = pet.device
    stats = {
        f"{period}_{field}": getattr(pet, f"{period}{attribute}", None)
        for period in ("daily", "weekly", "monthly")
        for field, attribute in (
            ("steps", "Steps"),
            ("distance_m", "TotalDistance"),
            ("sleep_s", "Sleep"),
            ("nap_s", "Nap"),
        )
    }
    return {
        "index": index,
        "breed": pet.breed,
        "activity_type": pet.activityType,
        "has_position": pet.currLatitude is not None,
        "at_saved_place": pet.currPlaceName is not None,
        "stats": stats,
        "collar": {
            "build": device.buildId,
            "battery_percent": device.batteryPercent,
            "charging": device.isCharging,
            "mode": device.mode,
            "led_on": device.ledOn,
            "led_color": device.ledColor,
            "led_colors_offered": len(device.availableLedColors),
            "connection_type": device.connectionStateType,
            "connection_signal_percent": device.connectionSignalStrength,
            "connected_to_a_base": device.connectedBaseId is not None,
        },
    }
