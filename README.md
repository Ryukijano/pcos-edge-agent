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
| Browser | Chrome 138+ | Page-grounded NLP transforms, side panel UI |
| Device | Android + LiteRT-LM | Private offline inference, function calling |
| Memory | PiecesOS | Episodic LTM, MCP, workflow context |
| Ambient | Pixel Watch 4 | Lightweight context signals, quick actions |
| Cloud | Gemini / OpenAI | Overflow reasoning, long context only |

## On-Device Models (LiteRT-LM)

| Model | Size | Backend | Prefill (tk/s) | Decode (tk/s) | Use Case |
|---|---|---|---|---|---|
| FunctionGemma 270M | 289MB | CPU | 2238 | 154 | Function calling, tool use |
| Gemma 4 E2B (2.3B) | 2.58GB | GPU | 3808 | 52 | General chat, transforms |
| Gemma 4 E4B (4.5B) | 3.65GB | GPU | 1293 | 22 | Complex reasoning, multimodal |

*Benchmarks from Samsung S26 Ultra. Adreno 730 (OnePlus 11R) uses OpenCL GPU backend with similar decode throughput. MTP/speculative decoding enabled for E2B/E4B. Apple Metal supported via LiteRT-LM Swift APIs.*

## Routing Policy

```python
def route(task):
    if task.sensitivity == "private" or task.is_offline:
        return "android_litert_gemma_e4b" if task.type == "reasoning" else "android_litert_gemma_e2b"
    if task.modality in ("image", "audio") and not task.is_webpage_grounded:
        return "android_litert_gemma_e4b"  # multimodal
    if task.is_webpage_grounded and task.is_short and task.task_type == "transform":
        return "chrome_builtin_ai"  # Summarizer / Translator / etc.
    if task.requires_personal_context:
        return "piecesos_memory_then_local"
    if task.requires_action:
        return "android_litert_functiongemma"
    if task.exceeds_local_limits:
        return "cloud_llm_escalation"
    return "android_litert_gemma_e2b"  # default local
```

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
