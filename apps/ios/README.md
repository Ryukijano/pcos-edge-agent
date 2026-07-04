# PCOS Edge — iOS

Native iOS app running Gemma 4 E2B/E4B on-device via LiteRT-LM Swift API with Metal GPU acceleration.

## Requirements

- iOS 17.0+ / macOS 14.0+
- Xcode 15.0+
- Swift 5.9+
- iPhone 12+ / iPad with A14+ chip
- 4GB+ RAM (6GB+ recommended for E2B, 8GB+ for E4B)

## Setup

### 1. Add LiteRT-LM Swift Package

1. In Xcode: **File → Add Package Dependencies…**
2. Enter: `https://github.com/google-ai-edge/LiteRT-LM.git`
3. Select the **LiteRTLM** product and add to your target

### 2. Add Model Files

Download `.litertlm` model files from HuggingFace:

```bash
# E2B (2.58GB) — text chat
curl -L -o gemma-4-E2B-it.litertlm \
  https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm

# E4B (3.65GB) — multimodal reasoning
curl -L -o gemma-4-E4B-it.litertlm \
  https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it.litertlm

# E2B Mobile (1.1GB) — QAT quantized for low-RAM
curl -L -o gemma-4-E2B-it-mobile.litertlm \
  https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it-mobile.litertlm
```

Drag the `.litertlm` files into Xcode's project navigator. Ensure they're added to the app target's **Build Phases → Copy Bundle Resources**.

### 3. Build & Run

1. Connect your iPhone via cable
2. Select your device in Xcode's run destination
3. Press **Cmd+R** to build and run

## Features

- **Metal GPU acceleration** — LiteRT-LM Swift API with `.gpu` backend
- **MTP/speculative decoding** — 2x+ faster decode on Metal (v0.11+)
- **RAM-based model auto-selection** — picks E2B Mobile / E2B / E4B based on device RAM
- **Real-time benchmark dashboard** — prefill/decode tk/s and latency
- **Streaming inference** — `sendMessageStreaming()` with async sequences
- **Multimodal support** — vision + audio backends for E4B (configure `visionBackend`/`audioBackend`)
- **Tool calling** — Swift `@ToolSet` structs for function calling

## Architecture

```
PCOSEdgeApp.swift          — App entry point
ContentView.swift          — SwiftUI chat UI with model selector + benchmarks
LiteRTManager.swift        — Engine lifecycle, RAM detection, Metal GPU, streaming
```

## Backend Selection

| Apple Chip | Backend | Notes |
|---|---|---|
| A17 Pro+ / M1+ | Metal GPU | Full acceleration, MTP enabled |
| A14–A16 | Metal GPU | Supported, slightly lower throughput |
| Older | CPU | Fallback |

## Performance (Google benchmarks)

| Model | Device | CPU Prefill (tk/s) | CPU Decode (tk/s) | GPU Prefill (tk/s) | GPU Decode (tk/s) |
|---|---|---|---|---|---|
| Gemma 4 E2B | iPhone 17 Pro | 532 | 25 | 2878 | 57 |
| Gemma 4 E4B | iPhone 17 Pro | 159 | 10 | 1189 | 25 |
| Gemma 4 E2B | MacBook Pro M4 | 901 | 42 | 7835 | 160 |
| Gemma 4 E4B | MacBook Pro M4 | 277 | 27 | 2560 | 101 |

## Known Issues

- **Metal TopK sampler**: `libLiteRtTopKMetalSampler.dylib` not yet shipped in prebuilts. Falls back to CPU sampling on iOS. Does not affect correctness, only marginal decode speed impact. ([Issue #1990](https://github.com/google-ai-edge/LiteRT-LM/issues/1990))
