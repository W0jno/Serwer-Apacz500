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
