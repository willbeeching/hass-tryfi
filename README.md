# TryFi for Home Assistant

[![CI](https://github.com/willbeeching/hass-tryfi/actions/workflows/ci.yaml/badge.svg)](https://github.com/willbeeching/hass-tryfi/actions/workflows/ci.yaml)
[![GitHub Release](https://img.shields.io/github/v/release/willbeeching/hass-tryfi?include_prereleases)](https://github.com/willbeeching/hass-tryfi/releases)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/willbeeching/hass-tryfi/blob/master/LICENSE)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![vibe-coded](https://img.shields.io/badge/vibe-coded-ff69b4?logo=musicbrainz&logoColor=white)](https://en.wikipedia.org/wiki/Vibe_coding)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20me%20AI%20tokens-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/willbeeching)

Get your dog's (or cat's) TryFi collar into Home Assistant: where they are, whether they're out
on a walk, steps, distance, sleep, the collar's battery, its light, and Lost Mode.

This is a maintained fork of [sbabcock23/hass-tryfi](https://github.com/sbabcock23/hass-tryfi),
which has had no code change since January 2025 and has over thirty open issues. It keeps the
same domain, the same entity ids and the same unique ids, so it drops in over the original and
your entities, history and automations carry on.

## Why this fork exists

**The original sends data to a third party.** The only release of its library on PyPI, pytryfi
0.0.21, starts an error-reporting client (Sentry) with a key owned by the library's author the moment it
signs in. That client hooks Home Assistant's root logger, so every error from anything in your
Home Assistant goes off-box, not just TryFi's. And when a sign-in fails, the report it sends
can include the frame holding your email and password, which its scrubber does not reach. Upstream
removed the call in April 2025 but never released it (upstream
[#115](https://github.com/sbabcock23/hass-tryfi/issues/115)).

This fork carries its own copy of pytryfi with all of that removed. It sends nothing anywhere
but `api.tryfi.com`, and a test fails if any file in the integration names the reporting library
or any other host.

**It also fixes what was broken.** Every open upstream issue is listed in
[docs/UPSTREAM_ISSUES.md](docs/UPSTREAM_ISSUES.md) with its cause and what was done. The big
ones:

- **"Only the bases show up."** One pet without a collar on the account (a Nano chip, a cat, a
  pet shared with you, a collar you retired) made the library abandon every pet. Each pet now
  loads on its own.
- **"Data stops updating until I reload."** No request had a timeout, so a connection that died
  quietly (a router failing over, say) hung the poll for ever. Now requests time out, a failed
  poll signs in again on a fresh connection, and the entities show unavailable while TryFi is
  unreachable instead of silently going stale.
- **The options dialog failed with a 500**, and the polling rate it saved was never read.
- **A wrong password was accepted at setup**, then retried in the background for ever. Now the
  form says so, and a password changed later asks you for the new one.
- **Ready for the 2027 removals** in Home Assistant, with no deprecation warnings on 2026.11.

## What you get

For each pet with a collar, a device named after the pet:

- **Tracker**, with the pet's photo, resolving to your zones. Unknown, not an error, until the
  collar has its first fix.
- **Activity**: Resting or Walking, and the saved place they're at.
- **Today's steps, distance, sleep and nap**, with long-term statistics. Weekly and monthly
  totals are there too, disabled by default.
- **Collar light**, colour included, and **Lost Mode**. Both update the moment you change them.
- **Diagnostics**: battery level and charging, and how the collar last connected (base, Wi-Fi,
  cellular or a phone), with which base, whose phone or the signal strength.

Each charging base shows as online or offline. Every entity is described in
[docs/ENTITIES.md](docs/ENTITIES.md).

## Requirements

- Home Assistant 2025.1 or newer.
- A TryFi account with at least one collar, and its email and password.

## Installation

### HACS (recommended)

1. In HACS, open **⋮** → **Custom repositories** and add `https://github.com/willbeeching/hass-tryfi`
   with category **Integration**.
2. Install **TryFi (maintained fork)**.
3. Restart Home Assistant.

### Manual

Download `tryfi.zip` from the [latest release](https://github.com/willbeeching/hass-tryfi/releases),
extract it into `config/custom_components/`, and restart.

### Moving over from sbabcock23/hass-tryfi

Your entities, their history and your automations are kept. In this order:

1. **Disable the existing TryFi entry and restart Home Assistant.** Settings → Devices & Services
   → TryFi → ⋮ → Disable. The old library's reporting client is loaded into the running process;
   only a restart unloads it.
2. **Change your TryFi password** in the TryFi app. If the old library ever sent a failed sign-in,
   the password went with it.
3. In HACS, **remove sbabcock23/hass-tryfi** (removing its files is fine; this replaces them),
   then add this repository as above, install it, and restart.
4. **Re-enable the TryFi entry.** Home Assistant will ask for your password again, because you
   changed it: enter the new one.
5. Check your tracker updates, and look over anything that used the two sensors whose states
   changed (below).

## Setup

**Settings → Devices & Services → Add Integration → TryFi.** Enter the email and password you
use in the TryFi app. A wrong password says so straight away.

### Options

**Settings → Devices & Services → TryFi → Configure.**

| Option | Default | What it does |
| --- | --- | --- |
| Polling interval | 60 seconds | How often TryFi is asked for new readings. At least 60. Saving reloads the integration; entity ids and history are kept. |

Upstream defaulted to 10 seconds. Each poll is a handful of requests per pet, and a collar
reports far less often than that, so a faster poll mostly fetches the same answer again. An
entry carried over from upstream at 10 seconds is raised to 60.

## Breaking changes from upstream

- **Activity type** reads `resting` / `walking`, not `OngoingRest` / `OngoingWalk`.
- **Connected to** reads `base` / `wifi` / `cellular` / `phone`, not `ConnectedToBase` and so on.
  TryFi's `UnknownConnectivity` is now plain unknown.
- The tracker's `battery_level` attribute is gone (Home Assistant stops supporting it in 2027.7).
  Use `sensor.<pet>_collar_battery_level`.

The full old-to-new table is in [docs/ENTITIES.md](docs/ENTITIES.md#moving-from-upstream-states-that-changed).
Entity ids, unique ids and long-term statistics are unchanged.

## How it works

It signs in with your email and password, the way the TryFi app does, and asks TryFi's cloud for
each pet's position, activity and totals on a timer. TryFi has no push or token sign-in for
third parties, so the password has to be kept, in your Home Assistant config entry and nowhere
else, to sign in again when TryFi's session lapses.

- **Location is where the collar last reported**, which it does on its own schedule.
- **If TryFi stops answering**, the poll gives up after 30 seconds, signs in once more on a fresh
  connection, and otherwise marks the entities unavailable until TryFi is back. It does not retry
  in a loop.
- **If TryFi rejects the password**, the TryFi entry asks you to sign in again, rather than
  retrying the old password in the background.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| A pet is missing | Pets with no collar are skipped on purpose. For a collared pet, download diagnostics (below) and open an issue. |
| Entities unavailable | TryFi isn't answering. They come back on their own; the log says why. |
| TryFi asks you to sign in again | Your TryFi password changed. Enter the current one in the prompt on the TryFi entry. |
| Distance reads 0 while steps climb | That's the figure TryFi returns; see [ENTITIES.md](docs/ENTITIES.md#what-the-numbers-mean). |
| Something else | **Settings → Devices & Services → TryFi → ⋮ → Download diagnostics**. Your email, password, pet and place names and coordinates are already removed, so it can go straight into an issue. |

## Documentation

| | |
| --- | --- |
| [Entities](docs/ENTITIES.md) | Every entity, what it means, and what changed from upstream |
| [Upstream issues](docs/UPSTREAM_ISSUES.md) | Every open upstream issue, its cause, and what this fork did |
| [Vendored pytryfi](custom_components/tryfi/pytryfi/VENDORED.md) | Where the library came from and every change made to it |

## Credits

Built on the work of **Steve Babcock** ([sbabcock23](https://github.com/sbabcock23)), who wrote
both the original integration and the pytryfi library it depends on, and of
**[disruptivepatternmaterial](https://github.com/disruptivepatternmaterial)**, whose fork first
removed the third-party reporting from pytryfi and is the commit this one vendors. Licensed under
the Apache License 2.0, as the originals are; see [LICENSE](LICENSE).

## Disclaimer

An unofficial community project, with no affiliation to or endorsement from TryFi. "TryFi" and "Fi" are their trademarks, used here only to say what this connects to. It talks
to TryFi's undocumented API, which can change without notice. It was developed with AI assistance,
comes with no warranty, and you use it with your own account at your own risk.

It reads your own pets' data from your own account into your own Home Assistant, and changes only
the collar light and Lost Mode when you ask it to. Nothing goes through me or anyone else.

## Support

If this saved you a walk round the garden looking for the cat, consider
[buying me some AI tokens](https://buymeacoffee.com/willbeeching) ☕🤖. Entirely optional; bug
reports and stars are appreciated just as much.
