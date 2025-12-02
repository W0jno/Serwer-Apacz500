#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_system.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "button_led.h"
#include "mqtt_client.h"
#include "cJSON.h"

#define WIFI_SSID      "wifi"
#define WIFI_PASS      "1029384756"
#define WIFI_MAX_RETRY 5

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

#define DEVICE_ID      "widget_001"
#define MQTT_BROKER_URI "mqtt://192.168.0.126"

static const char *TAG = "widget_esp";
static EventGroupHandle_t s_wifi_event_group;
static int s_retry_num = 0;
static esp_mqtt_client_handle_t mqtt_client = NULL;
static char effector_value[256] = "No data received";
static bool mqtt_connected = false;
static int last_button_state = -1;  // Track last sent button state for change detection

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

        // Get WiFi signal strength (RSSI)
        wifi_ap_record_t ap_info;
        if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
            ESP_LOGI(TAG, "WiFi Signal Strength (RSSI): %d dBm", ap_info.rssi);

            // Calculate connection quality (0-100%)
            int quality;
            if (ap_info.rssi >= -50) {
                quality = 100;
            } else if (ap_info.rssi <= -100) {
                quality = 0;
            } else {
                quality = 2 * (ap_info.rssi + 100);
            }
            ESP_LOGI(TAG, "WiFi Connection Quality: %d%%", quality);
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

    // Register event handlers
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

    // Configure WiFi
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

    // Wait for connection or failure
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

// MQTT event handler
static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;
    char effector_topic[64];
    snprintf(effector_topic, sizeof(effector_topic), "%s/command", DEVICE_ID);

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "MQTT_EVENT_CONNECTED");
        mqtt_connected = true;
        // Subscribe to effector topic
        esp_mqtt_client_subscribe(mqtt_client, effector_topic, 0);
        ESP_LOGI(TAG, "Subscribed to topic: %s", effector_topic);

        // Send initial status message on connect
        {
            char status_topic[64];
            char status_message[128];
            snprintf(status_topic, sizeof(status_topic), "%s/status", DEVICE_ID);
            snprintf(status_message, sizeof(status_message), "{"
                "\"status\": true,"
                "\"charge_level\": 100,"
                "\"actuators\": \"button\","
                "\"emitters\": \"led\" "
                "}");
            esp_mqtt_client_publish(mqtt_client, status_topic, status_message, 0, 1, 0);
            ESP_LOGI(TAG, "Published initial status on connect");
        }
        break;
    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "MQTT_EVENT_DISCONNECTED - will attempt reconnection automatically");
        mqtt_connected = false;
        break;
    case MQTT_EVENT_SUBSCRIBED:
        ESP_LOGI(TAG, "MQTT_EVENT_SUBSCRIBED, msg_id=%d", event->msg_id);
        break;
    case MQTT_EVENT_DATA:
        ESP_LOGI(TAG, "MQTT_EVENT_DATA");
        ESP_LOGI(TAG, "Topic: %.*s", event->topic_len, event->topic);
        ESP_LOGI(TAG, "Data: %.*s", event->data_len, event->data);
        // Store effector value
        if (event->data_len < sizeof(effector_value)) {
            memcpy(effector_value, event->data, event->data_len);
            effector_value[event->data_len] = '\0';

            // Parse JSON and control LED if it's an effector message
            cJSON *json = cJSON_ParseWithLength(event->data, event->data_len);
            if (json != NULL) {
                cJSON *state = cJSON_GetObjectItem(json, "state");
                if (cJSON_IsBool(state)) {
                    int led_state = cJSON_IsTrue(state) ? 1 : 0;
                    button_led_set_led(led_state);
                    ESP_LOGI(TAG, "LED set to: %s", led_state ? "ON" : "OFF");
                }
                cJSON_Delete(json);
            } else {
                ESP_LOGE(TAG, "Failed to parse JSON");
            }
        }
        break;
    case MQTT_EVENT_PUBLISHED:
        /* Here we get actual confirmations from the server that
         * something got published.
         */
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
    // Initialize NVS (required for WiFi)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_LOGI(TAG, "Starting WiFi connection...");
    wifi_init_sta();

    // Start MQTT client
    mqtt_app_start();

    // Initialize GPIO for button and LED
    button_led_init();

    // Main application loop - publish status and sensor messages
    char status_topic[64];
    char sensor_topic[64];
    char message[128];
    snprintf(status_topic, sizeof(status_topic), "%s/status", DEVICE_ID);
    snprintf(sensor_topic, sizeof(sensor_topic), "%s/sensor", DEVICE_ID);

    TickType_t last_status_time = xTaskGetTickCount();
    TickType_t last_effector_print_time = xTaskGetTickCount();
    const TickType_t status_interval = pdMS_TO_TICKS(10000);  // 10 seconds
    const TickType_t effector_print_interval = pdMS_TO_TICKS(5000);  // 5 seconds

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(100));
        TickType_t current_time = xTaskGetTickCount();

        if (mqtt_connected) {
            // Publish sensor data (button state) only when it changes
            int button_state = button_led_get_state();
            if (button_state != last_button_state) {
                snprintf(message, sizeof(message), "{\"button_state\": %d}", button_state);
                esp_mqtt_client_publish(mqtt_client, sensor_topic, message, 0, 0, 0);  // QoS 0 for frequent messages
                ESP_LOGI(TAG, "Button state changed: %d -> %d", last_button_state, button_state);
                last_button_state = button_state;
            }

            // Publish status message every 10 seconds
            if ((current_time - last_status_time) >= status_interval) {
                snprintf(message, sizeof(message), "{"
                    "\"status\": true,"
                    "\"charge_level\": 100,"
                    "\"actuators\": \"button\","
                    "\"emitters\": \"led\" "
                   " }");
                int msg_id = esp_mqtt_client_publish(mqtt_client, status_topic, message, 0, 1, 0);
                ESP_LOGI(TAG, "Published to %s: %s (msg_id=%d)", status_topic, message, msg_id);
                last_status_time = current_time;
            }

            // Print effector value every 5 seconds
            if ((current_time - last_effector_print_time) >= effector_print_interval) {
                ESP_LOGI(TAG, "Effector value: %s", effector_value);
                last_effector_print_time = current_time;
            }
        } else {
            // Reset timing when reconnected to avoid burst of messages
            last_status_time = current_time;
            last_button_state = -1;  // Reset to force sending state on reconnect
        }
    }
}
