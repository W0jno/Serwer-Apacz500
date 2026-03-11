#pragma once

#include <Arduino.h>

typedef void (*WidgetArduinoCommandCallback)(
    const char *actuator,
    bool hasBool,
    bool boolValue,
    const char *rawPayload);

void widgetBridgeArduinoSetCommandCallback(WidgetArduinoCommandCallback callback);

void widgetBridgeArduinoInit();
void widgetBridgeArduinoLoop();

bool widgetBridgeArduinoPublishStatus();
bool widgetBridgeArduinoPublishSensor(const char *emitter, int sensorValue, float value);
