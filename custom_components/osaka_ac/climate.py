"""Home Assistant N81 AC unit climate integration."""

import logging

from . import ir

from typing import Any, cast

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    ENTITY_ID_FORMAT,
)
from homeassistant.components.climate.const import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
    ATTR_HVAC_MODE,
    ATTR_FAN_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_CURRENT_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_HUMIDITY,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    PRESET_ACTIVITY,
    PRESET_BOOST,
    PRESET_SLEEP,
    PRESET_NONE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVACMode,
    HVACAction,
)
from homeassistant.components.template.const import CONF_AVAILABILITY_TEMPLATE
from homeassistant.const import (
    STATE_ON,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    ATTR_TEMPERATURE,
    CONF_NAME,
    STATE_UNKNOWN,
    STATE_UNAVAILABLE,
    CONF_ICON_TEMPLATE,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_UNIQUE_ID,
    ATTR_SUPPORTED_FEATURES,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONF_FAN_MODE_LIST = "fan_modes"
CONF_PRESET_MODE_LIST = "preset_modes"
CONF_MODE_LIST = "modes"
CONF_SWING_MODE_LIST = "swing_modes"
CONF_TEMP_MIN_TEMPLATE = "min_temp_template"
CONF_TEMP_MIN = "min_temp"
CONF_TEMP_MAX_TEMPLATE = "max_temp_template"
CONF_TEMP_MAX = "max_temp"
CONF_PRECISION = "precision"
CONF_CURRENT_TEMP_TEMPLATE = "current_temperature_template"
CONF_TEMP_STEP = "temp_step"

CONF_CURRENT_HUMIDITY_TEMPLATE = "current_humidity_template"
CONF_MIN_HUMIDITY_TEMPLATE = "min_humidity_template"
CONF_MAX_HUMIDITY_TEMPLATE = "max_humidity_template"
CONF_TARGET_HUMIDITY_TEMPLATE = "target_humidity_template"
CONF_TARGET_TEMPERATURE_TEMPLATE = "target_temperature_template"
CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE = "target_temperature_high_template"
CONF_TARGET_TEMPERATURE_LOW_TEMPLATE = "target_temperature_low_template"
CONF_HVAC_MODE_TEMPLATE = "hvac_mode_template"
CONF_FAN_MODE_TEMPLATE = "fan_mode_template"
CONF_PRESET_MODE_TEMPLATE = "preset_mode_template"
CONF_SWING_MODE_TEMPLATE = "swing_mode_template"
CONF_HVAC_ACTION_TEMPLATE = "hvac_action_template"

CONF_SET_HUMIDITY_ACTION = "set_humidity"
CONF_SET_TEMPERATURE_ACTION = "set_temperature"
CONF_SET_HVAC_MODE_ACTION = "set_hvac_mode"
CONF_SET_FAN_MODE_ACTION = "set_fan_mode"
CONF_SET_PRESET_MODE_ACTION = "set_preset_mode"
CONF_SET_SWING_MODE_ACTION = "set_swing_mode"

CONF_CLIMATES = "climates"

CONF_MQTT_TOPIC_NAME = "mqtt_topic_name"

DEFAULT_NAME = "N81 AC"
DEFAULT_TEMP = 25
DEFAULT_PRECISION = 1.0

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_TEMP_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_MIN_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_MAX_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_LOW_TEMPLATE): cv.template,
        vol.Optional(CONF_HVAC_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_FAN_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESET_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_SWING_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_HVAC_ACTION_TEMPLATE): cv.template,
        vol.Optional(CONF_SET_HUMIDITY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_HVAC_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_FAN_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_SWING_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(
            CONF_MODE_LIST,
            default=[
                HVACMode.AUTO,
                HVACMode.OFF,
                HVACMode.COOL,
                HVACMode.HEAT,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
            ],
        ): cv.ensure_list,
        vol.Optional(
            CONF_FAN_MODE_LIST,
            default=[FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        ): cv.ensure_list,
        vol.Optional(
            CONF_PRESET_MODE_LIST,
            default=[
                PRESET_BOOST,
                PRESET_SLEEP,
                PRESET_NONE,
            ],
        ): cv.ensure_list,
        vol.Optional(
            CONF_SWING_MODE_LIST, default=[STATE_ON, HVACMode.OFF]
        ): cv.ensure_list,
        vol.Optional(CONF_TEMP_MIN_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_MIN, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TEMP_MAX_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_MAX, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_TEMP_STEP, default=DEFAULT_PRECISION): vol.Coerce(float),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_MQTT_TOPIC_NAME, default="zigbee2mqtt/IR Control/set/ir_code_to_send"): cv.string,
    }
)

async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
) -> bool:
    async_add_entities([N81ACEntity(hass, config)])

    return True


class N81ACEntity(ClimateEntity, RestoreEntity):
    """N81 AC unit entity"""

    _attr_should_poll = False
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, hass: HomeAssistant, config: ConfigType):
        """Initialize the climate device."""
        super().__init__()
        self.hass = hass
        self._attr_unique_id = config.get(CONF_UNIQUE_ID)
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, config[CONF_NAME], hass=hass
        )
        self._attr_name = config[CONF_NAME]

        self._attr_supported_features: ClimateEntityFeature = ClimateEntityFeature(0)
        self._attr_supported_features |= ClimateEntityFeature.TURN_ON
        self._attr_supported_features |= ClimateEntityFeature.TURN_OFF
        self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
        self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        self._attr_temperature_unit = hass.config.units.temperature_unit

        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 16
        self._attr_fan_mode = "low"
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY
        ]
        self._attr_fan_modes = ["low", "medium", "high"]

        self.hass = hass

        self._attr_min_temp = 16
        self._attr_max_temp = 26
        self._attr_target_temperature_step = 1

        self._mqtt_topic_name = config.get(CONF_MQTT_TOPIC_NAME)

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Check If we have an old state
        previous_state = await self.async_get_last_state()
        if previous_state is not None:
            if previous_state.state in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(previous_state.state)
            if temperature := previous_state.attributes.get(
                    ATTR_TEMPERATURE, DEFAULT_TEMP
            ):
                self._attr_target_temperature = float(temperature)

            self._attr_fan_mode = previous_state.attributes.get(ATTR_FAN_MODE, FAN_LOW)
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

            self.async_write_ha_state()

    def update_control_command(self):
        """Send current settings control command to AC unit"""
        try:
            power_on = self._attr_hvac_mode != HVACMode.OFF
            temp = int(self._attr_target_temperature)

            fan_speed = 4
            if self._attr_fan_mode == "high":
                fan_speed = 1
            elif self._attr_fan_mode == "medium":
                fan_speed = 2

            mode=1
            if self._attr_hvac_mode == HVACMode.DRY:
                mode=2
            elif self._attr_hvac_mode == HVACMode.COOL:
                mode=8

            pac_data = ir.create_message(
                power=power_on, # true or false
                temp=temp,      # 16-32 or 61-89
                mode=mode,      # 1=fan, 2=dehumidify, 8=aircon
                fan=fan_speed,  # 1=high, 2=medium, 4=low
                timer=False,    # true or false
                timer_val=0,    # 0-12
                unit_f=False,   # true or false (fahrenheit or celsius)
            )

            raw_ir_timings = ir.nec_to_raw(pac_data)
            tuya_code = ir.encode_ir(raw_ir_timings)

            # _LOGGER.debug("Generated IR command: %s", tuya_code)

            if "mqtt" in self.hass.services.async_services():
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "mqtt",
                        "publish",
                        {"topic": self._mqtt_topic_name, "payload": str(tuya_code)},
                    )
                )
            else:
                _LOGGER.warning("MQTT service not available yet!")
        except Exception as e:
            _LOGGER.error("Could not generate IR command. %s", e)
        return

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if hvac_mode not in [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]:
            self._attr_supported_features &= ~ClimateEntityFeature.TARGET_TEMPERATURE
        else:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        self._attr_hvac_mode = hvac_mode  # always optimistic
        self.async_write_ha_state()

        self.update_control_command()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature explicitly triggered by user or automation."""
        updated = False

        if kwargs.get(ATTR_HVAC_MODE, self._attr_hvac_mode) in [HVACMode.COOL, HVACMode.HEAT]:
            temp = kwargs.get(ATTR_TEMPERATURE)
            if temp is not None and temp != self._attr_target_temperature:
                self._attr_target_temperature = temp
                updated = True

        # Update Home Assistant state if any changes occurred
        if updated:
            self.async_write_ha_state()

        self.update_control_command()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        self._attr_fan_mode = fan_mode  # always optimistic
        self.async_write_ha_state()

        self.update_control_command()