# API Reference

## Endpoints

### POST /route

Route a task to the best surface without executing.

**Request:**
```json
{
  "task": {
    "text": "Summarize this article",
    "task_type": "transform",
    "is_short": true,
    "is_webpage_grounded": true
  },
  "context": {}
}
```

**Response:**
```json
{
  "surface": "chrome_builtin_ai",
  "chrome_api": "summarizer",
  "reason": "Short browser-grounded transform: Chrome summarizer API",
  "escalate_to_cloud": false,
  "context_payload": {},
  "tool_plan": [],
  "latency_target_ms": 500
}
```

### POST /execute

Route and build an execution plan.

**Request:** Same as `/route`

**Response:**
```json
{
  "decision": { ... },
  "plan": { ... }
}
```

### POST /context/compress

Compress a PCOSContext into a prompt prefix string.

**Request:**
```json
{
  "browser": { "url": "https://example.com", "page_title": "Example" }
}
```

### GET /health

Health check with dependency status and latency budgets.

**Response:**
```json
{
  "status": "ok",
  "service": "pcos-context-broker",
  "version": "0.3.0",
  "dependencies": { "piecesos": true, "database": true },
  "latency_budgets_ms": { "route": 50, "execute": 500, "chrome": 200, "android": 1000, "cloud": 3000 }
}
```

### GET /metrics

Request metrics: local hit rate, cloud escalation rate, per-surface breakdown.

### GET /memory

PiecesOS memory status and recent items.

### POST /memory/query

Query PiecesOS LTM for relevant memories.

**Request:**
```json
{ "query": "quantum computing research", "top_k": 5 }
```

### WS /bridge

WebSocket relay hub for Chrome ↔ Android communication.

**Message types:** `register`, `relay`, `result`, `ping`

## Surfaces

| Surface | Enum | Description |
|---|---|---|
| Chrome Built-in AI | `chrome_builtin_ai` | Browser-side AI APIs |
| Android FunctionGemma | `android_litert_functiongemma` | On-device function calling (270M, CPU) |
| Android Gemma 4 E2B | `android_litert_gemma_e2b` | On-device inference (2.3B, GPU+MTP) |
| Android Gemma 4 E4B | `android_litert_gemma_e4b` | On-device full inference (4.5B, GPU+MTP, multimodal) |
| PiecesOS Memory | `piecesos_memory_then_local` | LTM query then local |
| Cloud LLM | `cloud_llm_escalation` | Cloud overflow |

## Chrome APIs

| API | Enum | Use Case |
|---|---|---|
| Prompt | `prompt` | General NL instructions |
| Summarizer | `summarizer` | Summarization |
| Translator | `translator` | Translation |
| Language Detector | `language_detector` | Language detection |
| Writer | `writer` | Long-form generation |
| Rewriter | `rewriter` | Text transformation |
| Proofreader | `proofreader` | Grammar/correction |
