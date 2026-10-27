import esphome.codegen as cg
import esphome.config_validation as cv
import esphome.final_validate as fv
from esphome import pins
from esphome.components import sensor

AUTO_LOAD = ["sensor"]
DEPENDENCIES = ["i2c"]

dts_ns = cg.esphome_ns.namespace("dts6012m")
DTS = dts_ns.class_("DTS6012MComponent", cg.PollingComponent)

CONFIG_SCHEMA = cv.All(
    cv.only_on_esp32,
    cv.only_with_arduino,
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(DTS),
            cv.Optional("update_interval", default="0.5s"): cv.positive_time_period_milliseconds,
            cv.Optional("retries", default=3): cv.int_range(min=1, max=10),
            cv.Optional("wakeup_time", default="20ms"): cv.positive_time_period_milliseconds,
            cv.Optional("powerup_time", default="250ms"): cv.positive_time_period_milliseconds,
            cv.Optional("sleep_between_updates", default=True): cv.boolean,
            cv.Optional("power_pin"): pins.gpio_output_pin_schema,
            cv.Required("distance"): sensor.sensor_schema(
                unit_of_measurement="m",
                accuracy_decimals=3,
                device_class="distance",
                state_class="measurement",
            ),
        }
    ),
)


def _validate_single_bus(config):
    if len(fv.full_config.get().get("i2c", [])) != 1:
        raise cv.Invalid("DTS6012M requires exactly one I2C bus (the global Arduino Wire bus)")
    return config


FINAL_VALIDATE_SCHEMA = _validate_single_bus


async def to_code(config):
    var = cg.new_Pvariable(
        config[cv.GenerateID()],
        config["update_interval"],
        config["retries"],
        config["wakeup_time"],
        config["powerup_time"],
        config["sleep_between_updates"],
    )

    await cg.register_component(var, config)
    sens = await sensor.new_sensor(config["distance"])
    cg.add(var.set_distance_sensor(sens))
    if "power_pin" in config:
        pin = await cg.gpio_pin_expression(config["power_pin"])
        cg.add(var.set_power_pin(pin))
