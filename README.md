# beeplan-builder

Облачная сборка прошивок **beeplan-edge** и **beeplan-gateway** для веб-прошивки (ESPHome-style).

## Локальный запуск

Из корня рабочей области:

```powershell
docker build -f beeplan-builder/Dockerfile -t beeplan-builder .
docker run --rm -p 9000:9000 -e BEEPLAN_BUILDER_SECRET=dev-builder-secret beeplan-builder
```

## API (internal)

- `POST /v1/builds` — Bearer `BEEPLAN_BUILDER_SECRET`
- `GET /v1/builds/{id}` — статус
- `GET /v1/builds/{id}/firmware.bin`
- `GET /v1/builds/{id}/manifest.json`

Вызывается из **beeplan-api**, не напрямую из браузера.

## Поддерживаемые платы (`board`)

| `board` | MCU | PlatformIO env | esp-web-tools `chipFamily` |
|---------|-----|----------------|----------------------------|
| `esp32dev` | ESP32 (classic) | `esp32dev` | `ESP32` |
| `esp32c3` | ESP32-C3 | `esp32c3` | `ESP32-C3` |
