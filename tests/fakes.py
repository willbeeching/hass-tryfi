"""A stand-in for TryFi's cloud, at the level pytryfi talks to it.

pytryfi makes every request through one requests.Session. Replacing that class
with FakeSession lets the real vendored library and the real integration run
end to end against canned answers, which is where upstream's bugs were: in what
the integration did with what pytryfi handed it.

Every value here is made up. None of it is a real pet, collar or account.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

PET_ID = "pet-0001"
BASE_ID = "base-0001"
MODULE_ID = "module-0001"

LED_COLORS = [
    {"ledColorCode": 1, "hexCode": "#FF00FF", "name": "Magenta"},
    {"ledColorCode": 3, "hexCode": "#0000FF", "name": "Blue"},
    {"ledColorCode": 5, "hexCode": "#00FF00", "name": "Green"},
    {"ledColorCode": 8, "hexCode": "#FFFFFF", "name": "White"},
]


class FakeResponse:
    def __init__(self, status: int, body: Any) -> None:
        self.status_code = status
        self.ok = 200 <= status < 300
        self._body = body
        self.cookies: dict[str, str] = {}

    def json(self) -> Any:
        if isinstance(self._body, Exception):
            raise self._body
        return copy.deepcopy(self._body)

    def raise_for_status(self) -> None:
        if not self.ok:
            raise requests.HTTPError(f"{self.status_code}", response=self)


class FakeCloud:
    """The account and collar state that TryFi would hold."""

    def __init__(self) -> None:
        self.password = "correct-horse"
        # What the login endpoint does: "ok", "reject_401", "reject_body",
        # "unreachable", "error_500", or "flaky" (unreachable once, then ok).
        self.login_mode = "ok"
        self.graphql_down = False
        self.mutations_fail = False
        self.mutations_answer_empty = False
        self.has_location = True
        # "rest", "rest_unsaved_place" (place: null), "walk", "walk_no_positions"
        self.location_mode = "rest"
        self.location_fails = False
        self.graphql_errors = False
        # The collar's lastConnectionState __typename, or None for no state.
        self.connection: str | None = "ConnectedToCellular"
        # Keys deleted from the collar's description, e.g. "operationParams".
        self.device_missing: set[str] = set()
        # Keys deleted from the base's description, e.g. "infoLastUpdated".
        self.base_missing: set[str] = set()
        # Pets TryFi lists alongside the collared one, as raw JSON.
        self.extra_pets: list[dict[str, Any]] = []
        self.has_rest_stats = True
        self.pet_present = True
        self.base_online = True
        self.led_enabled = False
        self.led_code = 8
        self.mode = "NORMAL"
        self.charging = False
        self.battery = 87
        self.daily_steps = 4321
        self.requests: list[str] = []
        self.mutations: list[dict[str, Any]] = []
        self.sessions: list[FakeSession] = []

    # ------------------------------------------------------------- answers
    def device(self) -> dict[str, Any]:
        led = next(c for c in LED_COLORS if c["ledColorCode"] == self.led_code)
        off_at = datetime.now(UTC) + timedelta(hours=1)
        device = {
            "id": "device-0001",
            "moduleId": MODULE_ID,
            "info": {
                "buildId": "4.0.0-test",
                "batteryPercent": self.battery,
                "isCharging": self.charging,
            },
            "operationParams": {
                "mode": self.mode,
                "ledEnabled": self.led_enabled,
                "ledOffAt": off_at.isoformat().replace("+00:00", "Z"),
            },
            "ledColor": {"name": led["name"], "hexCode": led["hexCode"]},
            "lastConnectionState": self.connection_state(),
            "availableLedColors": LED_COLORS,
        }
        for key in self.device_missing:
            device.pop(key, None)
        return device

    def connection_state(self) -> dict[str, Any] | None:
        if self.connection is None:
            return None
        state: dict[str, Any] = {
            "__typename": self.connection,
            "date": "2026-11-10T08:00:00Z",
        }
        if self.connection == "ConnectedToCellular":
            state["signalStrengthPercent"] = 70
        elif self.connection == "ConnectedToBase":
            state["chargingBase"] = {"id": BASE_ID}
        elif self.connection == "ConnectedToUser":
            state["user"] = {"firstName": "Sam", "lastName": "Example"}
        elif self.connection == "UnknownConnectivity":
            state["unknownConnectivity"] = True
        return state

    def households(self) -> list[dict[str, Any]]:
        pets = []
        if self.pet_present:
            pets.append(
                {
                    "id": PET_ID,
                    "name": "Biscuit",
                    "homeCityState": "Exampletown",
                    "yearOfBirth": 2020,
                    "monthOfBirth": 4,
                    "dayOfBirth": 1,
                    "gender": "MALE",
                    "weight": 12.5,
                    "breed": {"name": "Example Terrier"},
                    "photos": {
                        "first": {"image": {"fullSize": "https://example.com/p.jpg"}}
                    },
                    "device": self.device(),
                }
            )
        pets.extend(copy.deepcopy(self.extra_pets))
        base = {
            "baseId": BASE_ID,
            "name": "Kitchen Base",
            "position": {"latitude": 10.0, "longitude": 20.0},
            "online": self.base_online,
            "onlineQuality": "GOOD",
            "infoLastUpdated": "2026-11-10T08:00:00Z",
            "networkName": "example-wifi",
        }
        for key in self.base_missing:
            base.pop(key, None)
        return [{"household": {"pets": pets, "bases": [base]}}]

    def location(self) -> dict[str, Any]:
        if not self.has_location:
            # No ongoing activity with a position: what a collar that has never
            # had a fix looks like to pytryfi.
            return {"__typename": "OngoingRest", "areaName": None}
        here = {"latitude": 10.001, "longitude": 20.002}
        there = {"latitude": 10.101, "longitude": 20.202}
        if self.location_mode.startswith("walk"):
            positions = (
                []
                if self.location_mode == "walk_no_positions"
                else [
                    {"date": "2026-11-10T07:30:00Z", "position": here},
                    {"date": "2026-11-10T07:31:00Z", "position": there},
                ]
            )
            return {
                "__typename": "OngoingWalk",
                "areaName": "Park",
                "start": "2026-11-10T07:30:00Z",
                "positions": positions,
                "path": [here, there],
            }
        place = None
        if self.location_mode == "rest":
            place = {"name": "Home", "address": "1 Example Road"}
        return {
            "__typename": "OngoingRest",
            "areaName": "Home",
            "start": "2026-11-10T07:00:00Z",
            "position": here,
            "place": place,
        }

    def stats(self) -> dict[str, Any]:
        def period(steps: int, metres: float) -> dict[str, Any]:
            return {"stepGoal": 10000, "totalSteps": steps, "totalDistance": metres}

        return {
            "dailyStat": period(self.daily_steps, 3456.0),
            "weeklyStat": period(30000, 23456.0),
            "monthlyStat": period(120000, 98765.0),
        }

    def rest(self) -> dict[str, Any]:
        def period(sleep: int, nap: int) -> dict[str, Any]:
            if not self.has_rest_stats:
                return {"restSummaries": []}
            amounts = [
                {"type": "SLEEP", "duration": sleep},
                {"type": "NAP", "duration": nap},
            ]
            return {"restSummaries": [{"data": {"sleepAmounts": amounts}}]}

        return {
            "dailyStat": period(30000, 3000),
            "weeklyStat": period(200000, 20000),
            "monthlyStat": period(900000, 90000),
        }

    # ------------------------------------------------------------- routing
    def login(self, data: dict[str, str]) -> FakeResponse:
        self.requests.append("login")
        mode = self.login_mode
        if mode == "flaky":
            self.login_mode = "ok"
            raise requests.ConnectionError("connection reset")
        if mode == "unreachable":
            raise requests.ConnectionError("no route to host")
        if mode == "error_500":
            return FakeResponse(500, {})
        if mode == "reject_401" or (
            mode == "ok" and data.get("password") != self.password
        ):
            return FakeResponse(401, {})
        if mode == "reject_body":
            return FakeResponse(200, {"error": {"message": "Invalid credentials"}})
        return FakeResponse(200, {"userId": "user-0001", "sessionId": "session-0001"})

    def query(self, text: str) -> FakeResponse:
        if self.graphql_down:
            raise requests.ConnectionError("graphql unreachable")
        if self.graphql_errors:
            body = {"errors": [{"message": "Not authenticated"}], "data": None}
            return FakeResponse(200, body)
        if "ongoingActivity" in text:
            self.requests.append("location")
            if self.location_fails:
                raise requests.ConnectionError("location query failed")
            return FakeResponse(
                200, {"data": {"pet": {"ongoingActivity": self.location()}}}
            )
        if "currentActivitySummary" in text:
            self.requests.append("stats")
            return FakeResponse(200, {"data": {"pet": self.stats()}})
        if "restSummaryFeed" in text:
            self.requests.append("rest")
            return FakeResponse(200, {"data": {"pet": self.rest()}})
        if "UserFullDetails" in text.split("fragment")[0]:
            self.requests.append("households")
            body = {"currentUser": {"userHouseholds": self.households()}}
            return FakeResponse(200, {"data": body})
        self.requests.append("user")
        user = {
            "email": "someone@example.com",
            "firstName": "Sam",
            "lastName": "Example",
            "phoneNumber": None,
        }
        return FakeResponse(200, {"data": {"currentUser": user}})

    def mutate(self, body: dict[str, Any]) -> FakeResponse:
        if self.mutations_fail:
            raise requests.ConnectionError("mutation failed")
        variables = body["variables"]
        self.mutations.append(variables)
        if "ledColorCode" in variables:
            self.led_code = variables["ledColorCode"]
            key = "setDeviceLed"
        else:
            params = variables["input"]
            if "ledEnabled" in params:
                self.led_enabled = params["ledEnabled"]
            if "mode" in params:
                self.mode = params["mode"]
            key = "updateDeviceOperationParams"
        answer = None if self.mutations_answer_empty else self.device()
        return FakeResponse(200, {"data": {key: answer}})


class FakeSession:
    """Takes requests.Session's place. Bound to a FakeCloud by make_session."""

    cloud: FakeCloud

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.closed = False
        self.cloud.sessions.append(self)

    def post(
        self,
        url: str,
        data: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        # Every request must carry a timeout: without one a dead connection
        # hangs the poll for ever, which is what upstream did.
        assert timeout, "request sent without a timeout"
        if url.endswith("/auth/login"):
            return self.cloud.login(data or {})
        assert url == "https://api.tryfi.com/graphql", url
        return self.cloud.mutate(json or {})

    def get(
        self, url: str, params: dict[str, str], timeout: float | None = None
    ) -> FakeResponse:
        assert timeout, "request sent without a timeout"
        assert url == "https://api.tryfi.com/graphql", url
        return self.cloud.query(params["query"])

    def close(self) -> None:
        self.closed = True


def make_session(cloud: FakeCloud) -> type[FakeSession]:
    return type("BoundFakeSession", (FakeSession,), {"cloud": cloud})
