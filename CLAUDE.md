# Working on this repository

A maintained fork of sbabcock23/hass-tryfi: a Home Assistant custom integration
for TryFi dog collars. One domain, `tryfi`, in `custom_components/tryfi/`, with
its own copy of the pytryfi library in `custom_components/tryfi/pytryfi/`.

## Non-negotiables

**Send nothing anywhere but `api.tryfi.com`.** This fork exists because
upstream's library reported every error in Home Assistant to its author's
error-reporting service. `tests/test_no_telemetry.py` fails if any file in the
integration names that library or any other host. Do not add an endpoint.

**Never commit secrets.** No emails, passwords, pet names, place names,
addresses or coordinates from a real account, in code, tests, fixtures, commit
messages or issue replies. The fake cloud in `tests/fakes.py` uses made-up
values of the same shape; keep it that way. Diagnostics redact the same list;
extend `diagnostics.py` rather than working around it.

**Entity ids and unique ids are frozen.** Every unique id format is upstream's,
byte for byte, and entity names are chosen so Home Assistant builds the same
entity ids upstream's names did. Users moved over with their history and
automations intact. `tests/ha/test_entities.py` holds both lists; if one of
them has to change, it is a breaking change and needs a migration.

**Be a polite client.** TryFi's cloud is not ours. The polling floor is 60
seconds, a failed poll signs in again at most once, and one households query
serves both pets and bases. A change that talks to TryFi more often needs a
reason better than responsiveness.

**Releases happen only when the maintainer asks.** Merging is not releasing.

## The vendored pytryfi

Taken from disruptivepatternmaterial/pytryfi at `cc31b96`. Every import in it
is relative, so the pytryfi 0.0.21 still sitting in site-packages on any
install moved over from upstream (the one that reports) can never be reached.

It is not formatted, linted or type-checked here, so a diff against the pinned
commit shows only deliberate changes. Every change carries a `hass-tryfi:`
comment and a row in `pytryfi/VENDORED.md`, with the upstream issue it fixes.
Keep doing both.

Do not change the GraphQL queries without an account to test them against:
they are what works against TryFi today, and a broken query breaks every
install at once.

## What is settled about TryFi's data

Learned from upstream's issue tracker; see `docs/UPSTREAM_ISSUES.md`.

- **A pet's `device` is `null`, not `"None"`,** for a pet with no collar (a
  Nano chip, a cat, a shared pet). One such pet used to hide every other.
- **Collars report different fields.** The Fi Mini and Series 3+ leave some
  out. Every collar attribute defaults to `None` and entities show unknown.
- **Connection types grow.** `ConnectedToWifi` appeared after upstream was
  written. An unknown type reads as unknown, not as the raw API name.
- **`place` is `null`** when resting somewhere unsaved, and a walk can start
  before it has positions.
- **TryFi returns 0 for distance** on days with thousands of steps, and 0 for
  daily rest for hours at a time. Those are TryFi's figures; do not "fix" them.

## Local development

Four virtualenvs, one per CI lane, gitignored. Upgrade `uv` first
(`pip install --user --upgrade uv`): the container's old one builds 3.14 on a
release candidate.

```sh
UV=~/.local/bin/uv
$UV venv --python 3.14 .venv-ha
$UV venv --python 3.13 .venv-ha-min
$UV venv --python 3.14 .venv-lint
$UV venv --python 3.14 .venv-types

$UV pip install --python .venv-ha/bin/python     -r requirements-test.txt
$UV pip install --python .venv-ha-min/bin/python -r requirements-test-min.txt
$UV pip install --python .venv-lint/bin/python   -r requirements-lint.txt
$UV pip install --python .venv-types/bin/python  -r requirements-types.txt homeassistant
```

## The checks

Eight CI checks gate a merge. Run the first four locally before pushing.

```sh
.venv-lint/bin/black --check custom_components/ tests/
.venv-lint/bin/isort --check-only custom_components/ tests/
.venv-lint/bin/ruff check custom_components/ tests/
.venv-lint/bin/flake8 custom_components/ tests/

.venv-ha/bin/python -m pytest -q \
  --cov=custom_components/tryfi \
  --cov-report=term-missing --cov-report=json --cov-fail-under=95
.venv-ha/bin/python scripts/coverage_gate.py
.venv-ha-min/bin/python -m pytest -q

.venv-types/bin/mypy custom_components/tryfi/
```

The minimum lane runs the behaviour against core 2025.1.0, the version
`hacs.json` claims. `scripts/coverage_gate.py` enforces 95% per module; the
vendored library is omitted from coverage and tested through `tests/test_pytryfi.py`.

A refresh driven by `async_fire_time_changed` runs as a background task: wait
with `async_block_till_done(wait_background_tasks=True)`, or the assertions race
it.

## Versions and releases

- `manifest.json` carries the version, and the release workflow fails on a
  mismatch with the tag. Bump it in the same commit as the change.
- Release by `workflow_dispatch` on `release.yaml` with `version` (`v0.1.0`)
  and optional `notes`. A commit body line starting `BREAKING:` is lifted into
  a warning section at the top of the notes.
- Two archives ship: `tryfi.zip` wraps the directory for manual installs,
  `tryfi-hacs.zip` has the files at its root for HACS. They are not
  interchangeable.

## Code conventions

As in willbeeching/ha-jlr-incontrol: comments explain why, usually by naming
the upstream issue; line length 88, black, isort (black profile), ruff with
`E F W I UP B SIM C4 RET PTH`; strict mypy spelled out in `pyproject.toml`;
flow schemas import `probatio` as `vol` on core 2026.10+ and `voluptuous`
before it. Tests in `tests/` drive the real vendored library against the fake
cloud; tests in `tests/ha/` drive a running Home Assistant. Widen
`tests/fakes.py` rather than hand-rolling a payload per test.
