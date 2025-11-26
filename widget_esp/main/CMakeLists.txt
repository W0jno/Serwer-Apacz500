idf_component_register(SRCS "widget_esp.c" "button_led.c"
                    INCLUDE_DIRS "."
                    REQUIRES nvs_flash esp_wifi esp_netif esp_event driver mqtt json)
