# DeLonghi PAC N81 AC IR Integration for Home Assistant

Probably other similar ACs too.

Quick and dirty adaptation of https://github.com/Astro1247/osaka_integration.

IR commands are sent through MQTT in a format that Tuya IR blasters (for example Tuya ZS06) can parse.

## Setup

Declare your climate entity inside Home Assistant `configuration.yaml` file as follows:

```yaml
climate:
  - platform: n81_ac
    name: N81 AC
    unique_id: "n81_ac"
    # Set your IR blasters mqtt topic
    mqtt_topic_name: "zigbee2mqtt/IR Control/set/ir_code_to_send"
```

## Resources used

* https://gist.github.com/mildsunrise/1d576669b63a260d2cff35fda63ec0b5
* https://github.com/zeroflow/ESPAircon
* https://github.com/lukasgabriel/DL_smart_aircon
* https://github.com/Astro1247/osaka_integration/tree/main