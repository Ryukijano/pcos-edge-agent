# PCOS Edge — Flutter

Cross-platform on-device LLM app running Gemma 4 via LiteRT-LM with hardware acceleration.

## Supported Platforms

| Platform | Backend | Status |
|---|---|---|
| Android | OpenCL GPU / NPU | ✅ Production |
| iOS | Metal GPU | ✅ Production |
| macOS | Metal GPU | ✅ Production |
| Windows | OpenCL GPU | ✅ Production |
| Linux | OpenCL GPU | ✅ Production |

## Setup

```bash
cd apps/flutter
flutter pub get
flutter run
```

## Dependencies

- `flutter_litert_lm: ^0.3.0` — Community LiteRT-LM Flutter plugin
- `shared_preferences` — Settings persistence
- `path_provider` — Model file storage

## Features

- **Cross-platform** — Single codebase for iOS, Android, macOS, Windows, Linux
- **Hardware acceleration** — GPU (OpenCL/Metal) and NPU backends
- **RAM-based model auto-selection** — Picks E2B Mobile / E2B / E4B based on device RAM
- **Real-time benchmark dashboard** — TTFT, prefill/decode tk/s, total latency
- **Streaming inference** — Token-by-token streaming via async generators
- **Model selector** — Switch between FunctionGemma, E2B, E4B, and QAT mobile variants

## Architecture

```
lib/
  main.dart            — Flutter UI with chat, model selector, benchmark dashboard
  litert_manager.dart  — Engine lifecycle, RAM detection, streaming inference
```

## Model Files

Place `.litertlm` model files in the app's assets or download them at runtime:

```bash
# E2B (2.58GB)
curl -L -o gemma-4-E2B-it.litertlm \
  https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm
```
