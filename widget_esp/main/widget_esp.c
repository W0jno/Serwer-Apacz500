#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "cJSON.h"

#include "button_led.h"
#include "sdkconfig.h"

#define WIFI_MAX_RETRY 5

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

#define DEVICE_ID CONFIG_WIDGET_DEVICE_ID
#define WIFI_SSID CONFIG_WIDGET_WIFI_SSID
#define WIFI_PASS CONFIG_WIDGET_WIFI_PASS
#define MQTT_BROKER_URI CONFIG_WIDGET_MQTT_BROKER_URI

static const char *TAG = "widget_esp";
static EventGroupHandle_t s_wifi_event_group;
static int s_retry_num = 0;
static esp_mqtt_client_handle_t mqtt_client = NULL;
static char last_command_payload[256] = "No command received";
static bool mqtt_connected = false;
static int last_button_state = -1;

static cJSON *csv_to_json_array(const char *csv)
{
    cJSON *arr = cJSON_CreateArray();
    if (arr == NULL) {
        return NULL;
    }

    char *copy = strdup(csv);
    if (copy == NULL) {
        cJSON_Delete(arr);
        return NULL;
    }

    char *token = strtok(copy, ",");
    while (token != NULL) {
        while (*token == ' ') {
            token++;
        }

        size_t len = strlen(token);
        while (len > 0 && (token[len - 1] == ' ' || token[len - 1] == '\n' || token[len - 1] == '\r' || token[len - 1] == '\t')) {
            token[len - 1] = '\0';
            len--;
        }

        if (len > 0) {
            cJSON_AddItemToArray(arr, cJSON_CreateString(token));
        }

        token = strtok(NULL, ",");
    }

    free(copy);
    return arr;
}

static void publish_status(bool online)
{
    if (mqtt_client == NULL) {
        return;
    }

    char topic[64];
    snprintf(topic, sizeof(topic), "%s/status", DEVICE_ID);

    cJSON *root = cJSON_CreateObject();
    if (root == NULL) {
        ESP_LOGE(TAG, "Failed to create JSON for status");
        return;
    }

    cJSON_AddBoolToObject(root, "status", online);
    cJSON_AddNumberToObject(root, "charge_level", 100);

    cJSON *actuators = csv_to_json_array(CONFIG_WIDGET_ACTUATORS_CSV);
    cJSON *emitters = csv_to_json_array(CONFIG_WIDGET_EMITTERS_CSV);

    if (actuators == NULL || emitters == NULL) {
        ESP_LOGE(TAG, "Failed to build actuators/emitters arrays");
        cJSON_Delete(actuators);
        cJSON_Delete(emitters);
        cJSON_Delete(root);
        return;
    }

    cJSON_AddItemToObject(root, "actuators", actuators);
    cJSON_AddItemToObject(root, "emitters", emitters);

    char *payload = cJSON_PrintUnformatted(root);
    if (payload == NULL) {
        ESP_LOGE(TAG, "Failed to serialize status JSON");
        cJSON_Delete(root);
        return;
    }

    int msg_id = esp_mqtt_client_publish(mqtt_client, topic, payload, 0, 1, 1);
    ESP_LOGI(TAG, "Published status to %s (msg_id=%d): %s", topic, msg_id, payload);

    cJSON_free(payload);
    cJSON_Delete(root);
}

// WiFi event handler
static void event_handler(void* arg, esp_event_base_t event_base,
                          int32_t event_id, void* event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
        ESP_LOGI(TAG, "WiFi started, connecting...");
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < WIFI_MAX_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGI(TAG, "Retry connecting to WiFi... (attempt %d/%d)", s_retry_num, WIFI_MAX_RETRY);
        } else {
            xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
            ESP_LOGE(TAG, "Failed to connect to WiFi after %d attempts", WIFI_MAX_RETRY);
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Got IP address: " IPSTR, IP2STR(&event->ip_info.ip));
        s_retry_num = 0;

        wifi_ap_record_t ap_info;
        if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
            ESP_LOGI(TAG, "WiFi Signal Strength (RSSI): %d dBm", ap_info.rssi);
        } else {
            ESP_LOGW(TAG, "Failed to get WiFi AP info");
        }

        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

// Initialize WiFi in station mode
void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &event_handler,
                                                        NULL,
                                                        &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &event_handler,
                                                        NULL,
                                                        &instance_got_ip));

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASS,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
            .pmf_cfg = {
                .capable = true,
                .required = false
            },
        },
    };

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "WiFi initialization finished.");

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group,
            WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
            pdFALSE,
            pdFALSE,
            portMAX_DELAY);

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "Connected to WiFi SSID: %s", WIFI_SSID);
    } else if (bits & WIFI_FAIL_BIT) {
        ESP_LOGE(TAG, "Failed to connect to WiFi SSID: %s", WIFI_SSID);
    } else {
        ESP_LOGE(TAG, "Unexpected event");
    }
}

static void handle_command(cJSON *json)
{
    cJSON *state = cJSON_GetObjectItem(json, "state");
    if (cJSON_IsBool(state)) {
        int led_state = cJSON_IsTrue(state) ? 1 : 0;
        button_led_set_led(led_state);
        ESP_LOGI(TAG, "Backward-compatible state command -> LED: %s", led_state ? "ON" : "OFF");
    }

    cJSON *actuator = cJSON_GetObjectItem(json, "actuator");
    cJSON *value = cJSON_GetObjectItem(json, "value");

    if (cJSON_IsString(actuator) && value != NULL) {
        ESP_LOGI(TAG, "Generic command actuator=%s", actuator->valuestring);

        if (strcmp(actuator->valuestring, "led") == 0) {
            if (cJSON_IsBool(value)) {
                button_led_set_led(cJSON_IsTrue(value) ? 1 : 0);
            } else if (cJSON_IsNumber(value)) {
                button_led_set_led(value->valueint ? 1 : 0);
            }
        }
    }
}

// MQTT event handler
static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;
    char command_topic[64];
    snprintf(command_topic, sizeof(command_topic), "%s/command", DEVICE_ID);

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "MQTT_EVENT_CONNECTED");
        mqtt_connected = true;
        esp_mqtt_client_subscribe(mqtt_client, command_topic, 0);
        ESP_LOGI(TAG, "Subscribed to topic: %s", command_topic);
        publish_status(true);
        break;
    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "MQTT_EVENT_DISCONNECTED - will attempt reconnection automatically");
        mqtt_connected = false;
        break;
    case MQTT_EVENT_SUBSCRIBED:
        ESP_LOGI(TAG, "MQTT_EVENT_SUBSCRIBED, msg_id=%d", event->msg_id);
        break;
    case MQTT_EVENT_DATA:
        ESP_LOGI(TAG, "MQTT_EVENT_DATA topic=%.*s data=%.*s", event->topic_len, event->topic, event->data_len, event->data);

        if (event->data_len < sizeof(last_command_payload)) {
            memcpy(last_command_payload, event->data, event->data_len);
            last_command_payload[event->data_len] = '\0';

            cJSON *json = cJSON_ParseWithLength(event->data, event->data_len);
            if (json != NULL) {
                handle_command(json);
                cJSON_Delete(json);
            } else {
                ESP_LOGE(TAG, "Failed to parse JSON command");
            }
        }
        break;
    case MQTT_EVENT_PUBLISHED:
        ESP_LOGI(TAG, "MQTT_EVENT_PUBLISHED, msg_id=%d", event->msg_id);
        break;
    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "MQTT_EVENT_ERROR");
        if (event->error_handle->error_type == MQTT_ERROR_TYPE_TCP_TRANSPORT) {
            ESP_LOGE(TAG, "Last error code reported from esp-tls: 0x%x", event->error_handle->esp_tls_last_esp_err);
            ESP_LOGE(TAG, "Last tls stack error number: 0x%x", event->error_handle->esp_tls_stack_err);
            ESP_LOGE(TAG, "Last captured errno : %d (%s)", event->error_handle->esp_transport_sock_errno,
                     strerror(event->error_handle->esp_transport_sock_errno));
        } else if (event->error_handle->error_type == MQTT_ERROR_TYPE_CONNECTION_REFUSED) {
            ESP_LOGE(TAG, "Connection refused error: 0x%x", event->error_handle->connect_return_code);
        }
        break;
    default:
        break;
    }
}

// Initialize and start MQTT client
static void mqtt_app_start(void)
{
    const esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = MQTT_BROKER_URI,
        .credentials.client_id = DEVICE_ID,
        .session.keepalive = 30,
        .network.timeout_ms = 10000,
        .buffer.size = 1024,
        .buffer.out_size = 1024,
    };

    mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(mqtt_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(mqtt_client);

    ESP_LOGI(TAG, "MQTT client started");
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_LOGI(TAG, "Starting WiFi connection...");
    wifi_init_sta();

    mqtt_app_start();
    button_led_init();

    char sensor_topic[64];
    char message[160];
    snprintf(sensor_topic, sizeof(sensor_topic), "%s/sensor", DEVICE_ID);

    TickType_t last_status_time = xTaskGetTickCount();
    TickType_t last_command_print_time = xTaskGetTickCount();
    const TickType_t status_interval = pdMS_TO_TICKS(CONFIG_WIDGET_STATUS_INTERVAL_MS);
    const TickType_t command_print_interval = pdMS_TO_TICKS(5000);

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(100));
        TickType_t current_time = xTaskGetTickCount();

        if (mqtt_connected) {
            int button_state = button_led_get_state();
            if (button_state != last_button_state) {
                snprintf(
                    message,
                    sizeof(message),
                    "{\"emitter\":\"button\",\"sensor_value\":%d,\"value\":%d}",
                    button_state,
                    button_state
                );
                esp_mqtt_client_publish(mqtt_client, sensor_topic, message, 0, 0, 0);
                ESP_LOGI(TAG, "Button state changed: %d -> %d", last_button_state, button_state);
                last_button_state = button_state;
            }

            if ((current_time - last_status_time) >= status_interval) {
                publish_status(true);
                last_status_time = current_time;
            }

            if ((current_time - last_command_print_time) >= command_print_interval) {
                ESP_LOGI(TAG, "Last command payload: %s", last_command_payload);
                last_command_print_time = current_time;
            }
        } else {
            last_status_time = current_time;
            last_button_state = -1;
        }
    }
}
