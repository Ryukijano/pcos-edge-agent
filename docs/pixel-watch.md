# Pixel Watch

The PCOS Wear OS app provides ambient context signals and a glanceable tile.

## Features

- **Health monitoring** — Heart rate via Health Services `MeasureClient`
- **Data Layer sync** — Receives context updates from phone via `WearableListenerService`
- **Watch tile** — Heart rate, activity state, and broker status at a glance
- **Compose for Wear OS** — Material-designed round screen UI

## Architecture

```
Phone (PCOS App)
    │
    │  Data Layer API (/pcos-context)
    ▼
PhoneDataListenerService
    │
    ▼
WatchState (shared StateFlow)
    │
    ├── MainActivity (Compose UI)
    └── PCOSTileService (Tile)
```

## Health Services

Uses `MeasureClient` for foreground heart rate streaming and `PassiveMonitoringClient` for background activity detection.

## Data Layer Path

Context updates are sent via `DataItem` at path `/pcos-context` with keys:
- `activity_state` — idle | walking | running | sleeping
- `broker_status` — ok | degraded | offline
- `last_result` — truncated task result preview
- `heart_rate` — phone-side heart rate (if available)

## Build

```bash
cd apps/watch
./gradlew assembleDebug
```

Requires Wear OS 3+ (API 30+) and Health Services.
