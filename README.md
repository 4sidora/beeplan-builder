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

| `board` | Роль | PlatformIO env | Статус |
|---------|------|----------------|--------|
| `ttgo-t-call-v14` | Gateway | `ttgo-t-call-v14` | ✅ сборка |
| `ttgo-t-energy` | Edge | `ttgo-t-energy` | ✅ сборка |

В веб-мастере также показаны платы «Скоро» (без сборки): кастомный ESP32 Wi-Fi, LILYGO T-SIM7600, T-Energy-S3, T7 S3.
