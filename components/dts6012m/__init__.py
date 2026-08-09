import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.components import sensor

AUTO_LOAD = ["sensor"]

dts_ns = cg.esphome_ns.namespace("dts6012m")
DTS = dts_ns.class_("DTS6012MComponent", cg.PollingComponent)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(DTS),
        cv.Optional("update_interval",
                    default="0.5s"): cv.positive_time_period_milliseconds,
        cv.Optional("retries",
                    default=3): cv.int_,
        cv.Optional("wakeup_time",
                    default="20ms"): cv.positive_time_period_milliseconds,
        cv.Optional("powerup_time",
                default="250ms"): cv.positive_time_period_milliseconds,
        cv.Optional("sleep_between_updates",
                default=False): cv.boolean,
        cv.Optional("power_pin"): pins.gpio_output_pin_schema,
        cv.Required("distance"): sensor.sensor_schema(
                        unit_of_measurement="m",
                        accuracy_decimals=3,
                        device_class="distance",
                        state_class="measurement",
                    ),
    }
)

async def to_code(config):
    var = cg.new_Pvariable(
        config[cv.GenerateID()],
        config["update_interval"],
        config["retries"],
        config["wakeup_time"],
        config["powerup_time"],
        config["sleep_between_updates"]
    )

    await cg.register_component(var, config)
    sens = await sensor.new_sensor(config["distance"])
    cg.add(var.set_distance_sensor(sens))
    if "power_pin" in config:
        pin = await cg.gpio_pin_expression(config["power_pin"])
        cg.add(var.set_power_pin(pin))
