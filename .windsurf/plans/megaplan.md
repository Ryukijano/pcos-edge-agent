# PCOS Edge Agent — Comprehensive Megaplan

> **Status:** Draft for review — no implementation without explicit confirmation.
> **Date:** 2026-06-18
> **Scope:** Full audit findings + research-backed critique + prioritized implementation plan

---

## 1. Executive Summary

The PCOS core stack is structurally sound — the routing decision tree, Pydantic v2 schemas, privacy/escalation policies, and Chrome/Android integration points all follow the architectural vision. However, a thorough audit against **current** technology documentation (June 2026) reveals **15 critical issues**, **12 architectural gaps**, and **10 missing features** that must be addressed before the system is production-ready.

The most severe findings:
- **PiecesOS connector targets the wrong port and endpoints** (port 1000 vs real default 39300)
- **Chrome extension references a non-existent `window.ai.classifier` API** — Chrome has no classifier built-in AI
- **LiteRT-LM dependency is massively outdated** (0.2.1 vs current v0.13 with Gemma 4 + MTP)
- **Android BridgeClient blocks a thread with `Thread.sleep(3000)`** in `onClose`
- **No WebSocket keepalive in Chrome MV3 service worker** — connection will die after 30s inactivity
- **No CORS configuration** — Chrome extension fetch requests will be blocked

---

## 2. Audit Findings — Critical Bugs (P0)

### 2.1 PiecesOS Connector — Wrong Port and Endpoints

**File:** `@/home/ryukijano/work/PCOS/memory/pieces/connector.py:20-22`

**Current (wrong):**
```python
PIECES_MCP_BASE = "http://localhost:1000"
PIECES_SSE_ENDPOINT = "/mcp/sse"
PIECES_QUERY_ENDPOINT = "/mcp/query"
```

**Correct (per [PiecesOS MCP docs](https://docs.pieces.app/products/mcp/mcp-remote)):**
```python
PIECES_MCP_BASE = "http://localhost:39300"
PIECES_SSE_ENDPOINT = "/model_context_protocol/2024-11-05/sse"
PIECES_QUERY_ENDPOINT = "/model_context_protocol/2025-03-26/mcp"  # Streamable HTTP
PIECES_HEALTH_ENDPOINT = "/.well-known/version"
```

**Impact:** Every PiecesOS query silently fails. The graceful degradation masks this — it looks like PiecesOS is "just not running" when the connector is hitting the wrong port.

**Fix:** Update all endpoint constants. Add proper health check via `/.well-known/version`. The query mechanism should use MCP tool calling (`ask_pieces_ltm`), not a raw POST to `/mcp/query`.

---

### 2.2 Chrome Extension — Non-Existent `window.ai.classifier` API

**Files:**
- `@/home/ryukijano/work/PCOS/apps/chrome-extension/chrome_ai.js:50-55`
- `@/home/ryukijano/work/PCOS/apps/chrome-extension/sidepanel.js:57`
- `@/home/ryukijano/work/PCOS/broker/router/router.py:29` (`ChromeAPI.CLASSIFIER`)
- `@/home/ryukijano/work/PCOS/broker/router/router.py:52` (`_CLASSIFIER_KEYWORDS`)
- `@/home/ryukijano/work/PCOS/broker/planner/planner.py:57`

**Per [Chrome Built-in AI docs](https://developer.chrome.com/docs/ai/built-in-apis) (June 2026):**

| API | Chrome Status |
|---|---|
| Summarizer | ✅ Stable (Chrome 138) |
| Language Detector | ✅ Stable (Chrome 138) |
| Translator | ✅ Stable (Chrome 138) |
| Writer | 🔄 Developer trial (origin trial) |
| Rewriter | 🔄 Developer trial (origin trial) |
| Proofreader | 🔄 Developer trial (origin trial) |
| Prompt API | ✅ Stable for Extensions (Chrome 138) |
| **Classifier** | **❌ Does not exist** |
| **Multimodal Prompt** | **❌ Not a built-in API** |

**Impact:** `ChromeAI.classify()` will throw at runtime. The routing tree has a branch for `ChromeAPI.CLASSIFIER` that can never execute successfully. The test `test_classify_routes_to_classifier` passes in unit tests but will fail at runtime.

**Fix:**
1. Remove `ChromeAPI.CLASSIFIER` and `_CLASSIFIER_KEYWORDS` from router
2. Remove `classify()` from `chrome_ai.js`
3. Remove classifier badge from `sidepanel.html` and `sidepanel.js`
4. Remove classifier test from `test_router.py`
5. **Add** `ChromeAPI.TRANSLATOR` and `ChromeAPI.LANGUAGE_DETECTOR` (both stable since Chrome 138)
6. Add `translator()` and `detectLanguage()` to `chrome_ai.js`

---

### 2.3 Chrome Extension — Non-Existent `ChromeAPI.MULTIMODAL_PROMPT`

**File:** `@/home/ryukijano/work/PCOS/broker/router/router.py:33`

Chrome does not expose a "Multimodal Prompt API" under `window.ai`. The Prompt API (`window.ai.languageModel`) is text-only. Image/audio multimodal inference is handled by LiteRT-LM on Android, not Chrome.

**Fix:** Remove `ChromeAPI.MULTIMODAL_PROMPT`. The router already correctly routes multimodal non-web tasks to Android (step 2 in the decision tree). The `_select_chrome_api` fallback to `MULTIMODAL_PROMPT` for image/audio is dead code that would fail at runtime.

---

### 2.4 LiteRT-LM Dependency — Massively Outdated

**File:** `@/home/ryukijano/work/PCOS/apps/android/app/build.gradle.kts:46`

**Current:** `implementation("com.google.ai.edge.litert:litert-lm:0.2.1")`
**Should be:** `implementation("com.google.ai.edge.litert:litert-lm:0.13.0")` (or latest)

Per [LiteRT-LM v0.13](https://github.com/google-ai-edge/LiteRT-LM):
- Gemma 4 12B support
- MTP (Multi-Token Prediction) drafters for up to 3x speedup
- Agent skill support for Android
- Tool Use / function calling API improvements
- OpenAI API compatible server in CLI

**Fix:** Update dependency version. Update `LiteRTManager.kt` to use the actual v0.13 API (Engine, Session, ToolConfig). Enable speculative decoding via `--enable-speculative-decoding=true`.

---

### 2.5 Android BridgeClient — `Thread.sleep(3000)` Blocks Thread

**File:** `@/home/ryukijano/work/PCOS/apps/android/app/src/main/java/com/pcos/edge/BridgeClient.kt:128`

```kotlin
override fun onClose(code: Int, reason: String?, remote: Boolean) {
    clientId = null
    Thread.sleep(3000)  // ← BLOCKS THE WEBSOCKET THREAD
    connect()
}
```

**Impact:** Blocks the WebSocket callback thread for 3 seconds. If multiple disconnects happen, threads pile up. No exponential backoff.

**Fix:** Use a coroutine with exponential backoff:
```kotlin
override fun onClose(code: Int, reason: String?, remote: Boolean) {
    clientId = null
    reconnectWithBackoff()
}

private fun reconnectWithBackoff(attempt: Int = 0) {
    val delay = minOf(3000 * (2 shl attempt), 30000) // 3s, 6s, 12s, 24s, 30s cap
    mainScope.launch {
        delay(delay)
        if (!isConnected()) connect()
    }
}
```

---

### 2.6 Chrome MV3 Service Worker — No WebSocket Keepalive

**File:** `@/home/ryukijano/work/PCOS/apps/chrome-extension/background.js:118-143`

Per [Chrome docs](https://developer.chrome.com/docs/extensions/how-to/web-platform/websockets): Chrome 116+ allows WebSocket activity to extend service worker lifetime, but **only if messages are exchanged within the 30s activity window**. The current code connects but never sends keepalive pings.

**Impact:** After 30 seconds of no WebSocket traffic, the service worker is killed and the WebSocket closes. The `onclose` handler tries to reconnect after 3s, but this creates a connect/disconnect loop.

**Fix:** Add a `keepAlive()` interval that sends a ping every 20 seconds:
```javascript
function keepAlive() {
  const keepAliveIntervalId = setInterval(() => {
    if (bridgeSocket && bridgeSocket.readyState === WebSocket.OPEN) {
      bridgeSocket.send(JSON.stringify({ type: 'ping' }));
    } else {
      clearInterval(keepAliveIntervalId);
    }
  }, 20 * 1000);
}
```
Call `keepAlive()` in `bridgeSocket.onopen`. Also set `minimum_chrome_version: "116"` in manifest.json.

---

### 2.7 No CORS Configuration on Broker

**File:** `@/home/ryukijano/work/PCOS/broker/main.py`

The Chrome extension makes `fetch()` calls to `http://localhost:8000` but the broker has no CORS middleware. While Chrome extensions with `host_permissions` can bypass CORS, the current manifest.json doesn't declare host permissions for localhost.

**Fix:** Add `CORSMiddleware` to the FastAPI app AND add `host_permissions` to manifest.json:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```
```json
"host_permissions": ["http://localhost:8000/*"]
```

---

### 2.8 Duplicate Cloud Escalation Code

**Files:**
- `@/home/ryukijano/work/PCOS/broker/policies/escalation.py` — proper Pydantic-based implementation
- `@/home/ryukijano/work/PCOS/models/cloud/escalation.py` — older stub with `datetime.utcnow()` (deprecated)

The broker uses `broker/policies/escalation.py` (correct). The `models/cloud/escalation.py` is a stale duplicate with a TODO comment referencing "T9" and uses deprecated `datetime.utcnow()`.

**Fix:** Delete `models/cloud/escalation.py` or refactor it to import from `broker/policies/escalation.py`. Update any references.

---

### 2.9 Architecture Docs — Reference Non-Existent APIs

**File:** `@/home/ryukijano/work/PCOS/docs/architecture.md:9-18`

Lists "Classifier API" and "Multimodal Prompt API" as enabled Chrome APIs. Also lists "LiteRT-LM backend" and "Speculative decoding" as Chrome features — these are Android/desktop features, not Chrome Built-in AI.

**Fix:** Update docs to reflect actual Chrome Built-in AI API surface (see section 2.2 table).

---

### 2.10 Routing Spec — References Classifier API

**File:** `@/home/ryukijano/work/PCOS/docs/routing-spec.md:33`

Lists "Classify intent → Classifier API" in the API selection table. Also lists "Image/audio task → Multimodal Prompt API".

**Fix:** Remove classifier and multimodal prompt rows. Add "Translate text → Translator API" and "Detect language → Language Detector API".

---

### 2.11 `models/prompt-api/chrome_ai.js` — ES Module Export in Non-Module File

**File:** `@/home/ryukijano/work/PCOS/models/prompt-api/chrome_ai.js:146`

Has `export default ChromeAI;` but is loaded via `<script>` tag (not `type="module"`). This will cause a syntax error in the browser.

The extension copy at `apps/chrome-extension/chrome_ai.js` was already fixed (no export). But the canonical copy still has the export and references non-existent classifier API.

**Fix:** Remove the export from the canonical copy. Remove `classify()`. Add `translate()` and `detectLanguage()`. Sync both copies or use a build step.

---

### 2.12 Planner — Convoluted Surface/ChromeAPI Lookups

**File:** `@/home/ryukijano/work/PCOS/broker/planner/planner.py:140-143`

```python
system_prompt = _SYSTEM_PROMPTS.get(
    Surface(surface) if surface not in [s.value for s in Surface] else Surface(surface),
    "",
)
```

This expression `Surface(surface) if surface not in [s.value for s in Surface] else Surface(surface)` is a tautology — both branches do the same thing. The list comprehension `[s.value for s in Surface]` is computed every call.

**Fix:** Simplify to:
```python
try:
    system_prompt = _SYSTEM_PROMPTS.get(Surface(surface), "")
except ValueError:
    system_prompt = ""
```
Same pattern for ChromeAPI lookup at line 157.

---

### 2.13 SQLite — `check_same_thread=False` Without Locking

**File:** `@/home/ryukijano/work/PCOS/broker/main.py:38`

```python
conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
```

With `check_same_thread=False`, concurrent writes from async endpoints can corrupt data. FastAPI runs sync endpoints in a threadpool, so multiple threads can hit the DB simultaneously.

**Fix:** Use `aiosqlite` for async access, or wrap writes in a `threading.Lock`, or use a connection-per-request pattern. For a production system, switch to async DB (aiosqlite or asyncpg with PostgreSQL).

---

### 2.14 Sync Endpoints in FastAPI

**File:** `@/home/ryukijano/work/PCOS/broker/main.py:154,190,240,246,251`

All endpoints are `def` (sync), not `async def`. Sync endpoints run in a threadpool, which is fine for CPU-bound work but the endpoints call `httpx.get()` (blocking I/O) in the PiecesOS connector. This blocks a threadpool thread for the duration of each PiecesOS query.

**Fix:** Make endpoints `async def`. Use `httpx.AsyncClient` for PiecesOS queries. The router itself is CPU-bound and can stay sync or be wrapped in `run_in_executor`.

---

### 2.15 `datetime.utcnow()` Deprecation

**File:** `@/home/ryukijano/work/PCOS/models/cloud/escalation.py:38`

`datetime.utcnow()` is deprecated in Python 3.12+. Should use `datetime.now(timezone.utc)`.

**Fix:** Already fixed in `broker/policies/escalation.py`. Delete the stale `models/cloud/escalation.py` file.

---

## 3. Architecture Refactoring (P1)

### 3.1 Modularize with APIRouter

**Current:** All endpoints in `broker/main.py` (368 lines).
**Target:** Split into routers:

```
broker/
├── main.py              # App factory, lifespan, CORS
├── routers/
│   ├── route.py         # /route, /execute
│   ├── context.py       # /context/compress
│   ├── memory.py        # /memory, /memory/query
│   ├── metrics.py       # /metrics, /health
│   └── bridge.py        # /bridge WebSocket
```

### 3.2 Config Management with pydantic-settings

**Current:** Hardcoded URLs and paths throughout the codebase.
**Target:** Single `Settings` class:

```python
class Settings(BaseSettings):
    broker_host: str = "0.0.0.0"
    broker_port: int = 8000
    piecesos_base_url: str = "http://localhost:39300"
    piecesos_sse_endpoint: str = "/model_context_protocol/2024-11-05/sse"
    db_path: str = "data/pcos_metrics.db"
    ws_ping_interval: int = 30
    ws_ping_timeout: int = 10
    model_config = SettingsConfigDict(env_prefix="PCOS_", env_file=".env")
```

### 3.3 WebSocket Bridge — Heartbeat and Auth

**Current:** No heartbeat, no auth, no message schema validation.
**Target:**
- Uvicorn-level `ws_ping_interval=30, ws_ping_timeout=10` (per [FastAPI WebSocket best practices](https://websocket.org/guides/frameworks/fastapi/))
- First-message auth pattern: client sends `{"type": "auth", "token": "..."}` within 5s
- JSON schema validation on all incoming messages
- Connection manager class to track clients by role (chrome/android)

### 3.4 Streaming SSE Endpoint for LLM Output

**Current:** All responses are synchronous — wait for full inference, then return.
**Target:** Add `POST /execute/stream` that returns `StreamingResponse` with SSE format:

```
data: {"type": "routing", "surface": "chrome_builtin_ai"}
data: {"type": "chunk", "content": "The summary..."}
data: {"type": "done", "latency_ms": 340}
```

This enables the Chrome extension to show progressive output and the Android app to display tokens as they arrive.

### 3.5 Connection Pooling for PiecesOS Connector

**Current:** Creates a new `httpx.Client` per query call.
**Target:** Use a shared `httpx.AsyncClient` with connection pooling:

```python
class PiecesConnector:
    def __init__(self, base_url: str, settings: Settings):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(3.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        )
```

### 3.6 Proper Logging Configuration

**Current:** Basic `logging.getLogger()` calls, no structured logging.
**Target:** Structured JSON logging with `structlog` or Python's `logging` with a JSON formatter:

```python
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
)
```

### 3.7 Error Handling Middleware

**Current:** No global error handler. Exceptions return FastAPI's default 500.
**Target:** Add exception handlers:

```python
@app.exception_handler(PiecesOSUnavailable)
async def piecesos_handler(req, exc): return JSONResponse(503, {"error": "piecesos_unavailable"})

@app.exception_handler(RoutingError)
async def routing_handler(req, exc): return JSONResponse(400, {"error": str(exc)})
```

---

## 4. Feature Additions (P2)

### 4.1 Add Translator and Language Detector APIs

Per Chrome 138 stable release, these are production-ready:

**Router changes:**
- Add `ChromeAPI.TRANSLATOR` and `ChromeAPI.LANGUAGE_DETECTOR`
- Add keyword tables: `_TRANSLATOR_KEYWORDS = {"translate", "translation"}`, `_LANGUAGE_DETECTOR_KEYWORDS = {"detect language", "what language"}`
- Add routing branches in the transform section

**chrome_ai.js:**
```javascript
async translate(text, targetLang) {
  const translator = await window.ai.translator.create({ sourceLanguage: 'auto', targetLanguage: targetLang });
  const result = await translator.translate(text);
  translator.destroy();
  return result;
}

async detectLanguage(text) {
  const detector = await window.ai.languageDetector.create();
  const result = await detector.detect(text);
  detector.destroy();
  return result;
}
```

**Side panel:** Add badges for Translator and Language Detector.

---

### 4.2 Chrome Extension — Offscreen Document for WebSocket Keepalive

Per [MV3 lifecycle docs](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle), the service worker has a hard 5-minute maximum lifetime. Even with WebSocket keepalive pings every 20s, Chrome can kill the worker at the 300-second mark.

**Solution:** Use an offscreen document that sends `chrome.runtime.sendMessage({ keepAlive: true })` to the service worker every 20s. This is the recommended pattern for persistent background work in MV3.

```javascript
// offscreen.html → offscreen.js
setInterval(() => {
  chrome.runtime.sendMessage({ type: 'keepalive' });
}, 20 * 1000);
```

Add `offscreen.html` and `offscreen.js` to the extension. Create the offscreen document in `background.js` on startup.

---

### 4.3 Android — Exponential Backoff for Bridge Reconnection

Replace the fixed 3s delay with exponential backoff:
- Attempt 1: 3s
- Attempt 2: 6s
- Attempt 3: 12s
- Attempt 4: 24s
- Cap: 30s
- Reset on successful connection

---

### 4.4 Android — Use OkHttp for HTTP Requests

**Current:** `java.net.HttpURLConnection` (verbose, no connection pooling, deprecated patterns).
**Target:** Add OkHttp dependency and use it for broker communication. Or use Ktor client for idiomatic Kotlin coroutines support.

---

### 4.5 Android — LiteRT-LM v0.13 API Integration

Update `LiteRTManager.kt` to use the actual v0.13 API:

```kotlin
// Engine config with MTP drafters
val engineConfig = Engine.Config(
    modelPath = modelPath,
    enableSpeculativeDecoding = true,
)
engine = Engine.create(engineConfig)

// Session with system prompt
val sessionConfig = Session.Config(
    systemPrompt = "You are a helpful on-device assistant.",
)
session = engine.createSession(sessionConfig)

// Function calling
val toolConfig = Session.Config(
    tools = tools.map { it.toJsonSchema() },
)
session = engine.createSession(toolConfig)
val result = session.generate(prompt)
```

---

### 4.6 Proactive Suggestion Engine

The UI has a suggestion chip (`suggestion-chip` in HTML) but no logic generates suggestions. Add a lightweight suggestion engine in the broker:

```python
@app.post("/suggest")
def suggest(body: dict):
    """Generate proactive suggestions based on context."""
    ctx = PCOSContext(**body.get("context", {}))
    suggestions = []
    if ctx.browser.selection:
        suggestions.append({"text": f"Summarize: {ctx.browser.selection[:50]}...", "task": "summarize"})
    if ctx.memory.todos:
        suggestions.append({"text": f"You have {len(ctx.memory.todos)} pending todos", "task": "review"})
    return {"suggestions": suggestions[:3]}
```

---

### 4.7 Cloud Escalation — Wire to Real Provider

**Current:** `models/cloud/escalation.py` has `# TODO: wire to Gemini / OpenAI SDK` and returns `None`.
**Target:** Implement actual cloud LLM call with:
- Gemini API (default, free tier available)
- OpenAI as fallback
- Response caching to avoid duplicate calls
- Token counting and budget tracking

---

### 4.8 Embeddings Layer for Semantic Search

**File:** `@/home/ryukijano/work/PCOS/memory/embeddings/__init__.py` — placeholder

Add a local embeddings layer using sentence-transformers or LiteRT for semantic search when PiecesOS is unavailable. This enables the broker to do semantic matching over local context even without PiecesOS running.

---

### 4.9 Watch Context Integration

The `WatchContext` schema exists but no Wear OS app feeds it. Create a minimal Wear OS companion app:
- Sends heart rate, activity state, timer status to the Android app
- Android app forwards to broker via the bridge
- Broker includes watch context in routing decisions (e.g., if user is running, prefer short audio responses)

---

### 4.10 Tool Execution Layer

**Current:** FunctionGemma tool declarations exist but tool execution is stubbed.
**Target:** Implement actual tool execution on Android:
- `save_note` → save to local SQLite/Room database
- `create_task` → save to task manager
- `search_memory` → query PiecesOS via broker

---

## 5. Production Readiness (P3)

### 5.1 Docker Containerization

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "broker.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws-ping-interval", "30", "--ws-ping-timeout", "10"]
```

Add `docker-compose.yml` for broker + optional Redis for future scale-out.

---

### 5.2 Integration Tests

**Current:** Only unit tests for router logic (34 tests).
**Target:** Add integration tests:

```
tests/
├── test_router.py          # existing unit tests
├── test_planner.py         # planner unit tests
├── test_privacy.py         # privacy policy tests
├── test_escalation.py      # escalation policy tests
├── test_connector.py       # PiecesOS connector tests (mocked)
├── test_broker_api.py      # FastAPI TestClient integration tests
├── test_bridge_ws.py       # WebSocket bridge integration tests
└── test_e2e.py             # end-to-end: route → plan → execute
```

---

### 5.3 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: PCOS CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v --cov=broker --cov-report=xml
      - run: python -c "from broker.main import app; print('Import OK')"
```

---

### 5.4 Rate Limiting

Add `slowapi` middleware for rate limiting:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/route")
@limiter.limit("60/minute")
async def route_task(request: Request, req: RouteRequest): ...
```

---

### 5.5 Health Check Improvements

Add dependency checks to `/health`:
```python
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "dependencies": {
            "piecesos": _pieces_connector.is_available(),
            "database": _db_healthcheck(),
        },
        "uptime_seconds": time.time() - _start_time,
    }
```

---

## 6. Research-Backed Critique

### 6.1 Chrome Built-in AI — Reality vs Design

**Design assumption:** Chrome has 7 built-in AI APIs (Prompt, Summarizer, Writer, Rewriter, Proofreader, Classifier, Multimodal Prompt).

**Reality (June 2026):** Chrome has **6** stable/trial APIs:
- ✅ Prompt API (stable for extensions, origin trial for web)
- ✅ Summarizer (stable)
- ✅ Translator (stable) — **missing from PCOS**
- ✅ Language Detector (stable) — **missing from PCOS**
- 🔄 Writer (developer trial)
- 🔄 Rewriter (developer trial)
- 🔄 Proofreader (developer trial)
- ❌ Classifier — **does not exist**
- ❌ Multimodal Prompt — **not a Chrome API**

**Recommendation:** Remove classifier/multimodal references everywhere. Add Translator and Language Detector. Update docs. The routing spec's API selection table needs a complete rewrite.

### 6.2 LiteRT-LM — Major Version Gap

**Design assumption:** LiteRT-LM 0.2.1 with basic Engine/Session API.

**Reality:** LiteRT-LM v0.13 (June 2026):
- Gemma 4 12B support (E2B, E4B variants)
- MTP drafters for 3x inference speedup
- Agent skill support for Android
- Swift and JavaScript APIs (early preview)
- OpenAI API compatible server in CLI
- Production-proven in Chrome, Chromebook Plus, Pixel Watch

**Recommendation:** Update dependency to v0.13. Rewrite `LiteRTManager.kt` with actual API. Enable MTP speculative decoding. Update model paths to use HuggingFace litert-community repos (e.g., `litert-community/gemma-4-E4B-it-litert-lm`).

### 6.3 PiecesOS MCP — Protocol Mismatch

**Design assumption:** PiecesOS exposes `/health`, `/mcp/sse`, `/mcp/query` on port 1000.

**Reality:** PiecesOS exposes MCP on port 39300:
- SSE: `/model_context_protocol/2024-11-05/sse`
- Streamable HTTP: `/model_context_protocol/2025-03-26/mcp`
- Health: `/.well-known/version`
- The query mechanism uses MCP tool calling (`ask_pieces_ltm`), not raw POST

**Recommendation:** Rewrite connector to use proper MCP protocol. Use `mcp` Python SDK or implement MCP tool calling over SSE. The connector should:
1. Connect to SSE endpoint
2. List available tools
3. Call `ask_pieces_ltm` with the query
4. Parse structured results

### 6.4 FastAPI WebSocket — Missing Operational Practices

**Design assumption:** Basic WebSocket accept/receive/send loop.

**Reality (per best practices):**
- Need heartbeat (Uvicorn `ws_ping_interval=30, ws_ping_timeout=10`)
- Need auth (first-message pattern or query param token)
- Need connection manager with role-based tracking
- Need message schema validation
- Need proper cleanup on disconnect (cancel background tasks)
- For multi-worker: need Redis pub/sub for cross-worker relay

**Recommendation:** Implement all of the above. For now, single worker is fine. Add Uvicorn ping config as the lowest-effort fix.

### 6.5 Chrome MV3 Service Worker — Lifecycle Hostility

**Design assumption:** WebSocket in service worker stays connected indefinitely.

**Reality:**
- 30-second inactivity timer → service worker killed
- 5-minute hard maximum lifetime → service worker killed regardless of activity
- WebSocket traffic alone does NOT reset the 30s timer (only extension API events do)
- Chrome 116+ allows WebSocket activity to extend lifetime, but requires messages within 30s window
- The 5-minute max lifetime still applies even with WebSocket keepalive

**Recommendation:**
1. Add 20s keepalive interval (sends ping via WebSocket)
2. Add offscreen document that sends `chrome.runtime.sendMessage` every 20s (resets the 30s timer via extension API event)
3. Set `minimum_chrome_version: "116"` in manifest.json
4. Design for graceful reconnection after 5-minute kill
5. Store bridge client_id in `chrome.storage.session` to survive restarts

### 6.6 Privacy Architecture — Strong but Needs Tests

**Current state:** PII stripping covers email, phone, IP, API keys, credit cards, bracketed names. Cloud escalation always strips. This is good.

**Gaps:**
- No SSN pattern
- No street address pattern
- No test for `strip_context_for_cloud` (only `strip_pii` is tested)
- No regression test ensuring cloud payloads are always stripped
- No audit trail of what was stripped (for debugging)

**Recommendation:** Add SSN and address patterns. Add tests for `strip_context_for_cloud`. Add a `stripped_fields` list to the payload so the cloud call knows what was redacted.

---

## 7. Implementation Order

### Phase A — Critical Bug Fixes (P0)
**Estimated effort:** 4-6 hours

| # | Task | Files | Priority |
|---|---|---|---|
| A1 | Fix PiecesOS connector endpoints | `connector.py` | Critical |
| A2 | Remove ChromeAPI.CLASSIFIER everywhere | `router.py`, `planner.py`, `chrome_ai.js`, `sidepanel.js`, `sidepanel.html`, `test_router.py` | Critical |
| A3 | Remove ChromeAPI.MULTIMODAL_PROMPT | `router.py`, `planner.py` | Critical |
| A4 | Update LiteRT-LM dependency to v0.13 | `build.gradle.kts` | Critical |
| A5 | Fix Android BridgeClient Thread.sleep | `BridgeClient.kt` | Critical |
| A6 | Add WebSocket keepalive to Chrome background.js | `background.js`, `manifest.json` | Critical |
| A7 | Add CORS middleware + host_permissions | `main.py`, `manifest.json` | Critical |
| A8 | Delete stale `models/cloud/escalation.py` | `models/cloud/escalation.py` | High |
| A9 | Update architecture docs | `architecture.md`, `routing-spec.md`, `tickets.md` | High |
| A10 | Fix planner tautological lookups | `planner.py` | Medium |
| A11 | Fix SQLite thread safety | `main.py` | Medium |
| A12 | Make endpoints async | `main.py`, `connector.py` | Medium |
| A13 | Sync chrome_ai.js copies | `chrome_ai.js` (both) | Medium |
| A14 | Fix `datetime.utcnow()` | `models/cloud/escalation.py` (delete) | Low |
| A15 | Add Translator/Language Detector APIs | `router.py`, `planner.py`, `chrome_ai.js`, `sidepanel.html` | High |

### Phase B — Architecture Refactoring (P1)
**Estimated effort:** 8-12 hours

| # | Task | Priority |
|---|---|---|
| B1 | Split main.py into APIRouter modules | High |
| B2 | Add pydantic-settings config | High |
| B3 | Add WebSocket heartbeat (Uvicorn config) | High |
| B4 | Add WebSocket auth (first-message pattern) | Medium |
| B5 | Add SSE streaming endpoint | Medium |
| B6 | Connection pooling for PiecesOS | Medium |
| B7 | Structured logging | Low |
| B8 | Error handling middleware | Low |

### Phase C — Feature Additions (P2)
**Estimated effort:** 12-20 hours

| # | Task | Priority |
|---|---|---|
| C1 | Offscreen document for MV3 keepalive | High |
| C2 | Android exponential backoff | Medium |
| C3 | Android OkHttp/Ktor migration | Medium |
| C4 | LiteRT-LM v0.13 real API integration | High |
| C5 | Proactive suggestion engine | Low |
| C6 | Cloud escalation — real provider wiring | Medium |
| C7 | Local embeddings layer | Low |
| C8 | Wear OS companion app | Low |
| C9 | Tool execution layer on Android | Medium |

### Phase D — Production Readiness (P3)
**Estimated effort:** 6-10 hours

| # | Task | Priority |
|---|---|---|
| D1 | Dockerfile + docker-compose | Medium |
| D2 | Integration tests | High |
| D3 | CI/CD pipeline | Medium |
| D4 | Rate limiting | Low |
| D5 | Health check improvements | Medium |
| D6 | Privacy pattern additions + tests | Medium |

---

## 8. File Impact Summary

| File | Changes |
|---|---|
| `broker/main.py` | CORS, async endpoints, APIRouter split, settings, heartbeat config |
| `broker/router/router.py` | Remove CLASSIFIER/MULTIMODAL_PROMPT, add TRANSLATOR/LANGUAGE_DETECTOR |
| `broker/planner/planner.py` | Fix lookups, update ChromeAPI params, add translator params |
| `broker/context/context_schema.py` | No changes needed (schemas are correct) |
| `broker/policies/escalation.py` | No changes needed (correct) |
| `broker/policies/privacy.py` | Add SSN/address patterns, add `strip_context_for_cloud` tests |
| `memory/pieces/connector.py` | Fix endpoints (port 39300), MCP protocol, async client, connection pooling |
| `apps/chrome-extension/chrome_ai.js` | Remove classify(), add translate()/detectLanguage(), sync with canonical |
| `apps/chrome-extension/sidepanel.js` | Remove classifier badge, add translator/detector badges |
| `apps/chrome-extension/sidepanel.html` | Update API badges |
| `apps/chrome-extension/background.js` | Add keepalive, add offscreen document support |
| `apps/chrome-extension/manifest.json` | Add host_permissions, minimum_chrome_version, offscreen permission |
| `apps/android/app/build.gradle.kts` | Update LiteRT-LM to v0.13, add OkHttp |
| `apps/android/.../BridgeClient.kt` | Fix Thread.sleep, add exponential backoff, use OkHttp |
| `apps/android/.../LiteRTManager.kt` | Use real v0.13 API, enable MTP |
| `apps/android/.../PCOSService.kt` | Uncomment model loading |
| `docs/architecture.md` | Remove classifier/multimodal, add translator/detector |
| `docs/routing-spec.md` | Update API selection table |
| `docs/tickets.md` | Update to reflect current state |
| `tests/test_router.py` | Remove classifier test, add translator test |
| `models/cloud/escalation.py` | Delete (stale duplicate) |
| `models/prompt-api/chrome_ai.js` | Remove export, remove classify(), add translate() |
| `requirements.txt` | Add aiosqlite, structlog (optional) |

---

## 9. Open Questions for User

1. **PiecesOS port:** Is PiecesOS running on the default 39300, or a custom port? The connector should be configurable either way.

2. **Cloud LLM provider:** Which provider should we wire up for escalation? Gemini (free tier), OpenAI, or Anthropic? Need API key handling strategy.

3. **Chrome minimum version:** Should we require Chrome 138+ (Summarizer/Translator stable) or 116+ (WebSocket support)? Recommend 138+ for full API access.

4. **Android target devices:** Is the OnePlus 11R still the target? What about Pixel Watch 4 for the Wear OS companion?

5. **Authentication model:** Should the WebSocket bridge use a shared secret, JWT, or no auth (local network only)?

6. **Model download strategy:** Should the Android app download models from HuggingFace at first launch, or bundle them in the APK? (Gemma 4 E4B is ~4GB, too large for APK)

7. **Priority:** Should I proceed with Phase A (critical bug fixes) immediately after your confirmation, or do you want to review/adjust the plan first?
