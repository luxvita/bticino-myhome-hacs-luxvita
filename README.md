<p align="left">
  <img src="custom_components/bticino_myhome/frontend/bticino-logo.svg" alt="bticino logo" width="180" />
</p>

# bticino MyHome Unofficial Integration

Custom Home Assistant integration for BTicino/Legrand MyHome gateways over OpenWebNet.

## Project Status

This repository maintains and evolves a fork of the MyHome integration, with focus on:

- gateway worker stability
- active discovery and passive discovery from bus activity
- web UI for device discovery and configuration
- stronger climate and power support

## What's Fixed in This Fork

This fork started from a real-world debugging session against a home OpenWebNet
installation (F418U2 gateway, ~60 devices across lights, covers, and heating
zones). The following issues were found and fixed:

- **Repoll used the wrong address.** After an event-session reconnect, the
  integration re-polled every known entity but sent the internal
  `{WHO}-{WHERE}` config key (e.g. `1-32`, `4-7`) instead of the actual device
  address, so the gateway NACKed every single request. Light/cover entities
  now read their address from `CONF_WHERE`; climate zones read it from
  `CONF_ZONE`, matching how each platform's schema actually stores it.
- **Command bursts overwhelmed the gateway.** A full re-poll fired dozens of
  requests back-to-back with no pacing. A small delay between sends
  (configurable, `SEND_THROTTLE_DELAY`) keeps the burst within what the
  gateway can relay onto the physical bus.
- **Idle command sessions failed silently.** The gateway closes command
  sessions after a period of inactivity; the integration only discovered this
  on the next failed write. It now tracks session age and proactively
  recycles a session that's been idle too long (`COMMAND_SESSION_IDLE_TIMEOUT`).
- **`DisableCommandButtonEntity`/`EnableCommandButtonEntity` crashed the
  sending worker** on any command response, because neither implemented
  `handle_event`. Added as a no-op, matching their command-only nature.
- **Non-string manufacturer/model/serial values crashed device registry
  compatibility.** UPnP/SSDP discovery can hand back a list instead of a
  plain string for these fields; Home Assistant now warns (and will hard-fail
  in 2026.12.0) when that happens. All discovery fields feeding the device
  registry are now coerced to a clean string.
- **Routine event-session reconnects were logged as `WARNING`.** Since the
  session is torn down and re-established automatically in the same code
  path, this is downgraded to `INFO`.

See `CHANGELOG.md` for details.

## Main Features

- gateway setup through Home Assistant Config Flow
- supported platforms: `light`, `cover`, `climate`, `sensor`, `switch`, `binary_sensor`
- custom MyHome services (`sync_time`, `send_message`, discovery services)
- device configuration from web UI (no YAML dependency)
- direct import of discovered devices into runtime configuration
- manual add/remove of devices from the UI
- power endpoint discovery support (`WHO 18`)
- OWNd library vendored inside the integration (`0.7.49`, author: `anotherjulien`)

## Requirements

- Home Assistant (Core or Container)
- IP connectivity from Home Assistant to your MyHome gateway

## Installation

### HACS (recommended)

Prerequisite: HACS must already be installed.

1. Open Home Assistant and go to `HACS`.
2. Open the top-right menu (`⋮`) and choose `Custom repositories`.
3. Add:
   - Repository: `https://github.com/luxvita/bticino-myhome-hacs-luxvita`
   - Category: `Integration`
4. Click `Add`.
5. Search for `bticino MyHome` in HACS and open the integration page.
6. Click `Download` and complete installation.
7. Restart Home Assistant.
8. Go to `Settings` -> `Devices & Services` -> `Add Integration`.
9. Search for `bticino MyHome` and complete the config flow.

Optional direct link:

`https://my.home-assistant.io/redirect/hacs_repository/?owner=luxvita&repository=bticino-myhome-hacs-luxvita&category=integration`

### Manual

1. Copy `custom_components/bticino_myhome` to `config/custom_components/bticino_myhome`.
2. Restart Home Assistant.
3. Add and configure `bticino MyHome` from `Settings` -> `Devices & Services`.

## Device Configuration

Use the integration web panel to manage devices:

- automatic discovery by activation (passive collection)
- import discovered devices into configuration
- manual device creation and deletion

## Troubleshooting

- If entities stop updating after changes, restart Home Assistant. Reloading
  the integration from the UI does not always reimport changed Python files;
  a full Core restart guarantees a clean reload.
- If discovery fails, inspect logs for `custom_components.bticino_myhome`.
- Verify gateway reachability, IP address, and credentials.
- For deeper diagnostics, enable debug logging via **Developer Tools →
  Actions → Logger: Set Level**, with:
  ```yaml
  action: logger.set_level
  data:
    custom_components.bticino_myhome: debug
  ```

## Acknowledgments

This integration exists because of the work of several people before it:

- **[anotherjulien](https://github.com/anotherjulien)**, who wrote the
  original MyHome integration and the underlying OpenWebNet (OWNd) library
  that this project still vendors.
- **Léo ([@llellouc](https://github.com/llellouc))**, whose fork
  (`bticino-myhome-hacs-byLeo`) rebuilt gateway worker stability, added
  active/passive discovery, and the device-configuration web panel that this
  fork builds directly on top of. The fixes in this repository were found and
  tested against his codebase, and a large part of what works well here is
  thanks to that foundation. Thank you, Léo.

See `CREDITS.md` for the full acknowledgments.

## License

See `LICENSE`.
