"""Shared base for the entities that belong to a pet's collar."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TryFiDataUpdateCoordinator


class TryFiPetEntity(CoordinatorEntity[TryFiDataUpdateCoordinator]):
    """An entity reading one pet from the coordinator's latest refresh.

    Unique ids use exactly the formats upstream used. Names come from
    translations and are chosen so that the entity id Home Assistant builds
    from "<pet> <name>" is the one upstream's full names produced, so a fresh
    install lands on the same ids an existing one already has.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TryFiDataUpdateCoordinator,
        pet: Any,
        suffix: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._pet_id: str = pet.petId
        self._attr_unique_id = f"{pet.petId}-{suffix}"
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pet.petId)},
            name=pet.name,
            manufacturer="TryFi",
            model=pet.breed,
            sw_version=pet.device.buildId,
        )

    @property
    def pet(self) -> Any:
        """The pet as of the last refresh. None once it leaves the account."""
        return self.coordinator.data.getPet(self._pet_id)

    @property
    def device(self) -> Any:
        return self.pet.device

    @property
    def available(self) -> bool:
        return super().available and self.pet is not None
