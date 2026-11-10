"""Lost Mode on the collar."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TryFiConfigEntry, TryFiDataUpdateCoordinator
from .entity import TryFiPetEntity, async_add_per_pet

SAFE = "Safe"
LOST = "Lost"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TryFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_per_pet(
        entry, async_add_entities, lambda pet: [TryFiLostMode(coordinator, pet)]
    )


class TryFiLostMode(TryFiPetEntity, SelectEntity):
    _attr_options = [SAFE, LOST]

    def __init__(self, coordinator: TryFiDataUpdateCoordinator, pet: Any) -> None:
        super().__init__(coordinator, pet, "lost", "lost_mode")

    @property
    def current_option(self) -> str | None:
        # Unknown, rather than "Safe", when the collar did not report a mode.
        if self.device.mode is None:
            return None
        return LOST if self.device.isLost else SAFE

    async def async_select_option(self, option: str) -> None:
        accepted = await self.hass.async_add_executor_job(
            self.pet.setLostDogMode, self.coordinator.tryfi.session, option == LOST
        )
        # pytryfi catches the failure itself and returns False.
        if not accepted:
            raise HomeAssistantError(f"TryFi did not accept Lost Mode for {self.name}")
        # The reply carries the collar's new mode, which pytryfi has already
        # copied into the pet: show it now, then refresh for anything else.
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
