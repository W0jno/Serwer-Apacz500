# Integracja widgeta ESP32 z serwerem MQTT

Ten projekt ma gotowy firmware dla ESP32: `widget_esp/`.

## TL;DR

1. `cd widget_esp`
2. `idf.py menuconfig`
3. Ustaw `device_id`, Wi‑Fi, broker MQTT oraz **listy aktywatorów/emiterów**.
4. `idf.py build && idf.py -p /dev/ttyUSB0 flash monitor`

Po tym firmware działa bez ręcznej edycji C.

## 1) Konfiguracja (menuconfig)

Uruchom:

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

Przykład:
- `Actuators list (CSV)`: `led,light_strip,buzzer,relay`
- `Emitters list (CSV)`: `button,gyro,temp_sensor,motion`

Firmware publikuje te listy do backendu w `status` jako tablice JSON.

## 2) Build i flash

```bash
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

## 3) Kontrakt MQTT

### Status (ESP32 -> serwer)
Topic: `<device_id>/status`

```json
{
  "status": true,
  "charge_level": 100,
  "actuators": ["led", "light_strip", "relay"],
  "emitters": ["button", "gyro", "motion"]
}
```

### Sensor (ESP32 -> serwer)
Topic: `<device_id>/sensor`

Przykładowy payload wysyłany przez firmware:

```json
{
  "emitter": "button",
  "sensor_value": 0,
  "value": 0
}
```

- `sensor_value` zostaje dla kompatybilności wstecznej.
- Backend interpretuje teraz także `value` i różne typy danych (bool/int/float/string) do stanu aktywny/nieaktywny.

### Command (serwer -> ESP32)
Topic: `<device_id>/command`

Obsługiwane są dwa formaty:

1) Kompatybilny wstecz:

```json
{ "state": true }
```

2) Ogólny (dla dowolnych aktywatorów):

```json
{ "actuator": "light_strip", "value": true }
```

Firmware:
- loguje wszystkie komendy generyczne,
- ma przykład wykonania dla `actuator=led` (sterowanie diodą),
- dla innych aktywatorów należy dodać obsługę sprzętową w firmware (switch po nazwie aktywatora).


## 3A) Jak dane z C (ESP32) trafiają do Pythona?

**Nie przekazujesz danych bezpośrednio z C do kodu Python.**
Warstwa pośrednia to MQTT:

1. Firmware C na ESP32 publikuje JSON na topicach MQTT (`status` / `sensor`).
2. Backend Python subskrybuje te topici (`+/status`, `+/sensor`).
3. Python parsuje payload i aktualizuje stan urządzeń / logikę sesji.
4. Komendy wracają z Pythona na `<device_id>/command`.

Czyli transport to **MQTT**, a nie wywołanie funkcji Python z C.

### Minimalny przykład (C/ESP-IDF) - wysłanie danych emitera

```c
char topic[64];
char payload[256];
snprintf(topic, sizeof(topic), "%s/sensor", DEVICE_ID);
snprintf(payload, sizeof(payload),
         "{\"emitter\":\"gyro\",\"sensor_value\":0,\"value\":%.3f}",
         gyro_value);
esp_mqtt_client_publish(mqtt_client, topic, payload, 0, 0, 0);
```

### Odbiór komendy w C (od backendu Python)

Backend może wysłać np.:

```json
{ "actuator": "relay", "value": true }
```

W firmware odczytujesz JSON i mapujesz `actuator` na kod sprzętowy (GPIO, I2C, PWM itd.).

> Uwaga: backend normalizuje teraz wartości emitera do stanu logicznego:
> - `bool`: `true/false`
> - `int/float`: `!= 0` => aktywny, `0` => nieaktywny
> - `string`: np. `on/true/active/high/1` => aktywny oraz `off/false/inactive/low/0` => nieaktywny.

## 4) Co to daje twórcom widgetów

Nie są ograniczeni do `led`/`button` jako jedynych typów urządzeń.
Mogą zadeklarować dowolne nazwy aktywatorów/emiterów (gyro, buzzer, przekaźnik, światło itd.),
a firmware już teraz publikuje je do backendu i przyjmuje generyczne komendy.


## 5) Gotowe testy, które możesz uruchomić

Dodałem gotowy skrypt: `tests/widget_e2e_tests.py`.

Uruchamia dokładnie 3 scenariusze:
1. **LED + button**: backend wysyła ON/OFF na `<device_id>/command`.
2. **Emitter float**: `float != 0` aktywuje połączenie (`ON`), a `0.0` je dezaktywuje (`OFF`).
3. **Dwa widgety**: sesja łączy 2 urządzenia; press/release na źródle powoduje ON/OFF na celu.

### Jak uruchomić

```bash
docker compose up -d mosquitto fastapi
python tests/widget_e2e_tests.py
```

Opcjonalne zmienne środowiskowe:
- `MQTT_HOST` (domyślnie `localhost`)
- `MQTT_PORT` (domyślnie `1883`)
- `WS_URL` (domyślnie `ws://localhost:5000/ws`)
- `API_DEVICES_URL` (domyślnie `http://localhost:5000/api/devices`)


## 6) Sterowanie widgetami z frontendu

Po tej zmianie frontend może wysyłać komendy bezpośrednio do widgetu przez WebSocket:

- event: `device_command`
- payload:

```json
{
  "device_id": "widget_001",
  "actuator": "light_strip",
  "value": 0.42
}
```

Backend przekazuje to dalej na MQTT topic `<device_id>/command` jako JSON.

W UI (lista urządzeń) masz teraz:
- wybór aktywatora z `actuators` urządzenia,
- szybkie przyciski `ON/OFF`,
- pole `Custom value` (np. `0.42`, `true`, `pwm`).

Dzięki temu można sterować także aktywatorami innymi niż LED bez zmian po stronie Pythona.
