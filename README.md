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
| Browser | Chrome Canary | Page-grounded NLP transforms, side panel UI |
| Device | Android + LiteRT-LM | Private offline inference, function calling |
| Memory | PiecesOS | Episodic LTM, MCP, workflow context |
| Ambient | Pixel Watch 4 | Lightweight context signals, quick actions |
| Cloud | Gemini / OpenAI | Overflow reasoning, long context only |

## Routing Policy

```python
def route(task):
    if task.sensitivity == "private" or task.is_offline:
        return "android_litert_functiongemma"
    if task.is_webpage_grounded and task.is_short and task.task_type == "transform":
        return "chrome_builtin_ai"  # Summarizer / Classifier / Rewriter etc.
    if task.requires_personal_context:
        return "piecesos_memory_then_local"
    if task.requires_action:
        return "android_functiongemma"
    if task.exceeds_local_limits:
        return "cloud_llm_escalation"
    return "local_first_default"
```

## Chrome APIs Enabled

- ✅ Prompt API (Gemma 4 backend + LiteRT-LM)
- ✅ Multimodal Prompt API (image + audio)
- ✅ Summarizer API (speed / capability preference)
- ✅ Writer / Rewriter / Proofreader
- ✅ Classifier API
- ✅ Speculative decoding

## Quick Start

```bash
# Install broker dependencies
pip install -r requirements.txt

# Run the Context Broker locally
uvicorn broker.main:app --reload --port 8000

# Test routing
curl -X POST http://localhost:8000/route \
  -H 'Content-Type: application/json' \
  -d '{"task": {"text": "summarize this article", "is_webpage_grounded": true, "is_short": true}}'
```

## Implementation Plan

See [docs/tickets.md](docs/tickets.md) for all 10 tickets.

**This week:** Tickets 1–4 (validate Chrome stack, extension scaffold, Android app, Context Broker service)
**MVP:** Tickets 5–7 (PiecesOS memory, on-device function calling, Chrome↔Android bridge)
**Platform:** Tickets 8–10 (Pixel Watch, cloud escalation, observability)

## Philosophy

The intelligence isn't just the LLM. It's the routing. The Context Broker is deterministic — no reasoning, just: `collect → rank → compress → choose_model → choose_tool → execute`. Memory comes before inference. Cloud is the last resort, never the default.
