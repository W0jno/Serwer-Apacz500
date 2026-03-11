#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"

#include "esp_event.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "mqtt_client.h"
#include "nvs_flash.h"

#include "cJSON.h"
#include "widget_bridge.h"

/*
 * =============================
 *  ZMIEŃ TE WARTOŚCI (HARD CODED)
 * =============================
 */
#define WIDGET_WIFI_SSID            "CHANGE_ME_WIFI_SSID"         // <- ZMIEŃ
#define WIDGET_WIFI_PASS            "CHANGE_ME_WIFI_PASSWORD"     // <- ZMIEŃ
#define WIDGET_DEVICE_ID            "CHANGE_ME_WIDGET_ID"         // <- ZMIEŃ
#define WIDGET_MQTT_BROKER_URI      "mqtt://192.168.0.126"        // <- ZMIEŃ (IP serwera)
#define WIDGET_ACTUATORS_JSON       "[\"led\"]"                  // <- ZMIEŃ (np. ["relay","buzzer"])
#define WIDGET_EMITTERS_JSON        "[\"button\"]"               // <- ZMIEŃ (np. ["gyro","button"])
#define WIDGET_STATUS_INTERVAL_MS   10000                          // <- ZMIEŃ, jeśli trzeba

#define WIFI_MAX_RETRY 5
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT BIT1

static const char *TAG = "widget_bridge";

static EventGroupHandle_t s_wifi_event_group;
static int s_retry_num = 0;
static bool s_mqtt_connected = false;
static int64_t s_last_status_publish_ms = 0;

static esp_mqtt_client_handle_t s_mqtt_client = NULL;
static widget_command_callback_t s_command_callback = NULL;

static void publish_status(bool online);

static void wifi_event_handler(void *arg, esp_event_base_t event_base, int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
        ESP_LOGI(TAG, "WiFi started, connecting...");
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < WIFI_MAX_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGW(TAG, "WiFi reconnect attempt %d/%d", s_retry_num, WIFI_MAX_RETRY);
        } else {
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
            ESP_LOGE(TAG, "WiFi connection failed");
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
        ESP_LOGI(TAG, "WiFi connected (IP acquired)");
    }
}

static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;

    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &instance_got_ip));

    wifi_config_t wifi_config = {
        .sta = {
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
            .pmf_cfg = {
                .capable = true,
                .required = false,
            },
        },
    };

    snprintf((char *)wifi_config.sta.ssid, sizeof(wifi_config.sta.ssid), "%s", WIDGET_WIFI_SSID);
    snprintf((char *)wifi_config.sta.password, sizeof(wifi_config.sta.password), "%s", WIDGET_WIFI_PASS);

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    EventBits_t bits = xEventGroupWaitBits(
        s_wifi_event_group,
        WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
        pdFALSE,
        pdFALSE,
        portMAX_DELAY
    );

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "Connected to WiFi SSID: %s", WIDGET_WIFI_SSID);
    } else {
        ESP_LOGE(TAG, "Could not connect to WiFi SSID: %s", WIDGET_WIFI_SSID);
    }
}

static void handle_command_payload(const char *payload, int payload_len)
{
    cJSON *json = cJSON_ParseWithLength(payload, payload_len);
    if (json == NULL) {
        ESP_LOGE(TAG, "Invalid command JSON");
        return;
    }

    const char *actuator_name = "state";
    bool has_bool = false;
    bool bool_value = false;

    cJSON *actuator = cJSON_GetObjectItem(json, "actuator");
    if (cJSON_IsString(actuator) && actuator->valuestring != NULL) {
        actuator_name = actuator->valuestring;
    }

    cJSON *value = cJSON_GetObjectItem(json, "value");
    cJSON *state = cJSON_GetObjectItem(json, "state");

    if (cJSON_IsBool(value)) {
        has_bool = true;
        bool_value = cJSON_IsTrue(value);
    } else if (cJSON_IsBool(state)) {
        has_bool = true;
        bool_value = cJSON_IsTrue(state);
    }

    if (s_command_callback != NULL) {
        s_command_callback(actuator_name, has_bool, bool_value, payload);
    }

    cJSON_Delete(json);
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;

    char command_topic[80];
    snprintf(command_topic, sizeof(command_topic), "%s/command", WIDGET_DEVICE_ID);

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "MQTT connected");
        s_mqtt_connected = true;
        esp_mqtt_client_subscribe(s_mqtt_client, command_topic, 0);
        publish_status(true);
        break;
    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "MQTT disconnected");
        s_mqtt_connected = false;
        break;
    case MQTT_EVENT_DATA:
        if (event->data_len > 0 && event->data_len < 512) {
            char payload[512];
            memcpy(payload, event->data, event->data_len);
            payload[event->data_len] = '\0';
            ESP_LOGI(TAG, "MQTT command: %s", payload);
            handle_command_payload(payload, event->data_len);
        }
        break;
    default:
        break;
    }
}

static void mqtt_start(void)
{
    const esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = WIDGET_MQTT_BROKER_URI,
        .credentials.client_id = WIDGET_DEVICE_ID,
        .session.keepalive = 30,
    };

    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(s_mqtt_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(s_mqtt_client);
}

static void publish_status(bool online)
{
    if (!s_mqtt_connected || s_mqtt_client == NULL) {
        return;
    }

    char topic[80];
    snprintf(topic, sizeof(topic), "%s/status", WIDGET_DEVICE_ID);

    cJSON *root = cJSON_CreateObject();
    cJSON_AddBoolToObject(root, "status", online);
    cJSON_AddNumberToObject(root, "charge_level", 100);

    cJSON *actuators = cJSON_Parse(WIDGET_ACTUATORS_JSON);
    cJSON *emitters = cJSON_Parse(WIDGET_EMITTERS_JSON);

    if (actuators == NULL || emitters == NULL || !cJSON_IsArray(actuators) || !cJSON_IsArray(emitters)) {
        ESP_LOGE(TAG, "Invalid WIDGET_ACTUATORS_JSON or WIDGET_EMITTERS_JSON");
        cJSON_Delete(actuators);
        cJSON_Delete(emitters);
        cJSON_Delete(root);
        return;
    }

    cJSON_AddItemToObject(root, "actuators", actuators);
    cJSON_AddItemToObject(root, "emitters", emitters);

    char *payload = cJSON_PrintUnformatted(root);
    if (payload != NULL) {
        esp_mqtt_client_publish(s_mqtt_client, topic, payload, 0, 1, 1);
        cJSON_free(payload);
    }

    cJSON_Delete(root);
}

void widget_bridge_set_command_callback(widget_command_callback_t callback)
{
    s_command_callback = callback;
}

void widget_bridge_publish_sensor(const char *emitter, int sensor_value, double value)
{
    if (!s_mqtt_connected || s_mqtt_client == NULL || emitter == NULL) {
        return;
    }

    char topic[80];
    char payload[256];

    snprintf(topic, sizeof(topic), "%s/sensor", WIDGET_DEVICE_ID);
    snprintf(payload, sizeof(payload), "{\"emitter\":\"%s\",\"sensor_value\":%d,\"value\":%.3f}", emitter, sensor_value, value);

    esp_mqtt_client_publish(s_mqtt_client, topic, payload, 0, 0, 0);
}

void widget_bridge_init(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    wifi_init_sta();
    mqtt_start();
    s_last_status_publish_ms = esp_timer_get_time() / 1000;
}

void widget_bridge_process(void)
{
    if (!s_mqtt_connected) {
        return;
    }

    int64_t now_ms = esp_timer_get_time() / 1000;
    if ((now_ms - s_last_status_publish_ms) >= WIDGET_STATUS_INTERVAL_MS) {
        publish_status(true);
        s_last_status_publish_ms = now_ms;
    }
}
