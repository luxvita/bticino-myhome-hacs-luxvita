# Credits

This project stands on the work of others. In order of the fork chain:

## anotherjulien — original author

[anotherjulien](https://github.com/anotherjulien) designed and wrote the
original `MyHome` Home Assistant integration
(https://github.com/anotherjulien/MyHOME), including the OWNd library this
project still vendors for OpenWebNet communication with BTicino/Legrand
gateways. Every fork in this chain, including this one, is built on that
initial work.

## Léo (llellouc) — bticino-myhome-hacs-byLeo

[Léo](https://github.com/llellouc) forked and substantially reworked the
integration in `bticino-myhome-hacs-byLeo`
(https://github.com/llellouc/bticino-myhome-hacs-byLeo), focusing on:

- gateway worker stability
- active discovery and passive discovery from bus activity
- a device-configuration web panel (no YAML dependency)
- stronger climate and power support

This fork was branched directly from Léo's codebase. All of the fixes
described in `CHANGELOG.md` were diagnosed and tested against his gateway
worker implementation, and the overall architecture of the integration
(config flow, discovery panel, sending/listening workers) is his design.
Thank you, Léo, for the foundation this was built on.

## This fork

Maintained by [luxvita](https://github.com/luxvita). See `CHANGELOG.md` and
the "What's Fixed in This Fork" section of `README.md` for what changed here.
