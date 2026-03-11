#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Callback called when command is received on <device_id>/command.
 *
 * @param actuator     Actuator name from payload (or "state" for legacy state-only command)
 * @param has_bool     True when payload contains boolean value that can be applied directly
 * @param bool_value   Parsed boolean value (valid only when has_bool=true)
 * @param raw_payload  Original JSON payload as string
 */
typedef void (*widget_command_callback_t)(
    const char *actuator,
    bool has_bool,
    bool bool_value,
    const char *raw_payload
);

/** Initialize Wi-Fi + MQTT connectivity for widget. */
void widget_bridge_init(void);

/**
 * Periodic processing. Call in your app loop.
 * Publishes status heartbeat.
 */
void widget_bridge_process(void);

/**
 * Publish sensor event to <device_id>/sensor.
 * Example emitter: "button", "gyro", "temp_sensor".
 */
void widget_bridge_publish_sensor(const char *emitter, int sensor_value, double value);

/** Register command callback used by your business logic. */
void widget_bridge_set_command_callback(widget_command_callback_t callback);

#ifdef __cplusplus
}
#endif
