SENSORS = {
    "cputemp": {
        "name": "CPU Temperature",
        "unit_of_measurement": "°C",
        "device_class": "temperature",
        "platform": "sensor",
        "entity_category": "diagnostic",
        "value_template": '{{ value_json.cputemp }}',
    },
    "reboot": {
        "name": "Reboot",
        "device_class": "restart",
        "entity_category": "diagnostic",
        "platform": "button",
        "payload_press": '{"command": "reboot"}'
    },
    "restart": {
        "name": "Reload page",
        "device_class": "restart",
        "entity_category": "diagnostic",
        "platform": "button",
        "payload_press": '{"command": "reload"}'
    },
    "brightness": {
        "name": "Screen brightness",
        "icon": "mdi:brightness-7",
        "command_template": '{"command": "set_brightness", "arg": {{ value }} }',
        "value_template": '{{ value_json.brightness }}',
        "min": 0,
        "max": 100,
        "unit_of_measurement": "%",
        "platform": "number"
    }
}
