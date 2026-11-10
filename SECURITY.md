# Security policy

## Reporting a vulnerability

Please report anything security-relevant privately, using GitHub's
[report a vulnerability](https://github.com/willbeeching/hass-tryfi/security/advisories/new)
form, rather than opening a public issue.

This is a spare-time project rather than a product, so please do not expect a
same-day reply, but reports will be read and acted on.

## What is worth reporting

The integration holds the email and password of someone's TryFi account, and
reads where their pet is. Anything that could expose those is worth reporting:

- Credentials, pet locations or addresses appearing in logs or in the
  diagnostics download. Both are routinely pasted into public issues.
- Anything sending data anywhere other than `api.tryfi.com`.

That second point is why this fork exists. Upstream's pytryfi reported errors,
and every error record in the Home Assistant process, to a third-party service
owned by its author. The vendored copy here has none of that, and
`tests/test_no_telemetry.py` fails if any file names the reporting library or
any host other than TryFi's.

## What is out of scope

- That the integration talks to TryFi using the owner's own credentials. That
  is what it is for.
- Vulnerabilities in Home Assistant itself; report those to
  [Home Assistant](https://www.home-assistant.io/security/).
- Anything requiring an attacker who already has access to the Home Assistant
  configuration directory.

## Handling of secrets

The email and password live only in the Home Assistant config entry. TryFi
offers no token-based sign-in, so the password has to be kept to sign in again
when TryFi's session lapses.
