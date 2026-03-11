# Serwer

## Jak odpalić normalny serwer

1. Uruchom cały stack:

```bash
docker compose up -d --build
```

2. Sprawdź status usług:

```bash
docker compose ps
```

3. Otwórz:
- frontend: `http://localhost:5173`
- backend API: `http://localhost:5000/api/devices`
- websocket: `ws://localhost:5000/ws`

## Dokumentacja dla twórców widgetów ESP32

- Integracja i kontrakt MQTT: `docs/widget_integration.md`
- Gotowy firmware do wgrania: `widget_esp/`
- Szybki start firmware: `widget_esp/README.md`

## Testy integracyjne widgetów

- Gotowe scenariusze E2E: `tests/widget_e2e_tests.py`
- Sterowanie aktywatorami z UI (frontend): `device_command` opisane w `docs/widget_integration.md`

## Jak uruchomić serwer (krok po kroku)

Szczegółowa instrukcja jest w: `docs/widget_integration.md` (sekcja **3. Uruchomienie normalnego serwera (krok po kroku)**).


## Dostęp po Wi‑Fi (LAN)

Aby widgety łączyły się z serwerem przez Wi‑Fi, skonfiguruj je adresem LAN serwera (np. `mqtt://192.168.0.126`)
zamiast `localhost`.

Szczegóły konfiguracji LAN i portów są w `docs/widget_integration.md` (sekcja **3A. Konfiguracja serwera pod połączenia widgetów przez Wi‑Fi (LAN)**).


## Szybka integracja bez menuconfig (hardcoded)

- Gotowy moduł do wpięcia w istniejący projekt zespołu: `widget_dropin/`
- Instrukcja krok po kroku: `widget_dropin/README.md`

## Szybka integracja dla PlatformIO + Arduino framework

- Gotowy moduł: `widget_arduino_dropin/`
- Instrukcja krok po kroku: `widget_arduino_dropin/README.md`
