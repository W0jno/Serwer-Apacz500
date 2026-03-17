# Widget Arduino Drop-in (PlatformIO + Arduino framework)

Ten folder jest dla zespołów, które mają własną logikę widgeta i używają **PlatformIO + Arduino framework**.

Cel: dodać tylko warstwę Wi‑Fi/MQTT do istniejącego kodu, bez przepisywania logiki urządzenia.

## 1) Co zawiera folder

- `widget_bridge_arduino.h`
- `widget_bridge_arduino.cpp`

Moduł realizuje:
- połączenie Wi‑Fi,
- połączenie z MQTT brokerem,
- publikację `<device_id>/status`,
- publikację `<device_id>/sensor`,
- subskrypcję `<device_id>/command`.

## 2) Krok po kroku: integracja w projekcie PlatformIO

### Krok 1 — skopiuj pliki do projektu programisty

Skopiuj:
- `widget_arduino_dropin/widget_bridge_arduino.h` -> `include/widget_bridge_arduino.h`
- `widget_arduino_dropin/widget_bridge_arduino.cpp` -> `src/widget_bridge_arduino.cpp`

### Krok 2 — dodaj bibliotekę MQTT do `platformio.ini`

W `platformio.ini` dopisz:

```ini
lib_deps =
  knolleary/PubSubClient
```

### Krok 3 — ustaw dane połączenia (hardcoded)

W `src/widget_bridge_arduino.cpp` na początku pliku zmień wartości oznaczone komentarzem `// <- ZMIEŃ`:

- `WIDGET_WIFI_SSID`
- `WIDGET_WIFI_PASS`
- `WIDGET_DEVICE_ID`
- `WIDGET_MQTT_HOST`
- `WIDGET_MQTT_PORT`
- `WIDGET_ACTUATORS_JSON`
- `WIDGET_EMITTERS_JSON`
- `WIDGET_STATUS_INTERVAL_MS` (opcjonalnie)

### Krok 4 — podepnij moduł w `src/main.cpp`

```cpp
#include <Arduino.h>
#include "widget_bridge_arduino.h"

static void onCommand(const char *actuator, bool hasBool, bool boolValue, const char *rawPayload) {
  // Tu mapujesz komendy na Waszą logikę sprzętową.
  // Przykład: if (strcmp(actuator, "relay") == 0 && hasBool) digitalWrite(RELAY_PIN, boolValue ? HIGH : LOW);
}

void setup() {
  widgetBridgeArduinoSetCommandCallback(onCommand);
  widgetBridgeArduinoInit();
}

void loop() {
  widgetBridgeArduinoLoop();

  // Tu zostaje Wasza logika widgeta.
  // Przykład zdarzenia sensora:
  // widgetBridgeArduinoPublishSensor("button", 1, 1.0f);
}
```

### Krok 5 — publikuj sensory z Waszego kodu

Przykłady:

```cpp
widgetBridgeArduinoPublishSensor("button", 1, 1.0f); // aktywacja
widgetBridgeArduinoPublishSensor("button", 0, 0.0f); // dezaktywacja
widgetBridgeArduinoPublishSensor("gyro", 1, 0.73f);  // wartość float
```

## 3) Build i upload

```bash
pio run
pio run -t upload
pio device monitor
```

## 4) Co ten moduł **nie** robi

- Nie usuwa Waszej logiki biznesowej.
- Nie nadpisuje plików innych zespołów w repo.
- Nie wymaga `menuconfig`.

To tylko warstwa komunikacji z serwerem MQTT.
