# PCOS Edge Agent — Codemap

> **Repo:** `Ryukijano/pcos-edge-agent` · **Total LOC:** ~5,300 · **Tests:** 52 passing

---

## Architecture Overview

```
                    ┌─────────────────────────────────────────────┐
                    │            PCOS Context Broker               │
                    │         (FastAPI · async · :8000)            │
                    │                                             │
                    │  ┌─────────┐  ┌─────────┐  ┌──────────┐    │
                    │  │  Route  │  │   Ops   │  │  Bridge  │    │
                    │  │ Router  │  │ Router  │  │  Router  │    │
                    │  └────┬────┘  └────┬────┘  └────┬─────┘    │
                    │       │            │            │           │
                    │  ┌────▼────────────▼────────────▼─────┐     │
                    │  │           _shared.py               │     │
                    │  │  (SQLite metrics · bridge clients) │     │
                    │  └───────────────────────────────────┘     │
                    └──────────┬──────────────────┬──────────────┘
                               │                  │
                    ┌──────────▼──────┐  ┌───────▼──────────┐
                    │  Chrome Extension│  │  Android App      │
                    │  (MV3 · side panel)│  (LiteRT-LM · Kotlin)
                    └──────────┬──────┘  └───────┬──────────┘
                               │                 │
                    ┌──────────▼─────┐  ┌───────▼──────────┐
                    │ Chrome Built-in │  │  Gemma 4 / FG    │
                    │ AI APIs (7)     │  │  on-device       │
                    └────────────────┘  └──────────────────┘
                                         ┌──────────────────┐
                    ┌────────────────┐   │  Pixel Watch      │
                    │  PiecesOS MCP  │   │  (Wear OS · tile) │
                    │  (port 39300)  │   └──────────────────┘
                    └────────────────┘
```

---

## Directory Tree (with LOC)

```
pcos-edge-agent/
├── broker/                          1,346 LOC — FastAPI context broker
│   ├── main.py                         52 — App factory, CORS, lifespan, router mount
│   ├── config.py                       56 — pydantic-settings (PCOS_ env prefix)
│   ├── logging.py                     118 — StructuredLogger (JSON, kwargs→extra)
│   │
│   ├── context/
│   │   └── context_schema.py          152 — TaskObject, PCOSContext, enums, prompt prefix
│   │
│   ├── router/
│   │   └── router.py                  193 — RoutingDecision, Surface, ChromeAPI enums
│   │                                      route() decision tree, _select_chrome_api()
│   │
│   ├── planner/
│   │   └── planner.py                 178 — ExecutionPlan, build_plan(), system prompts
│   │                                      _CHROME_API_PARAMS, FUNCTIONGEMMA_TOOLS
│   │
│   ├── policies/
│   │   ├── privacy.py                  81 — strip_pii(), is_safe_for_cloud() (7 PII patterns)
│   │   └── escalation.py               88 — log_escalation(), get_escalation_log()
│   │
│   └── routers/
│       ├── __init__.py                  1
│       ├── _shared.py                  90 — SQLite DB, record_metric(), bridge client registry
│       ├── route_router.py            155 — POST /route, POST /execute (routing + execution)
│       ├── ops_router.py               98 — GET /health, GET /metrics, GET /memory
│       └── bridge_router.py            84 — WS /bridge (WebSocket relay, auth, heartbeat)
│
├── apps/                            2,311 LOC — Client applications
│   ├── chrome-extension/             1,156 — Chrome MV3 extension
│   │   ├── manifest.json               41 — MV3 manifest, side panel, offscreen perm
│   │   ├── background.js              234 — Service worker, keepalive, context menus
│   │   ├── chrome_ai.js               125 — Built-in AI wrapper (7 APIs + streaming)
│   │   ├── sidepanel.html              78 — Side panel UI (input, routing badge, output)
│   │   ├── sidepanel.css              260 — Dark theme, gradients, animations, scrollbar
│   │   ├── sidepanel.js               223 — Panel logic, broker communication, API strip
│   │   ├── content.js                  15 — Content script for page context capture
│   │   ├── offscreen.html              21 — Offscreen doc for persistent WebSocket
│   │   └── validation.html            158 — Chrome AI availability validation page
│   │
│   ├── android/                        787 — Android app (Kotlin + LiteRT-LM)
│   │   ├── app/build.gradle.kts            — LiteRT-LM 0.13.1, Compose, lifecycle
│   │   └── app/src/main/java/com/pcos/edge/
│   │       ├── LiteRTManager.kt       266 — Engine/Conversation/ToolSet, streaming, tools
│   │       ├── BridgeClient.kt        182 — WebSocket client, exponential backoff
│   │       ├── PCOSService.kt          88 — Foreground service, model pre-download
│   │       ├── PCOSViewModel.kt       128 — MVVM state, download progress, output
│   │       └── MainActivity.kt        123 — Compose UI, conversation interface
│   │
│   └── watch/                          369 — Wear OS companion (Kotlin + Compose)
│       └── app/src/main/java/com/pcos/watch/
│           ├── HealthMonitor.kt        73 — MeasureClient heart rate streaming
│           ├── PhoneDataListenerService.kt 94 — Data Layer API, /pcos-context path
│           ├── PCOSTileService.kt     111 — Watch tile (HR, activity, broker status)
│           └── MainActivity.kt         91 — Compose for Wear OS UI
│
├── memory/                             50 — Memory connectors
│   └── pieces/
│       └── connector.py               178 — PiecesOS MCP client (port 39300, async httpx)
│
├── tests/                             434 — Test suite (52 tests)
│   ├── test_router.py                 247 — Unit: routing, Chrome APIs, privacy, planner
│   └── test_integration.py            187 — E2E: route→execute→plan, health, metrics
│
├── hf_space/                          222 — Hugging Face Space demo
│   ├── app.py                         189 — Gradio UI, routing visualization, examples
│   ├── Dockerfile                      17 — Python 3.11-slim, port 7860
│   └── requirements.txt                 6 — gradio, fastapi, uvicorn, pydantic
│
├── docs/                              767 — MkDocs Material documentation
│   ├── index.md                        46 — Landing page, Mermaid architecture diagram
│   ├── architecture.md                 95 — System architecture, surface descriptions
│   ├── routing-spec.md                 55 — Routing decision tree specification
│   ├── api-reference.md               118 — All endpoints, request/response examples
│   ├── configuration.md                58 — Environment variables, .env, logging
│   ├── android.md                      47 — LiteRT-LM, models, Tool Use API
│   ├── chrome-extension.md             38 — Built-in AI APIs, keepalive, build
│   ├── pixel-watch.md                  47 — Health Services, Data Layer, tile
│   ├── demo-video-script.md            69 — 2-min, 6-scene walkthrough script
│   └── tickets.md                     131 — Original 10-ticket plan
│
├── models/                             — Model documentation
│   ├── gemma/README.md                     — Gemma 4 model card
│   └── litert/README.md                    — LiteRT-LM integration guide
│
├── tools/                              — Tool stubs (future MCP integrations)
│   ├── android/__init__.py
│   ├── browser/__init__.py
│   ├── filesystem/__init__.py
│   └── mcp/__init__.py
│
├── .github/
│   ├── workflows/ci.yml               49 — CI: Python 3.11/3.12, ruff, pytest, import check
│   └── ISSUE_TEMPLATE/ticket.md           — GitHub issue template
│
├── mkdocs.yml                         63 — MkDocs Material config (nav, theme, plugins)
├── requirements.txt                      — Python deps (fastapi, pydantic, uvicorn, httpx)
├── .env.example                          — Config template (PCOS_ env vars)
├── .gitignore                            — Python/Android/Chrome/IDE exclusions
├── LICENSE                               — Apache 2.0
├── CONTRIBUTING.md                       — Contribution guidelines
├── CODE_OF_CONDUCT.md                    — Contributor Covenant
└── README.md                             — Project overview, quick start, architecture
```

---

## Module Dependency Graph

```
broker/main.py
  ├── broker/config.py          (get_settings → Settings)
  ├── broker/logging.py         (get_logger, setup_logging)
  │     └── broker/config.py
  ├── broker/routers/_shared.py (get_db, record_metric, _bridge_clients)
  │     └── broker/config.py
  ├── broker/routers/route_router.py
  │     ├── broker/config.py
  │     ├── broker/logging.py
  │     ├── broker/context/context_schema.py  (TaskObject, PCOSContext)
  │     ├── broker/router/router.py           (route, Surface, ChromeAPI)
  │     │     └── broker/context/context_schema.py
  │     ├── broker/planner/planner.py         (build_plan, ExecutionPlan)
  │     │     ├── broker/context/context_schema.py
  │     │     └── broker/router/router.py
  │     ├── broker/policies/escalation.py     (log_escalation)
  │     ├── broker/routers/_shared.py         (record_metric)
  │     └── memory/pieces/connector.py        (PiecesConnector)
  ├── broker/routers/ops_router.py
  │     ├── broker/config.py
  │     ├── broker/logging.py
  │     ├── broker/policies/escalation.py     (get_escalation_log)
  │     ├── broker/routers/_shared.py         (get_db, _db_lock)
  │     └── memory/pieces/connector.py
  └── broker/routers/bridge_router.py
        ├── broker/config.py
        ├── broker/logging.py
        └── broker/routers/_shared.py         (_bridge_clients)
```

---

## Routing Decision Tree

```
route(task, ctx)
│
├─ 1. is_private() OR is_offline()?
│     YES → ANDROID_FUNCTION_GEMMA
│
├─ 2. modality == IMAGE/AUDIO AND NOT is_webpage_grounded?
│     YES → ANDROID_FUNCTION_GEMMA
│
├─ 3. is_webpage_grounded AND is_short AND task_type == TRANSFORM?
│     YES → CHROME_BUILTIN_AI
│            └─ _select_chrome_api(text)
│               ├─ "summarize"     → SUMMARIZER
│               ├─ "translate"     → TRANSLATOR
│               ├─ "detect lang"   → LANGUAGE_DETECTOR
│               ├─ "rewrite"       → REWRITER
│               ├─ "proofread"     → PROOFREADER
│               ├─ "write"/"draft" → WRITER
│               └─ fallback        → PROMPT
│
├─ 4. requires_personal_context?
│     YES → PIECESOS_MEMORY_THEN_LOCAL
│
├─ 5. requires_action?
│     YES → ANDROID_FUNCTION_GEMMA
│
├─ 6. user_explicit_escalate?
│     YES → CLOUD_LLM_ESCALATION
│
├─ 7. exceeds_local_limits OR (task_type == REASONING AND NOT is_short)?
│     YES → CLOUD_LLM_ESCALATION (PII stripped)
│
└─ 8. DEFAULT
      ├─ is_webpage_grounded AND is_short → CHROME_BUILTIN_AI (PROMPT)
      └─ else → ANDROID_GEMMA_FULL
```

---

## API Endpoints

| Method | Path | Router | Purpose |
|--------|------|--------|---------|
| `POST` | `/route` | `route_router` | Route a task → RoutingDecision |
| `POST` | `/execute` | `route_router` | Route + execute → result + ExecutionPlan |
| `GET` | `/health` | `ops_router` | Health check + latency budgets |
| `GET` | `/metrics` | `ops_router` | Request metrics + local hit rate |
| `GET` | `/memory` | `ops_router` | PiecesOS memory status |
| `WS` | `/bridge` | `bridge_router` | Chrome ↔ Android relay |

---

## Data Flow: Chrome → Broker → Android

```
1. User types task in Chrome side panel
2. sidepanel.js → POST /route (broker)
3. route_router → route() → RoutingDecision
4. If Chrome: sidepanel.js → chrome_ai.js → Built-in AI API
5. If Android: sidepanel.js → WS /bridge → bridge_router → Android BridgeClient
6. Android: LiteRTManager → Gemma/FunctionGemma inference
7. Result → WS /bridge → Chrome side panel
8. Metrics recorded in SQLite via record_metric()
```

---

## Key Enums

### Surface (5 values)
`chrome_builtin_ai` · `android_litert_functiongemma` · `android_litert_gemma_full` · `piecesos_memory_then_local` · `cloud_llm_escalation`

### ChromeAPI (7 values)
`prompt` · `summarizer` · `translator` · `language_detector` · `writer` · `rewriter` · `proofreader`

### TaskType (4 values)
`transform` · `action` · `reasoning` · `retrieval`

### Sensitivity (3 values)
`public` · `personal` · `private`

---

## Configuration (Environment Variables)

| Variable | Default | Module |
|----------|---------|--------|
| `PCOS_BROKER_PORT` | `8000` | `config.py` |
| `PCOS_CORS_ORIGINS` | `["*"]` | `config.py` → `main.py` |
| `PCOS_PIECESOS_PORT` | `39300` | `config.py` → `connector.py` |
| `PCOS_BRIDGE_AUTH_TOKEN` | (empty) | `config.py` → `bridge_router.py` |
| `PCOS_LOG_JSON` | `true` | `config.py` → `logging.py` |
| `PCOS_LATENCY_TARGET_ROUTE_MS` | `50` | `config.py` → `ops_router.py` |

---

## Test Coverage

| File | Tests | What's Covered |
|------|-------|----------------|
| `test_router.py` | 37 | Routing decision tree, all 7 Chrome APIs, privacy/PII (7 patterns), context schema, planner |
| `test_integration.py` | 15 | E2E route→execute→plan, health, metrics, context compress, privacy flow |
| **Total** | **52** | All passing |
