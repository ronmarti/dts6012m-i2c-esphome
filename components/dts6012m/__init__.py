import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor

AUTO_LOAD = ["sensor"]

dts_ns = cg.esphome_ns.namespace("dts6012m")
DTS = dts_ns.class_("DTS6012MComponent", cg.PollingComponent)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(DTS),
        cv.Optional("update_interval",
                    description="Interval at which the sensor polls the I²C sensor, e.g., '500ms', '1s', '5min'",
                    default="0.5s"): cv.positive_time_period_milliseconds,
        cv.Optional("retries",
                    description="Number of retries after a failed I²C read",
                    default=3): cv.int_,
        cv.Required("distance",
                    description="Sensor that will publish the measured distance in meters"): sensor.sensor_schema(
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
        config["retries"]
    )

    await cg.register_component(var, config)
    sens = await sensor.new_sensor(config["distance"])
    cg.add(var.set_distance_sensor(sens))
