"""The vendored pytryfi, against the fake cloud: one test per upstream failure.

Each of these reproduces a report on sbabcock23/hass-tryfi that traced back to
the library rather than the integration.
"""

from __future__ import annotations

import pytest
from fakes import BASE_ID, PET_ID, FakeCloud

from custom_components.tryfi.api import connect
from custom_components.tryfi.pytryfi.common.query import TryFiError

COLLARLESS = {"id": "pet-nano", "name": "Whiskers", "device": None}


def _tryfi(cloud: FakeCloud):  # type: ignore[no-untyped-def]
    return connect("someone@example.com", cloud.password)


@pytest.mark.parametrize(
    "extra",
    [
        COLLARLESS,
        # A pet TryFi sends with no device key at all.
        {"id": "pet-shared", "name": "Owl"},
    ],
)
def test_a_pet_without_a_collar_does_not_hide_the_others(
    cloud: FakeCloud, extra: dict[str, object]
) -> None:
    # #61, #62, #67, #87, #96, #99, #102: "only the bases show up". Upstream
    # compared the device with the string "None" while TryFi sends null.
    cloud.extra_pets = [extra]
    tryfi = _tryfi(cloud)
    assert [pet.petId for pet in tryfi.pets] == [PET_ID]
    tryfi.update()
    assert [pet.petId for pet in tryfi.pets] == [PET_ID]


def test_a_pet_that_cannot_be_read_does_not_hide_the_others(
    cloud: FakeCloud,
) -> None:
    broken = {"id": "pet-odd", "name": "Odd", "device": {"id": "d"}}
    cloud.extra_pets = [broken]
    assert [pet.petId for pet in _tryfi(cloud).pets] == [PET_ID]


@pytest.mark.parametrize(
    "missing", ["operationParams", "ledColor", "info", "availableLedColors"]
)
def test_a_collar_reporting_less_still_has_every_attribute(
    cloud: FakeCloud, missing: str
) -> None:
    # #69 `_ledOn`, #100 `_mode`: the first missing field left every later
    # attribute undefined.
    cloud.device_missing = {missing}
    device = _tryfi(cloud).pets[0].device
    for attribute in (
        "mode",
        "ledOn",
        "ledColorHex",
        "batteryPercent",
        "isCharging",
        "buildId",
        "connectionStateType",
        "availableLedColors",
        "isLost",
    ):
        getattr(device, attribute)


def test_a_mutation_answer_missing_fields_keeps_the_rest(cloud: FakeCloud) -> None:
    tryfi = _tryfi(cloud)
    device = tryfi.pets[0].device
    device.setDeviceDetailsJSON({"moduleId": "module-0001"})
    assert device.batteryPercent == 87
    assert device.mode == "NORMAL"


def test_a_base_missing_fields_still_loads(cloud: FakeCloud) -> None:
    # #93: a base without infoLastUpdated failed the whole sensor platform.
    cloud.base_missing = {"infoLastUpdated", "position", "name", "networkName"}
    base = _tryfi(cloud).bases[0]
    assert base.baseId == BASE_ID
    assert base.name == BASE_ID
    assert base.latitude is None
    assert base.lastUpdated is not None


def test_resting_somewhere_unsaved_has_a_position_and_no_place(
    cloud: FakeCloud,
) -> None:
    cloud.location_mode = "rest_unsaved_place"
    pet = _tryfi(cloud).pets[0]
    assert pet.currLatitude == pytest.approx(10.001)
    assert pet.currPlaceName is None
    assert pet.currStartTime is not None


def test_a_walk_reads_its_latest_position(cloud: FakeCloud) -> None:
    cloud.location_mode = "walk"
    pet = _tryfi(cloud).pets[0]
    assert pet.activityType == "OngoingWalk"
    assert pet.currLatitude == pytest.approx(10.101)


def test_a_walk_with_no_positions_yet_uses_its_path(cloud: FakeCloud) -> None:
    cloud.location_mode = "walk_no_positions"
    assert _tryfi(cloud).pets[0].currLatitude == pytest.approx(10.101)


def test_a_failed_location_keeps_the_last_one(cloud: FakeCloud) -> None:
    tryfi = _tryfi(cloud)
    cloud.location_fails = True
    cloud.daily_steps = 9999
    tryfi.update()
    pet = tryfi.pets[0]
    assert pet.currLatitude == pytest.approx(10.001)
    assert pet.currPlaceName == "Home"
    # Only the failed group is carried over; the rest is fresh.
    assert pet.dailySteps == 9999


def test_a_failed_account_fetch_raises(cloud: FakeCloud) -> None:
    # #56, #91: upstream swallowed this and the data silently went stale.
    tryfi = _tryfi(cloud)
    cloud.graphql_down = True
    with pytest.raises(Exception, match="graphql unreachable"):
        tryfi.update()
    # What was there before is still there to be read.
    assert [pet.petId for pet in tryfi.pets] == [PET_ID]


def test_a_graphql_error_raises_with_its_message(cloud: FakeCloud) -> None:
    tryfi = _tryfi(cloud)
    cloud.graphql_errors = True
    with pytest.raises(TryFiError, match="Not authenticated"):
        tryfi.update()


def test_one_households_query_per_refresh(cloud: FakeCloud) -> None:
    # Upstream fetched the same households query twice, once for pets and
    # once for bases.
    tryfi = _tryfi(cloud)
    assert cloud.requests.count("households") == 1
    cloud.requests.clear()
    tryfi.update()
    assert cloud.requests.count("households") == 1


@pytest.mark.parametrize(
    ("typename", "base", "person", "signal"),
    [
        ("ConnectedToBase", BASE_ID, None, None),
        ("ConnectedToUser", None, "Sam", None),
        ("ConnectedToCellular", None, None, 70),
        ("ConnectedToWifi", None, None, None),
        ("UnknownConnectivity", None, None, None),
    ],
)
def test_connection_detail(
    cloud: FakeCloud,
    typename: str,
    base: str | None,
    person: str | None,
    signal: int | None,
) -> None:
    cloud.connection = typename
    device = _tryfi(cloud).pets[0].device
    assert device.connectionStateType == typename
    assert device.connectedBaseId == base
    assert device.connectedUserFirstName == person
    assert device.connectionSignalStrength == signal


def test_a_collar_that_never_connected_still_loads(cloud: FakeCloud) -> None:
    cloud.connection = None
    pet = _tryfi(cloud).pets[0]
    assert pet.device.connectionStateType is None
    assert pet.connectedTo is None


def test_a_pet_that_left_is_not_an_error(
    cloud: FakeCloud, caplog: pytest.LogCaptureFixture
) -> None:
    tryfi = _tryfi(cloud)
    assert tryfi.getPet("gone") is None
    assert tryfi.getBase("gone") is None
    assert not [r for r in caplog.records if r.levelname == "ERROR"]
