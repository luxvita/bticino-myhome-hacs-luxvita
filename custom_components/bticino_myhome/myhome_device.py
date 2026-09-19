"""Support for common values for MyHome devices."""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gateway import MyHOMEGatewayHandler

from homeassistant.helpers.entity import Entity
from homeassistant.helpers import device_registry as dr
from homeassistant.const import CONF_ENTITIES


from .const import DOMAIN, CONF_PLATFORMS, CONF_ENTITIES


class MyHOMEEntity(Entity):
    def __init__(
        self,
        hass,
        name: str,
        platform: str,
        device_id: str,
        who: str,
        where: str,
        manufacturer: str,
        model: str,
        gateway: MyHOMEGatewayHandler,
    ):
        self._hass = hass
        self._platform = platform
        self._who = who
        self._where = where
        self._device_id = device_id
        self._attr_unique_id = f"{gateway.mac}-{self._device_id}"
        self._manufacturer = manufacturer or "BTicino S.p.A."
        self._model = model
        self._gateway_handler = gateway
        self._attr_has_entity_name = True
        self._attr_name = None
        self._attr_entity_registry_enabled_default = True
        self._attr_should_poll = False

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{gateway.mac}-{self._device_id}")},
            "name": name,
            "manufacturer": self._manufacturer,
            "model": self._model,
        }

        # `via_device` (a (domain, identifier) tuple) is deprecated in favor of
        # `via_device_id` (the gateway device's actual registry entry id), which
        # is unambiguous per config entry. The gateway device is always created
        # in __init__.py before platforms are forwarded, so it's already in the
        # registry by the time entities are constructed here. Guarded with a
        # try/except anyway: if that lookup ever fails, the entity should still
        # be created (just without the "via device" link) rather than crash
        # platform setup entirely.
        try:
            _gateway_device_id = dr.async_get_device_id_by_identifier(
                hass,
                (DOMAIN, self._gateway_handler.unique_id),
                config_entry_id=self._gateway_handler.config_entry.entry_id,
            )
        except (LookupError, ValueError):
            _gateway_device_id = None
        if _gateway_device_id is not None:
            self._attr_device_info["via_device_id"] = _gateway_device_id

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self._hass.data[DOMAIN][self._gateway_handler.mac][CONF_PLATFORMS][self._platform][self._device_id].setdefault(CONF_ENTITIES, {})[self._platform] = self
        await self.async_update()

    async def async_will_remove_from_hass(self):
        """When entity is removed from hass."""
        _entities = self._hass.data[DOMAIN][self._gateway_handler.mac][CONF_PLATFORMS][self._platform][self._device_id].get(CONF_ENTITIES, {})
        if self._platform in _entities:
            del _entities[self._platform]
