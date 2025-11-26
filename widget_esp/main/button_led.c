#include "button_led.h"
#include "driver/gpio.h"
#include "esp_log.h"

#define BOOT_GPIO      GPIO_NUM_0
#define LED_GPIO       GPIO_NUM_2

static const char *TAG = "button_led";

void button_led_init(void)
{
    // Configure GPIO 0 (BOOT button) as input with pull-up
    gpio_config_t io_conf_input = {
        .pin_bit_mask = (1ULL << BOOT_GPIO),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config(&io_conf_input);
    
    // Configure GPIO 2 (LED) as output
    gpio_config_t io_conf_output = {
        .pin_bit_mask = (1ULL << LED_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config(&io_conf_output);
    gpio_set_level(LED_GPIO, 0);  // LED off initially
    
    ESP_LOGI(TAG, "GPIO configured: Button (GPIO%d), LED (GPIO%d)", BOOT_GPIO, LED_GPIO);
}

int button_led_get_state(void)
{
    return gpio_get_level(BOOT_GPIO);
}

void button_led_set_led(int state)
{
    gpio_set_level(LED_GPIO, state);
}