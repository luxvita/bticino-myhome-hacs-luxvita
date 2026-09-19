# Changelog

All notable changes to this fork are documented here. Based on
[Léo's `bticino-myhome-hacs-byLeo`](https://github.com/llellouc/bticino-myhome-hacs-byLeo)
— see `CREDITS.md`.

## 1.3.0

Hardening pass driven by a real-world install (F418U2 gateway, ~60 devices
across lights, covers and heating zones), aimed at forward compatibility
with future Home Assistant releases (defensive access instead of direct
key lookups, so a future core/HA change to the entity-storage shape or a
partially-migrated config entry degrades gracefully instead of crashing
the whole integration) as well as day-to-day reliability.

### Fixed

- **`KeyError` crashes on optional config keys.** `light.py`, `cover.py`
  and `button.py` read `CONF_ENTITY_NAME` and `CONF_DEVICE_MODEL` with
  direct dict indexing (`config[KEY]`), even though both are optional
  schema keys. Any device configured without them crashed setup. Switched
  to `.get(KEY)`. Same issue in `myhome_device.py` and `button.py`'s
  enable/disable command entities, which indexed `CONF_ENTITIES` directly
  in `async_added_to_hass`/`async_will_remove_from_hass`/`async_press` —
  now uses `.setdefault(...)`/`.get(...)` so a device dict that hasn't
  had `CONF_ENTITIES` populated yet no longer raises.
- **Covers could get stuck on "opening"/"closing" forever.** This
  integration is fully push-driven (`should_poll=False`); if the gateway
  drops the final `*2*0*<where>##` stop event on the bus, the cover
  entity never got another update. Added a 150s self-healing timeout
  (`COVER_MOVEMENT_TIMEOUT`) per cover: if no follow-up event arrives
  while a cover reports movement, the integration now actively requests a
  fresh status instead of leaving the entity stuck.
- **Energy/power discovery stored a malformed WHERE.** `OWNEnergyEvent`
  messages carry a leading type digit (`5`/`7`) glued to the actual sensor
  number (e.g. `588` for sensor `88`); `_extract_energy_where()` wasn't
  stripping it, so newly discovered energy sensors got the wrong address —
  the same class of bug already fixed for climate/light/cover repoll in
  1.1.0. Climate discovery WHERE parsing was tightened the same way,
  logging when a raw WHERE differs from the parsed zone.
- **`close_listener` race on quick reload.** Unloading the gateway could
  return before its sender workers had actually finished and closed their
  command session, so a fast reload risked opening a new command session
  while the old one was still being torn down — something the gateway
  itself doesn't tolerate. Unload now waits (up to 10s) for the sender
  workers to finish before proceeding.
- **Schema validation instantiated every platform schema eagerly.**
  `gateway_schema`'s `Optional(...)` entries called each platform schema
  directly, so a gateway with, say, no `climate` devices could still
  trip on an unrelated schema at load time. Wrapped each in a `lambda`
  so they're only evaluated for platforms that are actually configured.

### Changed

- Downgraded two more routine log lines from `WARNING`/`ERROR` to
  `DEBUG`/`WARNING`: the per-send `[DIAG]` queue/worker status line, and
  the "Could not send message, retrying" line for the first two retry
  attempts (an eventual NACK after all retries still logs as an error).
  Neither is actionable on its own — they were drowning out real problems
  in the log.

### Added

- Local brand icon/logo shipped inside the integration
  (`custom_components/bticino_myhome/brand/`) so the device page shows
  the BTicino logo without depending on the `home-assistant/brands`
  repository being updated first. Repository icon/logo added for the
  HACS listing itself.
- CI: brands check skipped, `actions/checkout` bumped to v4.

## 1.1.0

### Fixed

- **Repoll used the internal device key instead of the real address.**
  `_repoll_all_entities()` re-queries every known entity after an event
  session reconnect. It was using the entities dict's key — the internal
  `{WHO}-{WHERE}` config identifier (e.g. `1-32`, `4-7`, see
  `validate.py`) — as the WHERE address sent to the gateway, instead of
  the actual device address. The gateway correctly rejected every one of
  these malformed requests with a NACK:
  ```
  Could not send message `*#1*1-32##`. No more retries.
  Could not send message `*#4*4-7##`. No more retries.
  ```
  instead of the valid `*#1*32##` / `*#4*7##`. Light and cover devices
  store their address under `CONF_WHERE`; climate devices store it under
  `CONF_ZONE` instead (see `climate_schema` in `validate.py`). The fix
  reads the correct field per platform.

- **`DisableCommandButtonEntity` / `EnableCommandButtonEntity` crashed the
  sending worker.** Neither class implemented `handle_event`, which
  `_dispatch_command_responses()` calls whenever the gateway echoes back a
  response to a sent command:
  ```
  AttributeError: 'DisableCommandButtonEntity' object has no attribute 'handle_event'
  ```
  Buttons are pure command entities with no bus-driven state, so the fix
  is a no-op stub matching the pattern used by other command-only
  entities.

- **Non-string manufacturer/model/serial values from discovery.** UPnP/SSDP
  discovery can return `manufacturer`, `modelName`, `modelNumber` and
  `serialNumber` as a list instead of a plain string. These values flow
  straight into Home Assistant's device registry (`manufacturer`, `model`,
  `sw_version`), which warns today and will hard-fail in HA 2026.12.0.
  Added a `_coerce_to_str()` helper applied to every discovery field that
  ends up in the device registry or in per-entity `CONF_MANUFACTURER`.

### Changed

- Downgraded the routine `Event session connection lost... Reconnecting`
  log from `WARNING` to `INFO`. The session is torn down and
  re-established automatically in the same code path, so it isn't an
  actionable warning for the user.

### Added

- **Command send pacing** (`SEND_THROTTLE_DELAY`, default `0.1` seconds).
  After a full entity repoll, dozens of status requests were previously
  fired back-to-back with only network round-trip time as spacing. This
  paces outgoing commands so the gateway isn't asked to relay messages onto
  the physical OpenWebNet bus faster than it can realistically process
  them.
- **Idle command session recycling** (`COMMAND_SESSION_IDLE_TIMEOUT`,
  default `60` seconds). The gateway silently closes command sessions that
  sit idle for a while (observed ~90-120s). The sending worker previously
  only discovered this via a failed write (`0 bytes read on a total of
  undefined expected bytes`), costing one wasted round trip on the first
  message after any idle period. The worker now tracks time since last use
  and proactively closes and reopens the session if it's been idle too
  long, before attempting to send.

Both `SEND_THROTTLE_DELAY` and `COMMAND_SESSION_IDLE_TIMEOUT` are defined
as constants in `const.py` and can be tuned if your gateway needs a
different pacing.
