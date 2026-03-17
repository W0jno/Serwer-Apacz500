#include "widget_bridge_arduino.h"

#include <PubSubClient.h>
#include <WiFi.h>

/*
 * =========================================
 * ZMIEŃ TE WARTOŚCI POD SWOJĄ INFRASTRUKTURĘ
 * =========================================
 */
static const char *WIDGET_WIFI_SSID = "YOUR_WIFI_SSID";                // <- ZMIEŃ
static const char *WIDGET_WIFI_PASS = "YOUR_WIFI_PASSWORD";            // <- ZMIEŃ
static const char *WIDGET_DEVICE_ID = "widget_01";                     // <- ZMIEŃ
static const char *WIDGET_MQTT_HOST = "192.168.1.100";                 // <- ZMIEŃ
static const uint16_t WIDGET_MQTT_PORT = 1883;                          // <- ZMIEŃ
static const uint32_t WIDGET_STATUS_INTERVAL_MS = 5000;                 // <- ZMIEŃ (opcjonalnie)
static const char *WIDGET_ACTUATORS_JSON = "[\"led\",\"relay\"]";     // <- ZMIEŃ
static const char *WIDGET_EMITTERS_JSON = "[\"button\",\"sensor\"]";    // <- ZMIEŃ

static WiFiClient g_wifiClient;
static PubSubClient g_mqttClient(g_wifiClient);
static WidgetArduinoCommandCallback g_commandCallback = nullptr;

static unsigned long g_lastReconnectAttempt = 0;
static unsigned long g_lastStatusPublish = 0;

static String g_topicStatus;
static String g_topicSensor;
static String g_topicCommand;

static String extractJsonString(const String &payload, const char *key) {
    String pattern = String("\"") + key + "\"";
    int keyPos = payload.indexOf(pattern);
    if (keyPos < 0) {
        return "";
    }

    int colonPos = payload.indexOf(':', keyPos + pattern.length());
    if (colonPos < 0) {
        return "";
    }

    int quoteStart = payload.indexOf('"', colonPos + 1);
    if (quoteStart < 0) {
        return "";
    }

    int quoteEnd = payload.indexOf('"', quoteStart + 1);
    if (quoteEnd < 0) {
        return "";
    }

    return payload.substring(quoteStart + 1, quoteEnd);
}

static bool extractJsonBool(const String &payload, const char *key, bool &valueOut) {
    String pattern = String("\"") + key + "\"";
    int keyPos = payload.indexOf(pattern);
    if (keyPos < 0) {
        return false;
    }

    int colonPos = payload.indexOf(':', keyPos + pattern.length());
    if (colonPos < 0) {
        return false;
    }

    String tail = payload.substring(colonPos + 1);
    tail.trim();

    if (tail.startsWith("true")) {
        valueOut = true;
        return true;
    }

    if (tail.startsWith("false")) {
        valueOut = false;
        return true;
    }

    if (tail.startsWith("1")) {
        valueOut = true;
        return true;
    }

    if (tail.startsWith("0")) {
        valueOut = false;
        return true;
    }

    return false;
}

static void mqttCallback(char *topic, byte *payload, unsigned int length) {
    (void)topic;

    String rawPayload;
    rawPayload.reserve(length);
    for (unsigned int i = 0; i < length; i++) {
        rawPayload += static_cast<char>(payload[i]);
    }

    // Sprawdzamy, czy payload to na pewno komenda typu "actuator"
    String commandType = extractJsonString(rawPayload, "command");
    if (commandType != "actuator") {
        // Ignorujemy wiadomość, jeśli to nie jest komenda zmiany stanu aktuatora
        return;
    }

    // W nowym payloadzie nazwa aktuatora jest pod kluczem "name"
    String actuator = extractJsonString(rawPayload, "name");

    // W nowym payloadzie wartość logiczna jest pod kluczem "state"
    bool hasBool = false;
    bool boolValue = false;
    hasBool = extractJsonBool(rawPayload, "state", boolValue);

    if (g_commandCallback != nullptr) {
        g_commandCallback(
            actuator.c_str(),
            hasBool,
            boolValue,
            rawPayload.c_str());
    }
}

static void ensureWifiConnected() {
    if (WiFi.status() == WL_CONNECTED) {
        return;
    }

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIDGET_WIFI_SSID, WIDGET_WIFI_PASS);

    unsigned long startedAt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 15000) {
        delay(250);
    }
}

static bool ensureMqttConnected() {
    if (g_mqttClient.connected()) {
        return true;
    }

    unsigned long now = millis();
    if (now - g_lastReconnectAttempt < 3000) {
        return false;
    }
    g_lastReconnectAttempt = now;

    if (!g_mqttClient.connect(WIDGET_DEVICE_ID)) {
        return false;
    }

    return g_mqttClient.subscribe(g_topicCommand.c_str());
}

void widgetBridgeArduinoSetCommandCallback(WidgetArduinoCommandCallback callback) {
    g_commandCallback = callback;
}

void widgetBridgeArduinoInit() {
    g_topicStatus = String(WIDGET_DEVICE_ID) + "/status";
    g_topicSensor = String(WIDGET_DEVICE_ID) + "/sensor";
    g_topicCommand = String(WIDGET_DEVICE_ID) + "/command";

    g_mqttClient.setServer(WIDGET_MQTT_HOST, WIDGET_MQTT_PORT);
    g_mqttClient.setCallback(mqttCallback);

    ensureWifiConnected();
    ensureMqttConnected();
    widgetBridgeArduinoPublishStatus();
}

bool widgetBridgeArduinoPublishStatus() {
    if (!g_mqttClient.connected()) {
        return false;
    }

    String payload = "{";
    payload += "\"device_id\":\"" + String(WIDGET_DEVICE_ID) + "\",";
    payload += "\"status\":\"online\",";
    payload += "\"actuators\":" + String(WIDGET_ACTUATORS_JSON) + ",";
    payload += "\"emitters\":" + String(WIDGET_EMITTERS_JSON);
    payload += "}";

    return g_mqttClient.publish(g_topicStatus.c_str(), payload.c_str(), true);
}

bool widgetBridgeArduinoPublishSensor(const char *emitter, int sensorValue, float value) {
    if (!g_mqttClient.connected()) {
        return false;
    }

    String payload = "{";
    payload += "\"device_id\":\"" + String(WIDGET_DEVICE_ID) + "\",";
    payload += "\"emitter\":\"" + String(emitter) + "\",";
    payload += "\"sensor_value\":" + String(sensorValue) + ",";
    payload += "\"value\":" + String(value, 4);
    payload += "}";

    return g_mqttClient.publish(g_topicSensor.c_str(), payload.c_str(), false);
}

void widgetBridgeArduinoLoop() {
    ensureWifiConnected();
    ensureMqttConnected();

    if (g_mqttClient.connected()) {
        g_mqttClient.loop();

        unsigned long now = millis();
        if (now - g_lastStatusPublish >= WIDGET_STATUS_INTERVAL_MS) {
            g_lastStatusPublish = now;
            widgetBridgeArduinoPublishStatus();
        }
    }
}
