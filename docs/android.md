# Android

PCOS on Android uses **LiteRT-LM v0.13+** for on-device inference with Gemma 4 and FunctionGemma models.

## Architecture

- **LiteRTManager** — Manages Engine, Conversation, and ToolSet lifecycle
- **PCOSService** — Foreground service that pre-downloads and loads models on startup
- **BridgeClient** — WebSocket client for broker communication with exponential backoff
- **PCOSViewModel** — MVVM bridge between service and Compose UI

## Models

| Model | Size | Use Case |
|---|---|---|
| FunctionGemma 270M | ~270MB | Fast function calling with @Tool annotations |
| Gemma 4 E2B | ~2GB | Full inference for complex tasks |

Models are downloaded from HuggingFace LiteRT Community on first launch.

## Tool Use API

```kotlin
@Tool("Save a note to memory")
fun saveNote(
    @ToolParam("The note content") content: String,
    @ToolParam("Optional category") category: String = "general"
): String {
    // Save to PiecesOS or local storage
    return "Note saved: $content"
}
```

## GPU Backend

Native libraries declared in AndroidManifest:
- `libvndksupport.so`
- `libOpenCL.so`

## Build

```bash
cd apps/android
./gradlew assembleDebug
```

Requires Android SDK 34+ and Kotlin 2.0.
