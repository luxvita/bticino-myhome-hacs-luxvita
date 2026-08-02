# Changelog

All notable changes to this fork are documented here. Based on
[Léo's `bticino-myhome-hacs-byLeo`](https://github.com/llellouc/bticino-myhome-hacs-byLeo)
— see `CREDITS.md`.

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
