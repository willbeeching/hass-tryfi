"""Shared base for collar entities, and adding them as pets and bases appear."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import TryFiClient, TryFiError
from .client import Base, Collar, Pet
from .const import DOMAIN
from .coordinator import TryFiConfigEntry, TryFiDataUpdateCoordinator


@callback
def async_add_per_pet(
    entry: TryFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
    build: Callable[[Pet], Iterable[Entity]],
) -> None:
    """Add a pet's entities now, and for any pet that turns up on a refresh.

    A pet can be missing at setup and arrive later: a collar fitted after the
    integration was added, or a first read that failed. Enumerating only at
    setup left such a pet with no entities until a reload.
    """
    _async_add_as_found(
        entry,
        async_add_entities,
        lambda client: client.pets,
        lambda pet: pet.pet_id,
        build,
    )


@callback
def async_add_per_base(
    entry: TryFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
    build: Callable[[Base], Iterable[Entity]],
) -> None:
    """The same, for charging bases."""
    _async_add_as_found(
        entry,
        async_add_entities,
        lambda client: client.bases,
        lambda base: base.base_id,
        build,
    )


def _async_add_as_found[T](
    entry: TryFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
    items: Callable[[TryFiClient], Iterable[T]],
    key: Callable[[T], str],
    build: Callable[[T], Iterable[Entity]],
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new() -> None:
        # A device removed as stale takes its entities with it, so if it comes
        # back it needs them made again.
        known.difference_update(coordinator.removed_ids)
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
        pet: Pet,
        suffix: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._pet_id = pet.pet_id
        self._attr_unique_id = f"{pet.pet_id}-{suffix}"
        self._attr_translation_key = translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, pet.pet_id)},
            name=pet.name,
            manufacturer="TryFi",
            model=pet.breed,
            sw_version=pet.collar.build_id,
        )

    def _lookup(self) -> Pet | None:
        return self.coordinator.data.get_pet(self._pet_id)

    @property
    def pet(self) -> Pet:
        """The pet as of the last refresh.

        Home Assistant reads state only while the entity is available, which
        it is only while the account still has the pet.
        """
        pet = self._lookup()
        if pet is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="pet_gone"
            )
        return pet

    @property
    def collar(self) -> Collar:
        return self.pet.collar

    @property
    def available(self) -> bool:
        return super().available and self._lookup() is not None

    async def _async_command(self, *changes: Callable[[], Awaitable[None]]) -> None:
        """Make changes to the collar, show the result at once, then refresh.

        TryFi's answer carries the collar's new state, which the client takes,
        so the UI need not wait a poll (upstream's "# Fix later"). The refresh
        catches anything an empty answer left out.
        """
        for change in changes:
            try:
                await change()
            except TryFiError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_failed",
                    translation_placeholders={
                        "entity": self.name if isinstance(self.name, str) else "",
                        "error": str(err),
                    },
                ) from err
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def client(self) -> TryFiClient:
        return self.coordinator.client
