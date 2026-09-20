"""Support for MyHome covers."""
from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as PLATFORM,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)

from homeassistant.const import (
    CONF_NAME,
    CONF_MAC,
)

from homeassistant.helpers.event import async_call_later

from .OWNd.message import (
    OWNAutomationEvent,
    OWNAutomationCommand,
)

from .const import (
    CONF_PLATFORMS,
    CONF_ENTITY,
    CONF_ENTITY_NAME,
    CONF_WHO,
    CONF_WHERE,
    CONF_BUS_INTERFACE,
    CONF_MANUFACTURER,
    CONF_DEVICE_MODEL,
    CONF_ADVANCED_SHUTTER,
    DOMAIN,
    LOGGER,
)
from .myhome_device import MyHOMEEntity
from .gateway import MyHOMEGatewayHandler

# Fallback timeout (seconds): if a cover reports opening/closing but no
# follow-up event (stop/position) arrives within this window, actively
# request a status update instead of staying stuck forever. This integration
# is fully push-driven (should_poll=False), so a single dropped bus event
# would otherwise leave the entity stuck on "opening"/"closing" indefinitely.
COVER_MOVEMENT_TIMEOUT = 150


async def async_setup_entry(hass, config_entry, async_add_entities):
    if PLATFORM not in hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_PLATFORMS]:
        return True

    _covers = []
    _configured_covers = hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_PLATFORMS][PLATFORM]

    for _cover in _configured_covers.keys():
        _cover = MyHOMECover(
            hass=hass,
            device_id=_cover,
            who=_configured_covers[_cover][CONF_WHO],
            where=_configured_covers[_cover][CONF_WHERE],
            interface=_configured_covers[_cover][CONF_BUS_INTERFACE] if CONF_BUS_INTERFACE in _configured_covers[_cover] else None,
            name=_configured_covers[_cover][CONF_NAME],
            entity_name=_configured_covers[_cover].get(CONF_ENTITY_NAME),
            advanced=_configured_covers[_cover][CONF_ADVANCED_SHUTTER],
            manufacturer=_configured_covers[_cover][CONF_MANUFACTURER],
            model=_configured_covers[_cover].get(CONF_DEVICE_MODEL),
            gateway=hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_ENTITY],
        )
        _covers.append(_cover)

    async_add_entities(_covers)


async def async_unload_entry(hass, config_entry):  # pylint: disable=unused-argument
    if PLATFORM not in hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_PLATFORMS]:
        return True

    _configured_covers = hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_PLATFORMS][PLATFORM]

    for _cover in _configured_covers.keys():
        del hass.data[DOMAIN][config_entry.data[CONF_MAC]][CONF_PLATFORMS][PLATFORM][_cover]


class MyHOMECover(MyHOMEEntity, CoverEntity):
    device_class = CoverDeviceClass.SHUTTER

    def __init__(
        self,
        hass,
        name: str,
        entity_name: str,
        device_id: str,
        who: str,
        where: str,
        interface: str,
        advanced: bool,
        manufacturer: str,
        model: str,
        gateway: MyHOMEGatewayHandler,
    ):
        super().__init__(
            hass=hass,
            name=name,
            platform=PLATFORM,
            device_id=device_id,
            who=who,
            where=where,
            manufacturer=manufacturer,
            model=model,
            gateway=gateway,
        )

        self._attr_name = entity_name

        self._interface = interface
        self._full_where = f"{self._where}#4#{self._interface}" if self._interface is not None else self._where

        self._attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        if advanced:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
        self._gateway_handler = gateway

        self._attr_extra_state_attributes = {
            "A": where[: len(where) // 2],
            "PL": where[len(where) // 2 :],
        }
        if self._interface is not None:
            self._attr_extra_state_attributes["Int"] = self._interface

        self._attr_current_cover_position = None
        self._attr_is_opening = None
        self._attr_is_closing = None
        self._attr_is_closed = None

        self._movement_timeout_cancel = None

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._gateway_handler.send_status_request(OWNAutomationCommand.status(self._full_where))

    async def async_open_cover(self, **kwargs):  # pylint: disable=unused-argument
        """Open the cover."""
        await self._gateway_handler.send(OWNAutomationCommand.raise_shutter(self._full_where))

    async def async_close_cover(self, **kwargs):  # pylint: disable=unused-argument
        """Close cover."""
        await self._gateway_handler.send(OWNAutomationCommand.lower_shutter(self._full_where))

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            await self._gateway_handler.send(OWNAutomationCommand.set_shutter_level(self._full_where, position))

    async def async_stop_cover(self, **kwargs):  # pylint: disable=unused-argument
        """Stop the cover."""
        await self._gateway_handler.send(OWNAutomationCommand.stop_shutter(self._full_where))

    def handle_event(self, message: OWNAutomationEvent):
        """Handle an event message."""
        LOGGER.debug(
            "%s %s",
            self._gateway_handler.log_id,
            message.human_readable_log,
        )
        self._attr_is_opening = message.is_opening
        self._attr_is_closing = message.is_closing
        if message.is_closed is not None:
            self._attr_is_closed = message.is_closed
        if message.current_position is not None:
            self._attr_current_cover_position = message.current_position

        if self._movement_timeout_cancel is not None:
            self._movement_timeout_cancel()
            self._movement_timeout_cancel = None

        if self._attr_is_opening or self._attr_is_closing:
            self._movement_timeout_cancel = async_call_later(
                self.hass, COVER_MOVEMENT_TIMEOUT, self._async_movement_timeout
            )

        self.async_schedule_update_ha_state()

    async def _async_movement_timeout(self, _now):
        """Recover if no stop/position event arrived after reporting movement.

        Some BTicino actuators occasionally fail to deliver the final
        `*2*0*<where>##` stop event on the bus. Since this integration is
        fully push-driven (should_poll=False), a dropped event would
        otherwise leave the entity stuck on "opening"/"closing" forever.

        A plain status request (`*#2*<where>##`) does NOT help here: for
        actuators without end-of-travel feedback, the gateway only ever
        reports the *last motion command it was told about* (1=opening,
        2=closing, 0=stopped), not the actual physical position. If the
        stop event never reached the gateway either, querying status just
        echoes back the same stale "opening"/"closing" state forever,
        even though the cover has long finished moving - which is exactly
        what was observed in practice (repeated warnings every 150s for
        hours, on covers that were not physically stuck).
        As a fallback, actively send a stop command instead: harmless if
        the cover already finished moving (which is overwhelmingly the
        common case after 150s - see COVER_MOVEMENT_TIMEOUT), and it
        resets the gateway's own bookkeeping to "stopped", which comes
        back as a proper event and clears the stuck state in HA too.
        """
        self._movement_timeout_cancel = None
        LOGGER.warning(
            "%s Cover %s still reporting %s after %ss with no update, sending stop to reset state.",
            self._gateway_handler.log_id,
            self._where,
            "opening" if self._attr_is_opening else "closing",
            COVER_MOVEMENT_TIMEOUT,
        )
        await self._gateway_handler.send(
            OWNAutomationCommand.stop_shutter(self._full_where)
        )

    async def async_will_remove_from_hass(self):
        """Cancel any pending movement-timeout timer on entity removal."""
        if self._movement_timeout_cancel is not None:
            self._movement_timeout_cancel()
            self._movement_timeout_cancel = None
