# Widget Drop-in (hardcoded config, bez `menuconfig`)

Ten folder zawiera gotowy moduł C do podłączenia istniejącego firmware zespołu do serwera MQTT.

Cel: **nie przepisywać całej logiki widgeta**, tylko dołożyć komunikację z serwerem.

## Co zawiera folder

- `widget_bridge.c` — obsługa Wi‑Fi, MQTT, publish/subscribe
- `widget_bridge.h` — API do użycia w projekcie zespołu

---

## 1) Co programista ma zmienić (obowiązkowo)

W pliku `widget_bridge.c`, na początku, jest sekcja:

```c
/*
 * =============================
 *  ZMIEŃ TE WARTOŚCI (HARD CODED)
 * =============================
 */
```

Należy ustawić:
- `WIDGET_WIFI_SSID`
- `WIDGET_WIFI_PASS`
- `WIDGET_DEVICE_ID`
- `WIDGET_MQTT_BROKER_URI` (adres LAN serwera, np. `mqtt://192.168.0.126`)
- opcjonalnie: `WIDGET_ACTUATORS_JSON`, `WIDGET_EMITTERS_JSON`, `WIDGET_STATUS_INTERVAL_MS`

---

## 2) Jak dodać moduł do istniejącego projektu (PlatformIO)

### 2.1 Skopiuj pliki

Skopiuj do projektu programisty:

- `widget_dropin/widget_bridge.c` -> `<twoj_projekt>/src/widget_bridge.c`
- `widget_dropin/widget_bridge.h` -> `<twoj_projekt>/include/widget_bridge.h`

### 2.2 Zainicjalizuj moduł w `app_main`

W swoim `app_main` dodaj:

```c
#include "widget_bridge.h"

void app_main(void)
{
    widget_bridge_init();

    while (1) {
        widget_bridge_process();

        // Tu zostaje Wasza logika biznesowa widgeta
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
```

### 2.3 Podepnij odbiór komend z serwera

Zarejestruj callback:

```c
static void on_command(const char *actuator, bool has_bool, bool bool_value, const char *raw_payload)
{
    // Tu mapujesz actuator na swoją logikę (relay, led, buzzer, ...)
    // np. if (strcmp(actuator, "relay") == 0 && has_bool) { ... }
}

void app_main(void)
{
    widget_bridge_set_command_callback(on_command);
    widget_bridge_init();
    ...
}
```

### 2.4 Publikuj dane emitera z Waszej logiki

Gdy w Twoim kodzie wykryjesz zdarzenie sensora:

```c
widget_bridge_publish_sensor("button", 0, 1.0); // aktywacja
widget_bridge_publish_sensor("button", 1, 0.0); // dezaktywacja
```

Dla floatów (np. gyro):

```c
widget_bridge_publish_sensor("gyro", 0, gyro_value);
```

---

## 3) Build i wgranie (PlatformIO)

```bash
pio run
pio run -t upload
pio device monitor
```

---

## 4) Ważna informacja o "nie usuwaniu logiki"

Ten moduł jest dodatkiem — **nie zastępuje** logiki biznesowej zespołu.
Programista włącza go do swojego projektu i wywołuje API (`init/process/publish/callback`).

Na urządzeniu ESP zawsze działa firmware, który zostanie ostatnio wgrany przez `upload`.
