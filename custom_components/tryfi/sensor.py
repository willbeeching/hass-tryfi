"""Collar battery, activity totals, whereabouts, connection, and base status."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_STATS_BY_TIME, SENSOR_STATS_BY_TYPE
from .coordinator import TryFiConfigEntry, TryFiDataUpdateCoordinator
from .entity import TryFiPetEntity


@dataclass(frozen=True)
class _Stat:
    """How one stat type reads out of pytryfi and what it means."""

    attribute: str
    divisor: int | None
    unit: str
    device_class: SensorDeviceClass | None
    precision: int


# TryFi reports distance in metres and rest in seconds. Distance stays in
# kilometres and rest in minutes, the units upstream used, so the long-term
# statistics already recorded carry on in the same unit.
_STATS = {
    "STEPS": _Stat("Steps", None, "steps", None, 0),
    "DISTANCE": _Stat(
        "TotalDistance", 1000, UnitOfLength.KILOMETERS, SensorDeviceClass.DISTANCE, 2
    ),
    "SLEEP": _Stat("Sleep", 60, UnitOfTime.MINUTES, SensorDeviceClass.DURATION, 0),
    "NAP": _Stat("Nap", 60, UnitOfTime.MINUTES, SensorDeviceClass.DURATION, 0),
}

# TryFi's activity and connection type names, and the state each becomes. One
# TryFi does not list here reads as unknown rather than as a raw API name.
ACTIVITY_STATES = {"OngoingRest": "resting", "OngoingWalk": "walking"}
CONNECTION_STATES = {
    "ConnectedToBase": "base",
    "ConnectedToWifi": "wifi",
    "ConnectedToCellular": "cellular",
    "ConnectedToUser": "phone",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TryFiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for pet in coordinator.data.pets:
        entities.append(TryFiBatterySensor(coordinator, pet))
        entities.extend(
            PetStatsSensor(coordinator, pet, stat_type, stat_time)
            for stat_type in SENSOR_STATS_BY_TYPE
            for stat_time in SENSOR_STATS_BY_TIME
        )
        entities.extend(
            [
                PetActivitySensor(coordinator, pet),
                PetPlaceSensor(coordinator, pet, "Current Place Name"),
                PetPlaceSensor(coordinator, pet, "Current Place Address"),
                PetConnectionSensor(coordinator, pet),
                PetSignalSensor(coordinator, pet),
            ]
        )
    entities.extend(
        TryFiBaseSensor(coordinator, base) for base in coordinator.data.bases
    )
    async_add_entities(entities)


def _slug(label: str) -> str:
    return label.lower().replace(" ", "-")


class TryFiBaseSensor(CoordinatorEntity[TryFiDataUpdateCoordinator], SensorEntity):
    """Whether a charging base is online. The base's only entity."""

    _attr_has_entity_name = True
    # The base's main feature, so it takes the device's own name.
    _attr_name = None
    _attr_translation_key = "base"

    def __init__(self, coordinator: TryFiDataUpdateCoordinator, base: Any) -> None:
        super().__init__(coordinator)
        self._base_id: str = base.baseId
        self._attr_unique_id = f"{base.baseId}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, base.baseId)},
            name=base.name,
            manufacturer="TryFi",
            model="TryFi Base",
        )

    @property
    def base(self) -> Any:
        return self.coordinator.data.getBase(self._base_id)

    @property
    def available(self) -> bool:
        return super().available and self.base is not None

    @property
    def native_value(self) -> str | None:
        if self.base.online is None:
            return None
        return "Online" if self.base.online else "Offline"


class PetActivitySensor(TryFiPetEntity, SensorEntity):
    """Resting or walking."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(ACTIVITY_STATES.values())

    def __init__(self, coordinator: TryFiDataUpdateCoordinator, pet: Any) -> None:
        super().__init__(coordinator, pet, "activity-type", "activity_type")

    @property
    def native_value(self) -> str | None:
        return ACTIVITY_STATES.get(self.pet.activityType)


class PetPlaceSensor(TryFiPetEntity, SensorEntity):
    """The saved place the pet is at, by name or by address."""

    def __init__(
        self, coordinator: TryFiDataUpdateCoordinator, pet: Any, label: str
    ) -> None:
        super().__init__(coordinator, pet, _slug(label), _slug(label).replace("-", "_"))
        self._read: Callable[[Any], Any] = (
            (lambda pet: pet.currPlaceName)
            if label == "Current Place Name"
            else (lambda pet: pet.currPlaceAddress)
        )

    @property
    def native_value(self) -> str | None:
        return self._read(self.pet)  # type: ignore[no-any-return]


class PetConnectionSensor(TryFiPetEntity, SensorEntity):
    """How the collar last reached TryFi, and through what."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(CONNECTION_STATES.values())
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TryFiDataUpdateCoordinator, pet: Any) -> None:
        super().__init__(coordinator, pet, "connected-to", "connected_to")

    @property
    def native_value(self) -> str | None:
        return CONNECTION_STATES.get(self.device.connectionStateType)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which base, whose phone, or what signal (upstream #60)."""
        device = self.device
        attributes: dict[str, Any] = {}
        if base_id := device.connectedBaseId:
            attributes["base_id"] = base_id
            base = self.coordinator.data.getBase(base_id)
            if base is not None:
                attributes["base_name"] = base.name
        if person := device.connectedUserFirstName:
            attributes["person"] = person
        if (signal := device.connectionSignalStrength) is not None:
            attributes["signal_strength"] = signal
        return attributes


class PetSignalSensor(TryFiPetEntity, SensorEntity):
    """Cellular signal, when the collar last connected over cellular."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: TryFiDataUpdateCoordinator, pet: Any) -> None:
        super().__init__(coordinator, pet, "signal-strength", "signal_strength")

    @property
    def native_value(self) -> int | None:
        return self.device.connectionSignalStrength  # type: ignore[no-any-return]


class PetStatsSensor(TryFiPetEntity, SensorEntity):
    """Steps, distance, sleep or nap over the current day, week or month."""

    # Each total climbs through its period and drops back at the start of the
    # next, which is the shape total_increasing describes: Home Assistant reads
    # the drop as a new cycle rather than as a fall.
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: TryFiDataUpdateCoordinator,
        pet: Any,
        stat_type: str,
        stat_time: str,
    ) -> None:
        period, kind = stat_time.lower(), stat_type.lower()
        super().__init__(coordinator, pet, f"{period}-{kind}", f"{period}_{kind}")
        stat = _STATS[stat_type]
        self._divisor = stat.divisor
        self._attribute = f"{period}{stat.attribute}"
        self._attr_native_unit_of_measurement = stat.unit
        self._attr_device_class = stat.device_class
        self._attr_suggested_display_precision = stat.precision
        # Today's figures are the useful ones. The weekly and monthly totals
        # start disabled on a new install; entities that already exist keep
        # whatever they had.
        self._attr_entity_registry_enabled_default = period == "daily"

    @property
    def native_value(self) -> float | int | None:
        # Absent when pytryfi could not read the stats for this pet.
        value = getattr(self.pet, self._attribute, None)
        if value is None or self._divisor is None:
            return value
        return value / self._divisor  # type: ignore[no-any-return]


class TryFiBatterySensor(TryFiPetEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TryFiDataUpdateCoordinator, pet: Any) -> None:
        super().__init__(coordinator, pet, "battery", "collar_battery_level")

    @property
    def native_value(self) -> int | None:
        return self.device.batteryPercent  # type: ignore[no-any-return]
