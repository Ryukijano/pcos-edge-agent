# PCOS — Personal Context Operating System

> A local-first hybrid AI agent across Chrome, Android, Pixel Watch, PiecesOS, and cloud LLMs.

## What is this?

PCOS is not a chatbot. It is a **context router** — a system that coordinates multiple specialized local AI models, memory systems, devices, and tools into one coherent cognitive runtime while keeping latency low and preserving privacy.

```
                    YOU
                     │
        ┌────────────┴────────────┐
        │                         │
   Chrome Extension         Android App
        │                         │
 Built-in AI APIs          LiteRT-LM
 Prompt API                Gemma (trained)
 Writer / Rewriter          Function Calling
 Summarizer / Classifier    AI Edge Gallery
 Proofreader                Local Tools
        │                         │
        └────────────┬────────────┘
                     │
            PiecesOS (Memory Cortex)
                     │
     LTM + MCP + Workflow Context
                     │
         Context Broker (service)
                     │
   ┌─────────────────┼─────────────────┐
   │                 │                  │
  Rank           Compress           Route
   │                                   │
LiteRT / Prompt API            Cloud LLM (escalation)
```

## Architecture Planes

| Plane | Surface | Role |
|---|---|---|
| Build | Antigravity / GitHub | Orchestration, agent wiring, Android CLI |
| Browser | Chrome Canary | Page-grounded NLP, extension side panel |
| Device | Android + LiteRT-LM | Private offline inference, function calling |
| Memory | PiecesOS | Long-Term Memory, MCP, workflow context |
| Ambient | Pixel Watch 4 | Lightweight context, smart replies, triggers |
| Cloud | Gemini / Anthropic / OpenAI | Overflow reasoning, long context |

## Routing Logic

```python
def route(task, context):
    if task.requires_private_action or task.is_offline:
        return "android_litert_functiongemma"
    if task.is_webpage_grounded and task.is_short:
        return "chrome_builtin_ai"
    if task.requires_personal_context:
        return "piecesos_memory_then_local"
    if task.is_long_reasoning or task.exceeds_local_limits:
        return "cloud_llm_escalation"
    return "local_first_default"
```

## Chrome APIs Enabled

- ✅ Prompt API (Gemma 4 backend)
- ✅ Multimodal Prompt API (image + audio)
- ✅ Writer / Rewriter / Proofreader
- ✅ Summarizer (speed/capability preference)
- ✅ Classifier
- ✅ LiteRT-LM backend
- ✅ Speculative decoding
- ✅ Sampling modes

## Repo Structure

```
pcos-edge-agent/
├── chrome-extension/       # Chrome side panel + Built-in AI API calls
├── android-app/            # LiteRT-LM, Gemma, FunctionGemma, AI Edge Gallery
├── context-broker/         # Context ranking, compression, routing service
├── piecesos-connector/     # PiecesOS MCP integration layer
├── watch-companion/        # Pixel Watch context events + smart reply triggers
├── cloud-escalation/       # Cloud LLM fallback logic (Gemini / OpenAI)
├── agent-skills/           # Reusable skills for Windsurf / Cursor
├── docs/
│   ├── architecture.md
│   ├── routing-spec.md
│   ├── context-schema.md
│   └── tickets.md
└── README.md
```

## Getting Started

See [docs/tickets.md](docs/tickets.md) for the 10-ticket implementation plan.

## Philosophy

The intelligence isn't just the LLM. It's the routing. Every request becomes a structured object with: modality, sensitivity, context sources, available tools, target surface, and escalation threshold. The system maximises context packing and action routing — not raw chat quality.
