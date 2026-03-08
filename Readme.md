# Serwer

Skrypt testowy można odpalić przez:

```bash
docker compose exec flask uv run python test_mqtt_publisher.py
```

## Dokumentacja dla twórców widgetów ESP32

- Integracja i kontrakt MQTT: `docs/widget_integration.md`
- Gotowy firmware do wgrania: `widget_esp/`
- Szybki start firmware: `widget_esp/README.md`


## Testy integracyjne widgetów

- Gotowe scenariusze E2E: `tests/widget_e2e_tests.py`
