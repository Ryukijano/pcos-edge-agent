# PCOS Android App

Local-first AI runtime for Android — runs Gemma 4 and FunctionGemma via LiteRT-LM with on-device function calling.

## Architecture

- **LiteRTManager** — Engine → Session pipeline for Gemma 4 (quality) and FunctionGemma 270M (fast function calls)
- **BridgeClient** — WebSocket client to PCOS Context Broker for Chrome ↔ Android relay
- **PCOSService** — Foreground service keeping model warm and bridge connected
- **MainActivity** — Jetpack Compose UI with model selector, input, and streaming output

## Setup

1. Download model files:
   - `gemma_4.task` (~4GB) — full quality model
   - `functiongemma_270m.task` (~270MB) — fast function calling
2. Place in `app/src/main/assets/models/`
3. Build: `./gradlew assembleDebug`
4. Install: `adb install app/build/outputs/apk/debug/app-debug.apk`

## Function Calling

Three built-in tools run fully offline:
- `save_note` — save text locally
- `create_task` — create todo with due date
- `search_memory` — query PiecesOS LTM

## Bridge

Connects to `ws://localhost:8000/bridge` on the PCOS Context Broker.
Chrome extension sends tasks → Android executes via LiteRT-LM → results stream back.
