"""Shared base for collar entities, and adding them as pets and bases appear."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TryFiConfigEntry, TryFiDataUpdateCoordinator


@callback
def async_add_per_pet(
    entry: TryFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
    build: Callable[[Any], Iterable[Entity]],
) -> None:
    """Add a pet's entities now, and for any pet that turns up on a refresh.

    A pet can be missing at setup and arrive later: a collar fitted after the
    integration was added, or a first read that failed. Enumerating only at
    setup left such a pet with no entities until a reload.
    """
    _async_add_as_found(
        entry, async_add_entities, lambda data: data.pets, lambda pet: pet.petId, build
    )


@callback
def async_add_per_base(
    entry: TryFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
    build: Callable[[Any], Iterable[Entity]],
) -> None:
    """The same, for charging bases."""
    _async_add_as_found(
        entry,
        async_add_entities,
        lambda data: data.bases,
        lambda base: base.baseId,
        build,
    )


def _async_add_as_found(
    entry: TryFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
    items: Callable[[Any], Iterable[Any]],
    key: Callable[[Any], str],
    build: Callable[[Any], Iterable[Entity]],
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new() -> None:
        new = [item for item in items(coordinator.data) if key(item) not in known]
        if not new:
            return
        known.update(key(item) for item in new)
        async_add_entities([entity for item in new for entity in build(item)])

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


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
