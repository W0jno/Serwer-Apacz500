#ifndef BUTTON_LED_H
#define BUTTON_LED_H

/**
 * @brief Initialize GPIO pins for button and LED
 * 
 * Configures GPIO 0 (BOOT button) as input with pull-up
 * and GPIO 2 (LED) as output.
 */
void button_led_init(void);

/**
 * @brief Get current button state
 * 
 * @return int Current button state (0 = pressed, 1 = released)
 */
int button_led_get_state(void);

/**
 * @brief Set LED state
 * 
 * @param state LED state (0 = off, 1 = on)
 */
void button_led_set_led(int state);

#endif // BUTTON_LED_H