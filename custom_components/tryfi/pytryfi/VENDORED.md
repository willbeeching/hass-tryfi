# Vendored pytryfi

A copy of [pytryfi](https://github.com/sbabcock23/pytryfi) by Steve Babcock,
Apache 2.0 (see `LICENSE` here), taken from
[disruptivepatternmaterial/pytryfi](https://github.com/disruptivepatternmaterial/pytryfi)
at commit `cc31b965d408794a8cb4311a9d8695b622f1e5cc` (tag `v0.0.22.post2`).
That commit is upstream's 0.0.22 plus two changes: the third-party error
reporting removed, and location attributes defaulted to `None`.

It is vendored rather than installed for two reasons:

- **Nothing is fetched at install time.** No git dependency, no PyPI package
  that could change underneath a release.
- **The installed one is never used by accident.** Anyone moving over from
  upstream hass-tryfi still has pytryfi 0.0.21 in Home Assistant's
  site-packages, and that release starts reporting to its author's service the
  moment it is constructed. Every import here is relative, so this copy cannot
  reach for it. `tests/test_api.py` plants a booby-trapped top-level `pytryfi`
  to prove it.

It is not formatted, linted or type-checked by this repo's tooling, so that a
diff against the commit above shows only the changes made on purpose. Every
change is marked in the code with a `hass-tryfi:` comment and listed below.

## Changes from the pinned commit

| File | Change | Why |
| --- | --- | --- |
| all | `from pytryfi.x` → `from .x` | Never import the installed 0.0.21 (above). |
| `_reporting.py` | Replaces the commit's no-op shim. Swallowed exceptions go to this package's logger at debug level. | So they can be seen with debug logging, and go nowhere else. |
| `common/__init__.py` | Added, empty. | A regular package rather than a namespace one. |
| `common/query.py` | 30-second timeout on every request. | No timeout meant a connection that died silently hung the poll until a reload (#56, #91). |
| `common/query.py` | Non-2xx answers raise; a GraphQL `errors` answer with no data raises `TryFiError` with TryFi's message. | Failures surfaced as a `KeyError` somewhere else, or not at all. |
| `__init__.py` | Login request has the same timeout. | As above. |
| `__init__.py` | Pets and bases load one at a time; one that fails is skipped (first load) or keeps its last readings (refresh). | One odd pet abandoned every pet: "only the bases show up" (#61, #62, #67, #87, #96, #99, #102). |
| `__init__.py` | Pets whose `device` is not an object are skipped. | Upstream compared it with the string `"None"`, but TryFi sends `null` for a pet with no collar (a Nano chip, a cat, a shared pet). |
| `__init__.py` | Location, activity and rest are fetched separately per pet; a failure in one carries that group's previous readings over. | One failed query no longer blanks the pet. |
| `__init__.py` | `update()` fetches the households once for pets and bases, and raises if it fails. | Upstream made the same request twice per poll, and swallowed failure so data went stale silently. |
| `__init__.py` | "Cannot find Pet/Base" logged at debug, not error. | Home Assistant asks for a pet that left the account on every refresh. |
| `fiDevice.py` | Every attribute defaults to `None` (charging to `False`); fields read in independent groups. | A collar reporting less (Fi Mini, Series 3+) left later attributes undefined: `_ledOn` (#69), `_mode` (#100). |
| `fiDevice.py` | `connectionSignalStrength`, `connectedBaseId`, `connectedUserFirstName`. | Which base, whose phone, what signal (#60). Already in the response. |
| `fiBase.py` | Defaults, and fields read with `.get`. | A base without `infoLastUpdated` failed the sensor platform (#93). |
| `fiPet.py` | `place: null` handled. | TryFi sends it when resting somewhere that is not a saved place. |
| `fiPet.py` | A walk with no positions yet uses the end of its path. | Otherwise the tracker lost its fix at the start of every walk. |
| `fiPet.py` | Each stats period read independently. | A period left out no longer costs the other two. |
| `fiPet.py` | `setConnectedTo` tolerates no connection state. | A collar that never connected failed the whole pet. |

Issue numbers are on [sbabcock23/hass-tryfi](https://github.com/sbabcock23/hass-tryfi/issues).

The GraphQL queries themselves are unchanged. Upstream's master trimmed some
fields from them, but these are the queries running against TryFi on working
installs today, and changing one without an account to test it against risks
breaking every install at once.
