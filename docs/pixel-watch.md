# Pixel Watch

The PCOS Wear OS app provides ambient health context signals and a glanceable tile, with background passive monitoring that survives reboots.

## Features

- **Foreground heart rate** — `MeasureClient` streaming while app is visible
- **Background passive monitoring** — `PassiveMonitoringClient` + `PassiveListenerService` for continuous HR, daily steps, and activity state (asleep/awake/exercise)
- **Boot restore** — `BroadcastReceiver` + `WorkManager` worker re-registers passive monitoring after device reboot
- **Data Layer sync** — Receives context updates from phone via `WearableListenerService` at `/pcos-context`
- **Watch tile** — Heart rate, activity state, daily steps, and broker status at a glance
- **Watch face complication** — Heart rate and activity state directly on the watch face via `ComplicationDataSourceService`
- **Runtime permissions** — Requests `BODY_SENSORS`, `ACTIVITY_RECOGNITION`, `POST_NOTIFICATIONS` at first launch
- **Splash screen** — 48dp icon on black background (WO-V15)
- **Standalone app** — Declared as standalone in manifest (Play Store requirement)

## Architecture

```
Phone (PCOS App)
    │
    │  WatchSyncManager.syncContext(setUrgent)
    │  Data Layer API (/pcos-context)
    ▼
PhoneDataListenerService ──► WatchState (shared StateFlow)
                                │
    Health Services              ├── MainActivity (Compose UI)
    │                            ├── PCOSTileService (Tile)
    ├── MeasureClient (foreground HR)  ├── PCOSOngoingActivity (WO-V4)
    └── PassiveHealthService (background)  └── PCOSComplicationDataSourceService
            │
            ├── HEART_RATE_BPM
            ├── STEPS_DAILY
            └── UserActivityInfo (asleep/awake/exercise)

    BootReceiver ──► RegisterPassiveDataWorker ──► PassiveHealthService.register()

    WatchState.update() ──► ComplicationDataSourceUpdateRequester.requestUpdate()
    (push updates, no polling)
```

## Health Services

### MeasureClient (foreground)
- Rapid heart rate updates while app is visible
- Automatically unregisters when app leaves foreground
- Has error handling for sensor unavailability

### PassiveMonitoringClient (background)
- `PassiveListenerService` receives batched data updates in background
- Monitors `HEART_RATE_BPM`, `STEPS_DAILY`, and user activity state
- `PassiveListenerConfig` requests `shouldUserActivityInfoBeRequested(true)` for sleep/awake/exercise states
- Registration persists until app uninstalls or device reboots

### Boot Restore
- `BootReceiver` listens for `ACTION_BOOT_COMPLETED`
- Delegates to `RegisterPassiveDataWorker` (WorkManager) to re-register passive monitoring
- Worker has 10-minute execution limit (vs 10 seconds for BroadcastReceiver)

### Ongoing Activity (WO-V4)
- `PCOSOngoingActivity` creates an ongoing notification paired with `OngoingActivity`
- Shows tappable icon on watch face for quick return to app
- Dynamic `Status` updates with activity state and heart rate in launcher Recents
- Notification channel: `pcos_health_monitoring` (IMPORTANCE_LOW)
- Started on permission grant, stopped on activity destroy
- Updates in real-time as `WatchState` changes

### Watch Face Complications
- `PCOSComplicationDataSourceService` extends `SuspendingComplicationDataSourceService`
- Provides heart rate and activity state directly on the watch face
- Supports `SHORT_TEXT` (e.g. "72 bpm" with "Idle" title) and `SMALL_IMAGE` (icon) types
- Tappable — opens MainActivity when tapped
- Push updates via `ComplicationDataSourceUpdateRequester` — no polling
- `WatchState.update()` automatically triggers complication refresh
- 5-minute fallback update period (system minimum for battery life)
- White heart icon for complication picker

## Permissions

| Permission | Purpose | Runtime |
|------------|---------|---------|
| `BODY_SENSORS` | Heart rate monitoring | Yes |
| `ACTIVITY_RECOGNITION` | Step count, activity state | Yes |
| `POST_NOTIFICATIONS` | Ongoing activity notification (Android 13+) | Yes |
| `RECEIVE_BOOT_COMPLETED` | Re-register passive monitoring after reboot | No |
| `FOREGROUND_SERVICE_HEALTH` | Health foreground service type | No |
| `WAKE_LOCK` | Data Layer sync | No |

## Data Layer Path

Context updates sent via `DataItem` at path `/pcos-context` with keys:
- `activity_state` — idle | walking | running | sleeping
- `broker_status` — ok | degraded | offline
- `last_result` — truncated task result preview
- `heart_rate` — phone-side heart rate (if available)

Use `setUrgent()` for time-sensitive context updates to avoid up to 30-minute sync delay.

## Play Store Compliance

| Requirement | Status |
|-------------|--------|
| WO-P1: Target API 34+ | ✅ targetSdk = 34 |
| WO-V3: Swipe to dismiss | ✅ Compose for Wear OS default |
| WO-V4: Ongoing activity | ✅ PCOSOngoingActivity with notification channel |
| WO-V13: Black background | ✅ |
| WO-V14: Min font 12sp | ✅ |
| WO-V15: Splash screen | ✅ 48dp icon on black |
| WO-V16: Watch shapes | ✅ Compose adaptive layout |
| WO-G7: Same package as phone | Planned |
| Standalone declaration | ✅ `com.google.android.wearable.standalone` |

## Build

```bash
cd apps/watch
./gradlew assembleDebug
```

Requires Wear OS 3+ (API 30+) and Health Services. Tested on Pixel Watch 2/3.
