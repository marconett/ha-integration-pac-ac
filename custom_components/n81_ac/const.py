"""Constants for n81 integration."""

from typing import Final

from homeassistant.const import Platform

DEFAULT_NAME = "N81 AC"
DEFAULT_MQTT_TOPIC: Final = "zigbee2mqtt/IR Control/set/ir_code_to_send"
DOMAIN = "n81_ac"
PLATFORMS: Final = [Platform.CLIMATE]