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
