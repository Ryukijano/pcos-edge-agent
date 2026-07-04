# Configuration

PCOS uses `pydantic-settings` for environment-driven configuration. All settings use the `PCOS_` prefix.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PCOS_BROKER_HOST` | `0.0.0.0` | Broker listen host |
| `PCOS_BROKER_PORT` | `8000` | Broker listen port |
| `PCOS_BROKER_LOG_LEVEL` | `info` | Uvicorn log level |
| `PCOS_CORS_ORIGINS` | `["*"]` | CORS allowed origins (JSON array) |
| `PCOS_PIECESOS_HOST` | `localhost` | PiecesOS MCP host |
| `PCOS_PIECESOS_PORT` | `39300` | PiecesOS MCP port |
| `PCOS_PIECESOS_ENABLED` | `true` | Enable PiecesOS connector |
| `PCOS_BRIDGE_AUTH_TOKEN` | (empty) | WebSocket bridge auth token |
| `PCOS_LOG_LEVEL` | `INFO` | Logging level |
| `PCOS_LOG_JSON` | `true` | Structured JSON logging |
| `PCOS_LOG_REQUEST_BODIES` | `false` | Log request bodies |
| `PCOS_DB_PATH` | (default) | SQLite metrics DB path |
| `PCOS_LATENCY_TARGET_ROUTE_MS` | `50` | Route endpoint latency budget |
| `PCOS_LATENCY_TARGET_EXECUTE_MS` | `500` | Execute endpoint latency budget |
| `PCOS_LATENCY_TARGET_CHROME_MS` | `200` | Chrome surface latency budget |
| `PCOS_LATENCY_TARGET_ANDROID_MS` | `1000` | Android surface latency budget |
| `PCOS_LATENCY_TARGET_CLOUD_MS` | `3000` | Cloud surface latency budget |

## .env File

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

## Usage in Code

```python
from broker.config import get_settings

settings = get_settings()
print(settings.broker_port)        # 8000
print(settings.piecesos_port)      # 39300
print(settings.latency_target_route_ms)  # 50
```

## Structured Logging

```python
from broker.logging import get_logger

log = get_logger("my_module")
log.info("event_name", key="value", count=42)
```

Output (JSON mode):
```json
{"ts": "2026-07-04T12:00:00+00:00", "level": "INFO", "logger": "my_module", "msg": "event_name", "key": "value", "count": 42}
```
