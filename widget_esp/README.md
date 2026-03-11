# Widget ESP32 (gotowy firmware MQTT)

Firmware jest gotowy do wgrania i konfiguracji przez `menuconfig`.

## Konfiguracja

```bash
idf.py menuconfig
```

Sekcja: **Widget ESP32 config**
- `Widget device ID`
- `WiFi SSID`
- `WiFi password`
- `MQTT broker URI`
- `Actuators list (CSV)`
- `Emitters list (CSV)`
- `Status publish interval (ms)`

Przykładowe CSV:
- Actuators: `led,relay,buzzer,light_strip`
- Emitters: `button,gyro,motion,temp_sensor`

## Build i flash

```bash
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

## MQTT

- publish: `<device_id>/status`
- publish: `<device_id>/sensor`
- subscribe: `<device_id>/command`

## Komendy

Obsługiwane payloady:

```json
{ "state": true }
```

oraz

```json
{ "actuator": "relay", "value": true }
```


## Jak to łączy się z backendem Python?

Nie przekazujesz danych „do Pythona” bezpośrednio z C.
Ścieżka jest taka:

- ESP32 C -> MQTT publish (`<device_id>/status`, `<device_id>/sensor`)
- Backend Python -> MQTT subscribe (`+/status`, `+/sensor`)
- Backend Python -> MQTT publish komendy (`<device_id>/command`)
- ESP32 C -> MQTT subscribe komend

Czyli jedyny interfejs między C i Pythonem to kontrakt MQTT (topic + JSON).


## Jak uruchomić ESP-IDF i `menuconfig`

1. Aktywuj środowisko ESP-IDF (w terminalu, z katalogu `esp-idf`):

```bash
source ./export.sh
```

2. Przejdź do projektu widgeta:

```bash
cd /workspace/Serwer-Apacz500/widget_esp
```

3. Uruchom konfigurację:

```bash
idf.py set-target esp32
idf.py menuconfig
```

4. Zapisane ustawienia trafią do `widget_esp/sdkconfig`.


## PlatformIO (jeżeli zespół pracuje w PlatformIO)

Dla zgodności z tym firmware użyj frameworku `espidf`:

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = espidf
```

Komendy:

```bash
pio run -t menuconfig
pio run
pio run -t upload
pio device monitor
```


## PlatformIO - co przenieść do własnego projektu zespołu

Jeżeli firmware rozwijany jest w osobnym projekcie PlatformIO, przenieś minimum:

1. `widget_esp/main/Kconfig.projbuild` -> `<twoj_projekt>/main/Kconfig.projbuild`
2. W kodzie zespołu dodaj `#include "sdkconfig.h"` i użyj `CONFIG_WIDGET_*`.
3. Uruchom:

```bash
pio run -t menuconfig
pio run
pio run -t upload
pio device monitor
```

Szczegółowy opis krok po kroku jest w `docs/widget_integration.md` (sekcja 4B).
