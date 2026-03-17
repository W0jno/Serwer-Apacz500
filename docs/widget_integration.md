# Dokumentacja integracji widgetów ESP32 z serwerem MQTT

## 1. Cel dokumentu

Dokument opisuje standard integracji widgetów ESP32 z systemem opartym o MQTT, FastAPI i frontend webowy.
Zakres obejmuje:

- uruchomienie środowiska serwerowego,
- konfigurację i uruchomienie firmware ESP32,
- kontrakt MQTT (topici i formaty payloadów),
- sterowanie widgetami z poziomu frontendu,
- uruchamianie testów integracyjnych.

---

## 2. Architektura komunikacji

Komunikacja pomiędzy firmware C (ESP32) i backendem Python odbywa się **wyłącznie przez MQTT**.

Przepływ danych:

1. ESP32 publikuje dane urządzenia na topicach:
   - `<device_id>/status`
   - `<device_id>/sensor`
2. Backend FastAPI subskrybuje:
   - `+/status`
   - `+/sensor`
3. Backend przetwarza dane i publikuje komendy sterujące na:
   - `<device_id>/command`
4. ESP32 subskrybuje `<device_id>/command` i wykonuje komendy sprzętowe.

---

## 3. Uruchomienie normalnego serwera (krok po kroku)

### 3.1. Wymagania

- Docker i Docker Compose,
- wolne porty: `1883`, `5000`, `5173`.

### 3.2. Start środowiska

1. Przejdź do katalogu projektu:

```bash
cd /workspace/Serwer-Apacz500
```

2. Uruchom wszystkie usługi:

```bash
docker compose up -d --build
```

3. Zweryfikuj stan usług:

```bash
docker compose ps
```

Oczekiwane kontenery:
- `mosquitto` (MQTT broker),
- `fastapi-server` (backend API + WebSocket),
- `react-frontend` (interfejs webowy).

4. (Opcjonalnie) Podgląd logów backendu:

```bash
docker compose logs -f fastapi
```


## 3A. Konfiguracja serwera pod połączenia widgetów przez Wi‑Fi (LAN)

Aby urządzenia ESP32 mogły łączyć się z serwerem z sieci Wi‑Fi, serwer musi być osiągalny po adresie LAN komputera/hosta (nie `localhost`).

### 3A.1. Wystawienie usług na interfejs sieciowy

Konfiguracja `docker-compose.yml` mapuje porty na `0.0.0.0`, dzięki czemu usługi są dostępne z innych urządzeń w tej samej sieci:

- MQTT broker: `0.0.0.0:1883`
- Backend API/WebSocket: `0.0.0.0:5000`
- Frontend: `0.0.0.0:5173`

### 3A.2. Ustalenie adresu IP hosta

Na komputerze uruchamiającym serwer odczytaj adres LAN (np. `192.168.0.126`).

Przykładowe polecenia:

```bash
ip a
```

lub:

```bash
hostname -I
```

### 3A.3. Konfiguracja widgeta ESP32

W `idf.py menuconfig` ustaw:

- `MQTT broker URI` = `mqtt://<LAN_IP_SERWERA>`

Przykład:

- `mqtt://192.168.0.126`

`localhost` w firmware ESP32 jest niepoprawne (oznacza samo urządzenie ESP32, a nie serwer).

### 3A.4. Konfiguracja dostępu do frontendu z innych urządzeń

Frontend i backend będą dostępne z telefonu/laptopa w tej samej sieci pod adresami:

- `http://<LAN_IP_SERWERA>:5173`
- `http://<LAN_IP_SERWERA>:5000/api/devices`
- `ws://<LAN_IP_SERWERA>:5000/ws`

### 3A.5. Zapora sieciowa (firewall)

Jeżeli połączenie z innego urządzenia nie działa, należy odblokować porty:

- `1883/tcp` (MQTT)
- `5000/tcp` (FastAPI/WebSocket)
- `5173/tcp` (frontend)

### 3.3. Punkty dostępu

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:5000/api/devices`
- WebSocket: `ws://localhost:5000/ws`

### 3.4. Zatrzymanie środowiska

```bash
docker compose down
```

---

## 4. Konfiguracja i uruchomienie firmware ESP32

### 4.1. Konfiguracja (`menuconfig`)

W katalogu `widget_esp`:

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
- Actuators: `led,light_strip,buzzer,relay`
- Emitters: `button,gyro,temp_sensor,motion`

### 4.2. Build i flash

```bash
cd widget_esp
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

---


## 4A. Uruchomienie ESP-IDF i pliku konfiguracyjnego (`menuconfig`)

`menuconfig` nie jest osobnym plikiem do ręcznego uruchamiania — to interfejs konfiguracji projektu ESP-IDF,
który zapisuje ustawienia do `sdkconfig` w katalogu `widget_esp/`.

### 4A.1. Instalacja i aktywacja ESP-IDF

Przykładowy flow (Linux/macOS):

```bash
# 1) Pobierz ESP-IDF
mkdir -p ~/esp
cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf

# 2) Zainstaluj narzędzia
./install.sh esp32

# 3) Aktywuj środowisko (powtarzaj w każdym nowym terminalu)
source ./export.sh
```

### 4A.2. Wejście do projektu widgeta

```bash
cd /workspace/Serwer-Apacz500/widget_esp
```

### 4A.3. Uruchomienie konfiguratora

```bash
idf.py set-target esp32
idf.py menuconfig
```

Po wejściu do menu przejdź do: **Widget ESP32 config** i ustaw:
- `Widget device ID`
- `WiFi SSID`
- `WiFi password`
- `MQTT broker URI`
- `Actuators list (CSV)`
- `Emitters list (CSV)`
- `Status publish interval (ms)`

Po zapisaniu konfiguracji ESP-IDF zapisze ustawienia do pliku `widget_esp/sdkconfig`.

### 4A.4. Build i flash po konfiguracji

```bash
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```


## 4B. Integracja w projekcie programisty korzystającym z PlatformIO (krok po kroku)

Poniższa procedura zakłada, że zespół ma już własny projekt widgeta w PlatformIO i chce dodać konfigurację Wi‑Fi/MQTT bez utraty własnej logiki.

### 4B.1. Struktura docelowa projektu PlatformIO

W typowym projekcie PlatformIO (ESP-IDF) powinny istnieć:

- `platformio.ini`
- `src/main.c` (lub `src/main.cpp`) — logika zespołu
- `main/Kconfig.projbuild` — konfiguracja `menuconfig` (jeżeli nie ma, należy utworzyć)

### 4B.2. Ustawienie frameworku w PlatformIO

W pliku `platformio.ini` ustaw środowisko ESP-IDF:

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = espidf
monitor_speed = 115200
```

### 4B.3. Skopiowanie definicji opcji konfiguracyjnych

1. Skopiuj plik:

- z: `widget_esp/main/Kconfig.projbuild`
- do: `<TWOJ_PROJEKT_PLATFORMIO>/main/Kconfig.projbuild`

2. Jeżeli w projekcie docelowym istnieje już `main/Kconfig.projbuild`, nie nadpisuj go w całości —
   przenieś sekcje `config WIDGET_*` i scal ręcznie.

Plik źródłowy opcji w tym repo:
- `WIDGET_DEVICE_ID`
- `WIDGET_WIFI_SSID`
- `WIDGET_WIFI_PASS`
- `WIDGET_MQTT_BROKER_URI`
- `WIDGET_ACTUATORS_CSV`
- `WIDGET_EMITTERS_CSV`
- `WIDGET_STATUS_INTERVAL_MS`

### 4B.4. Podłączenie `CONFIG_*` w kodzie zespołu

W kodzie firmware (np. `src/main.c`) należy:

1. dodać:

```c
#include "sdkconfig.h"
```

2. użyć makr `CONFIG_*` zamiast hardcodów, np.:

```c
#define DEVICE_ID CONFIG_WIDGET_DEVICE_ID
#define WIFI_SSID CONFIG_WIDGET_WIFI_SSID
#define WIFI_PASS CONFIG_WIDGET_WIFI_PASS
#define MQTT_BROKER_URI CONFIG_WIDGET_MQTT_BROKER_URI
```

Referencja użycia w tym repo: `widget_esp/main/widget_esp.c`.

### 4B.5. Konfiguracja w menuconfig (PlatformIO)

W katalogu projektu PlatformIO uruchom:

```bash
pio run -t menuconfig
```

Następnie przejdź do sekcji `Widget ESP32 config` i uzupełnij dane:
- `Widget device ID`
- `WiFi SSID`
- `WiFi password`
- `MQTT broker URI` (np. `mqtt://192.168.0.126`)
- pozostałe opcje według potrzeb

### 4B.6. Build, upload, monitor

```bash
pio run
pio run -t upload
pio device monitor
```

### 4B.7. Co **nie** nadpisuje logiki zespołu

- `pio run -t menuconfig` zmienia tylko konfigurację (`sdkconfig`) projektu,
- logika biznesowa w `src/main.c` / innych plikach C pozostaje taka, jaką napisał zespół,
- program na ESP zostanie podmieniony dopiero przy `upload` (standardowe wgrywanie firmware).

### 4B.8. Minimalna lista rzeczy do przeniesienia z tego repo

Jeśli zespół chce tylko konfigurację i integrację MQTT, a nie cały firmware referencyjny:

1. **Obowiązkowo** przenieść:
   - `widget_esp/main/Kconfig.projbuild` -> `<projekt>/main/Kconfig.projbuild` (scalić, jeśli istnieje)

2. **Opcjonalnie jako referencję** podejrzeć i zaadaptować fragmenty z:
   - `widget_esp/main/widget_esp.c` (użycie `CONFIG_*`, tematy MQTT, format payloadów)

3. Nie trzeba kopiować całego `widget_esp/` 1:1, jeżeli zespół ma własną logikę firmware.



## 4C. Integracja bez `menuconfig` (hardcoded config)

Dla zespołów, które nie chcą używać `menuconfig`, dostępny jest gotowy moduł:

- `widget_dropin/widget_bridge.c`
- `widget_dropin/widget_bridge.h`
- instrukcja: `widget_dropin/README.md`

W tym wariancie konfiguracja (`SSID`, `hasło`, `device_id`, `MQTT URI`) jest wpisywana bezpośrednio w `widget_bridge.c`.

## 5. Kontrakt MQTT

### 5.1. Status urządzenia (ESP32 -> serwer)

Topic: `<device_id>/status`

Przykładowy payload:

```json
{
  "status": true,
  "charge_level": 100,
  "actuators": ["led", "light_strip", "relay"],
  "emitters": ["button", "gyro", "motion"]
}
```

### 5.2. Dane emitera (ESP32 -> serwer)

Topic: `<device_id>/sensor`

Przykładowy payload:

```json
{
  "emitter": "button",
  "sensor_value": 0,
  "value": 0
}
```

Zasady interpretacji po stronie backendu:

- `sensor_value` pozostaje polem kompatybilności wstecznej,
- backend interpretuje również `value` i normalizuje różne typy danych do stanu logicznego:
  - `bool`: `true` / `false`,
  - `int/float`: `!= 0` => aktywny, `0` => nieaktywny,
  - `string`: np. `on`, `true`, `active`, `high`, `1` => aktywny; `off`, `false`, `inactive`, `low`, `0` => nieaktywny.

### 5.3. Komendy sterujące (serwer -> ESP32)

Topic: `<device_id>/command`

Wspierane formaty:

1. Kompatybilny wstecz:

```json
{ "state": true }
```

2. Generyczny:

```json
{ "actuator": "light_strip", "value": 0.42 }
```

Implementacja firmware powinna mapować `actuator` na odpowiednią logikę sprzętową (GPIO/I2C/PWM itp.).

---

## 6. Sterowanie widgetami z frontendu

Frontend umożliwia sterowanie urządzeniami przez WebSocket event `device_command`.

Payload eventu:

```json
{
  "device_id": "widget_001",
  "actuator": "light_strip",
  "value": 0.42
}
```

Backend przekazuje payload na MQTT topic `<device_id>/command`.

Elementy dostępne w UI:
- wybór aktywatora (na podstawie `actuators` z `status`),
- szybkie komendy `ON/OFF`,
- pole wartości własnej (`Custom value`).

---

## 7. Przykład publikacji danych emitera w C (ESP-IDF)

```c
char topic[64];
char payload[256];
snprintf(topic, sizeof(topic), "%s/sensor", DEVICE_ID);
snprintf(payload, sizeof(payload),
         "{\"emitter\":\"gyro\",\"sensor_value\":0,\"value\":%.3f}",
         gyro_value);
esp_mqtt_client_publish(mqtt_client, topic, payload, 0, 0, 0);
```

---

## 8. Testy integracyjne

Skrypt testów: `tests/widget_e2e_tests.py`

Scenariusze:
1. LED + button,
2. emitter float (`float != 0` => ON, `0.0` => OFF),
3. komunikacja dwóch widgetów w sesji.

Uruchomienie:

```bash
docker compose up -d mosquitto fastapi
python tests/widget_e2e_tests.py
```

Opcjonalne zmienne środowiskowe:
- `MQTT_HOST` (domyślnie `localhost`)
- `MQTT_PORT` (domyślnie `1883`)
- `WS_URL` (domyślnie `ws://localhost:5000/ws`)
- `API_DEVICES_URL` (domyślnie `http://localhost:5000/api/devices`)


## 4D. Integracja dla zespołów używających Arduino framework (PlatformIO)

Jeżeli zespół rozwija firmware w **PlatformIO + Arduino framework**, należy użyć gotowego modułu z folderu `widget_arduino_dropin/`.

### 4D.1. Skopiowanie plików

Do projektu programisty skopiować:

- `widget_arduino_dropin/widget_bridge_arduino.h` -> `include/widget_bridge_arduino.h`
- `widget_arduino_dropin/widget_bridge_arduino.cpp` -> `src/widget_bridge_arduino.cpp`

### 4D.2. Konfiguracja `platformio.ini`

W `platformio.ini` dodać bibliotekę:

```ini
lib_deps =
  knolleary/PubSubClient
```

### 4D.3. Uzupełnienie danych połączeniowych

W pliku `src/widget_bridge_arduino.cpp` należy zmienić pola oznaczone komentarzem `// <- ZMIEŃ`:

- SSID i hasło Wi‑Fi,
- `WIDGET_DEVICE_ID`,
- adres i port brokera MQTT,
- listy `actuators` i `emitters`.

### 4D.4. Wpięcie modułu w `main.cpp`

W `setup()`:

1. zarejestrować callback `widgetBridgeArduinoSetCommandCallback(...)`,
2. wywołać `widgetBridgeArduinoInit()`.

W `loop()`:

1. wywoływać `widgetBridgeArduinoLoop()` w każdej iteracji,
2. publikować sensory przez `widgetBridgeArduinoPublishSensor(...)` w momentach wystąpienia zdarzeń.

### 4D.5. Build i upload

```bash
pio run
pio run -t upload
pio device monitor
```

Szczegółowa instrukcja krok po kroku znajduje się w: `widget_arduino_dropin/README.md`.


## 8. Zależności serwerowe (widget Y -> widget X)

Serwer obsługuje reguły zależności: zdarzenie z emitera na urządzeniu źródłowym może automatycznie publikować payload na wskazany topic urządzenia docelowego.

### 8.1. API reguł

- `GET /api/dependencies` — lista reguł
- `POST /api/dependencies` — dodanie reguły
- `DELETE /api/dependencies/{rule_id}` — usunięcie reguły

Payload `POST /api/dependencies`:

```json
{
  "source_device_id": "widget_y",
  "source_emitter": "button",
  "trigger_state": "on",
  "target_device_id": "widget_x",
  "target_topic": "widget_x/command",
  "payload": {
    "command": "actuator",
    "name": "lamp",
    "state": true
  },
  "enabled": true
}
```

Znaczenie pól:
- `trigger_state`: `on`, `off` lub `any`.
- `target_topic`: jeśli puste, serwer używa domyślnie `<target_device_id>/command`.
- `payload`: dowolny JSON wysyłany na MQTT po spełnieniu warunku.

### 8.2. Przykład scenariusza

Cel: gdy `button` na `widget_y` zostanie naciśnięty (`on`), to `widget_x` ma zapalić lampkę.

1. Tworzysz regułę API (jak wyżej).
2. `widget_y` publikuje sensor na `widget_y/sensor`, np.:

```json
{
  "device_id": "widget_y",
  "emitter": "button",
  "sensor_value": 1,
  "value": 1
}
```

3. Serwer publikuje na `widget_x/command` payload z reguły:

```json
{
  "command": "actuator",
  "name": "lamp",
  "state": true,
  "source_device": "widget_y",
  "emitter": "button",
  "sensor_value": 1,
  "value": 1
}
```

Metadane (`source_device`, `emitter`, `sensor_value`, `value`, `state`) są automatycznie uzupełniane, jeśli nie zostały podane w `payload` reguły.
