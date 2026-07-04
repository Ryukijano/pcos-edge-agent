# PCOS — Personal Context Operating System

> A local-first hybrid AI runtime across Chrome, Android, Pixel Watch, PiecesOS, and cloud LLMs.

## What is this?

PCOS is not a chatbot. It is a **context router** — a deterministic system that coordinates multiple specialized local AI models, memory systems, devices, and tools into one coherent cognitive runtime while keeping latency low and preserving privacy.

```
                   User

                     │

          Intent + Current Context

                     │

          PCOS Context Broker
────────────────────────────────────────
      Browser Context (Chrome)
      Android Context
      Wearable Context (Pixel Watch 4)
      PiecesOS Episodic Memory
      Calendar / Notifications / Files
      Git / IDE / Research
────────────────────────────────────────
        Context Selection Engine
────────────────────────────────────────
  Prompt API · Gemma 4 · LiteRT-LM
  AI Edge Gallery · FunctionGemma
  Cloud Gemini · OpenAI · Claude
────────────────────────────────────────
          Tool Execution Layer
────────────────────────────────────────
  Browser · Phone · Watch · MCP
```

## Repo Structure

```
pcos-edge-agent/
├── apps/
│   ├── android/           # LiteRT-LM, Gemma, FunctionGemma, AI Edge Gallery
│   ├── chrome-extension/  # Side panel, Built-in AI API calls, context capture
│   ├── watch/             # Pixel Watch 4 Wear OS companion
│   └── desktop/           # Optional desktop tray / Pieces integration
├── broker/
│   ├── router/            # Routing decision engine (router.py)
│   ├── planner/           # Prompt + tool plan builder
│   ├── context/           # PCOSContext schema (context_schema.py)
│   ├── policies/          # Escalation + privacy policies
│   └── main.py            # FastAPI service entry point
├── memory/
│   ├── pieces/            # PiecesOS MCP connector (connector.py)
│   └── embeddings/        # Local semantic search layer
├── models/
│   ├── prompt-api/        # Chrome Built-in AI JS wrapper (chrome_ai.js)
│   ├── litert/            # LiteRT-LM Android configs
│   ├── gemma/             # Trained Gemma model notes + configs
│   └── cloud/             # Cloud escalation layer (escalation.py)
├── tools/
│   ├── browser/           # Page context, DOM, tab tools
│   ├── android/           # Camera, mic, sensors, notifications
│   ├── mcp/               # MCP connectors
│   └── filesystem/        # Local file tools
├── docs/
│   ├── architecture.md
│   ├── routing-spec.md
│   └── tickets.md         # 10-ticket implementation plan
├── requirements.txt
└── README.md
```

## Five Planes

| Plane | Surface | Role |
|---|---|---|
| Browser | Chrome 138+ | Page-grounded NLP transforms, side panel UI, WebGPU |
| Device (Android) | Android + LiteRT-LM | Private offline inference, function calling, NPU/GPU |
| Device (iOS) | iOS + LiteRT-LM Swift | Private offline inference, Metal GPU, multimodal |
| Memory | PiecesOS | Episodic LTM, MCP, workflow context |
| Ambient | Pixel Watch 4 | Lightweight context signals, quick actions |
| Desktop | lit serve | Local desktop GPU fallback (Gemini-compatible API) |
| Cloud | Gemini / OpenAI | Overflow reasoning, long context only (last resort) |

## On-Device Models (LiteRT-LM)

| Model | Size | Backend | Prefill (tk/s) | Decode (tk/s) | Use Case |
|---|---|---|---|---|---|
| FunctionGemma 270M | 289MB | CPU | 2238 | 154 | Function calling, tool use |
| Gemma 4 E2B (2.3B) | 2.58GB | GPU | 3808 | 52 | General chat, transforms |
| Gemma 4 E4B (4.5B) | 3.65GB | GPU | 1293 | 22 | Complex reasoning, multimodal |
| Gemma 4 E2B Mobile (QAT) | 1.1GB | GPU | ~3500 | ~48 | Low-RAM devices, text-only |
| Gemma 4 E4B Mobile (QAT) | 2.5GB | GPU | ~1200 | ~20 | Low-RAM reasoning + multimodal |

*Benchmarks from Samsung S26 Ultra and iPhone 17 Pro (Google official). Adreno 730 (OnePlus 11R) uses OpenCL GPU backend. MTP/speculative decoding enabled for E2B/E4B. Apple Metal supported via LiteRT-LM Swift APIs. NPU (Qualcomm QNN) supported on Snapdragon 8 Gen 2+ with auto-fallback to GPU/CPU. QAT mobile models use Google's wNa8o8 quantization schema with targeted 2-bit decoding layers and optimized KV caches.*

### iOS / Apple Silicon Benchmarks

| Model | Device | CPU Prefill (tk/s) | CPU Decode (tk/s) | GPU Prefill (tk/s) | GPU Decode (tk/s) |
|---|---|---|---|---|---|
| Gemma 4 E2B | iPhone 17 Pro | 532 | 25 | 2878 | 57 |
| Gemma 4 E4B | iPhone 17 Pro | 159 | 10 | 1189 | 25 |
| Gemma 4 E2B | MacBook Pro M4 | 901 | 42 | 7835 | 160 |
| Gemma 4 E4B | MacBook Pro M4 | 277 | 27 | 2560 | 101 |

### RAM-Based Model Auto-Selection

The Android and iOS apps automatically detect device RAM and select the best model:

| RAM | Tier | Default Model | Reasoning Model | Action Model |
|---|---|---|---|---|
| < 6GB | Low-End | E2B Mobile (1.1GB) | E2B Mobile | FunctionGemma |
| 6-8GB | Mid-Range | E2B (2.6GB) | E4B Mobile (2.5GB) | FunctionGemma |
| 8+GB | High-End | E2B (2.6GB) | E4B (3.7GB) | FunctionGemma |

OEM RAM expansion detection (Realme, Xiaomi, OPPO, OnePlus) caps reported RAM to avoid overestimating available memory.

### QAT Mobile Quantization

Google released Quantization-Aware Training (QAT) checkpoints for Gemma 4 E2B and E4B with a custom mobile-optimized quantization schema:

- **Targeted 2-bit quantization** — decoding layers heavily compressed, reasoning layers kept at higher precision
- **Static activations** — pre-calculated scaling reduces mobile processor workload
- **Channel-wise quantization** — structured for mobile accelerator hardware
- **KV cache optimization** — compressed vocabulary and short-term memory for longer chats in less RAM

Result: **E2B text-only fits in <1GB RAM** (vs 2.58GB standard), making it viable on devices with 4GB RAM.

### Chrome WebGPU Surface

Browser-grounded reasoning tasks now run **Gemma 4 E2B/E4B directly in Chrome** via the LiteRT-LM JavaScript API with WebGPU acceleration:

```javascript
import { Engine } from 'https://cdn.jsdelivr.net/npm/@litert-lm/core/+esm';
const engine = await Engine.create({
  model: 'https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it-web.litertlm'
});
```

- No relay to Android needed for browser tasks
- Streaming inference via `sendMessageStreaming()`
- Auto-fallback to Chrome Built-in AI if WebGPU unavailable
- E2B for transforms, E4B for reasoning (auto-selected by broker)

### Backend Auto-Selection

The Android app automatically detects the best available backend:

1. **NPU** (Qualcomm QNN) — Snapdragon 8 Gen 2+ (SM8550+), Hexagon DSP
2. **GPU** (OpenCL/ML Drift) — Adreno 730+ (Snapdragon 8 Gen 1+)
3. **CPU** (XNNPack) — Universal fallback

If the preferred backend fails, the app automatically falls back to the next available. MTP is disabled on CPU fallback for stability.

### Model Warm-Loading

On app startup, Gemma 4 E2B is warm-loaded in the background (download + initialize) for instant first response. Falls back to FunctionGemma 270M if E2B download fails.

### Dynamic Model Switching

When the broker routes a task to a different model surface (e.g., E2B → E4B for reasoning), the app automatically:
1. Downloads the target model if not cached
2. Swaps the loaded model in memory
3. Resumes inference on the new model

## Routing Policy

```python
def route(task):
    if task.sensitivity == "private" or task.is_offline:
        return "android_litert_gemma_e4b" if task.type == "reasoning" else "android_litert_gemma_e2b"
    if task.modality in ("image", "audio") and not task.is_webpage_grounded:
        return "android_litert_gemma_e4b"  # multimodal
    if task.is_webpage_grounded and task.is_short and task.task_type == "transform":
        return "chrome_builtin_ai"  # Summarizer / Translator / etc.
    if task.is_webpage_grounded and (task.type == "reasoning" or not task.is_short):
        return "chrome_webgpu"  # Gemma 4 E2B/E4B in browser via WebGPU
    if task.requires_personal_context:
        return "piecesos_memory_then_local"
    if task.requires_action:
        return "android_litert_functiongemma"
    if task.exceeds_local_limits:
        if desktop.litert_server_available:
            return "litert_server"  # local desktop GPU via lit serve
        return "cloud_llm_escalation"
    return "android_litert_gemma_e2b"  # default local
```

### LiteRT-LM Server (`lit serve`)

The LiteRT-LM CLI includes a `serve` command that starts an **OpenAI-compatible local HTTP server**:

```bash
litert-lm serve
# Starts on port 9379 with OpenAI-compatible endpoints:
#   GET  /v1/models          — list available models
#   POST /v1/chat/completions — chat completions (streaming supported)
```

The model field supports dynamic backend selection: `model_id[,backend][,max_tokens]`
Example: `"gemma4-e2b,gpu,4096"`

When a desktop with `lit serve` running is detected in the context, the broker routes long reasoning tasks to it instead of cloud — keeping all data local while leveraging desktop GPU power.

The broker proxies requests via three endpoints:
- `GET /litert_server/models` — list available models
- `POST /litert_server/infer` — non-streaming inference
- `POST /litert_server/chat/stream` — SSE streaming inference

A Python client wrapper (`LiteRTServerClient`) is available in `models/local/litert_server_client.py` for drop-in OpenAI client replacement:

```python
from models.local.litert_server_client import LiteRTServerClient

with LiteRTServerClient() as client:
    if client.is_available():
        resp = client.chat_completion(
            messages=[{"role": "user", "content": "Hello!"}],
            model="gemma4-e2b,gpu,4096",
        )
        print(resp["choices"][0]["message"]["content"])
```

### Benchmark Dashboard

The Android, iOS, and Flutter apps display real-time performance metrics after each inference:

- **TTFT** (ms) — time-to-first-token, measures prefill latency
- **Prefill throughput** (tokens/sec) — input processing speed
- **Decode throughput** (tokens/sec) — output generation speed
- **Total latency** (ms) — wall-clock time for the complete inference

TTFT is measured from inference start to the first streaming chunk received. This matches the LiteRT-LM `BenchmarkInfo` metric: `TTFT = first_prefill_turn_duration + first_decode_turn_duration`.

Tokens are estimated at ~4 chars/token for English text. The dashboard updates after every execution.

### LoRA Adapter Infrastructure

Task-specific LoRA (Low-Rank Adaptation) adapters can be loaded on top of the base model for specialized domains without doubling memory footprint:

| Adapter | Task | Rank | Size |
|---|---|---|---|
| `gemma4-code-lora` | Code generation | 16 | ~50MB |
| `gemma4-medical-lora` | Medical Q&A | 16 | ~50MB |
| `gemma4-creative-lora` | Creative writing | 32 | ~80MB |

Adapters share the base model's KV cache and weights — only the small adapter weights are swapped. This enables domain-specific fine-tuning without loading separate full models.

## Chrome Built-in AI APIs (Chrome 138+)

**Stable:**
- ✅ `LanguageModel` (Prompt API) — natural language instructions to Gemini Nano, streaming via `promptStreaming()`
- ✅ `Summarizer` — summarization with type/length/format options, streaming via `summarizeStreaming()`
- ✅ `Translator` — translation between languages (expert model)
- ✅ `LanguageDetector` — detect text language (expert model)

**Developer Trial:**
- ⚠️ `Writer` — long-form generation with `sharedContext`
- ⚠️ `Rewriter` — transformation of existing text with tone control
- ⚠️ `Proofreader` — grammar/clarity on a small expert model

## Chrome ↔ Android Bridge

```
Chrome Extension → WebSocket → Broker /bridge → Android BridgeClient
                                                      │
                                              LiteRT-LM inference
                                                      │
Chrome Extension ← WebSocket ← Broker /bridge ← Android (result + streaming)
```

- Chrome sends task via broker `/execute` → routed to Android → relayed via WebSocket bridge
- Android executes LiteRT-LM inference, streams chunks back to Chrome in real-time
- Final result delivered to Chrome side panel

## Cloud Escalation (Last Resort)

- ✅ Gemini 2.5 Flash via `google-genai` SDK (preferred — free tier)
- ✅ OpenAI via `openai` SDK (fallback)
- ✅ PII stripping before any cloud call
- ✅ Every escalation logged with reason, provider, latency
- ✅ Policy-gated: only triggers on low confidence, long reasoning, or explicit user request

## Android On-Device Inference

- ✅ LiteRT-LM v0.13+ — production inference with Engine/Conversation API
- ✅ FunctionGemma 270M — fast function calling with @Tool/@ToolParam annotations
- ✅ Gemma 4 E2B — larger model for complex tasks, GPU backend
- ✅ Model download flow — auto-download .litertlm files from HuggingFace
- ✅ Streaming inference — Flow-based token streaming

## Quick Start

```bash
# Install broker dependencies
pip install -r requirements.txt

# Copy env template (optional)
cp .env.example .env

# Run the Context Broker locally
uvicorn broker.main:app --reload --port 8000

# Test routing
curl -X POST http://localhost:8000/route \
  -H 'Content-Type: application/json' \
  -d '{"task": {"text": "summarize this article", "is_webpage_grounded": true, "is_short": true}}'

# Run tests
python -m pytest tests/ -q
```

## Configuration

All config is via environment variables (prefix `PCOS_`) or a `.env` file:

| Variable | Default | Description |
|---|---|---|
| `PCOS_BROKER_PORT` | 8000 | Broker listen port |
| `PCOS_PIECESOS_PORT` | 39300 | PiecesOS MCP port |
| `PCOS_BRIDGE_AUTH_TOKEN` | (empty) | WebSocket bridge auth token |
| `PCOS_LOG_JSON` | true | Structured JSON logging |
| `PCOS_LATENCY_TARGET_ROUTE_MS` | 50 | Route endpoint latency budget |

See `.env.example` for the full list.

## Philosophy

The intelligence isn't just the LLM. It's the routing. The Context Broker is deterministic — no reasoning, just: `collect → rank → compress → choose_model → choose_tool → execute`. Memory comes before inference. Cloud is the last resort, never the default.
