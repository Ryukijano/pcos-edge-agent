# PCOS Architecture

## The Five Planes

### 1. Browser Plane — Chrome Canary

Chrome is the **browser intelligence surface**. It knows the current URL, selected text, DOM, tab groups, and browsing session. Its Built-in AI APIs operate on that context.

**Enabled APIs (Chrome 138+):**
- `Prompt API` — natural language instructions to Gemma 4 locally
- `Writer API` — long-form generation
- `Rewriter API` — transformation of existing text
- `Proofreader API` — grammar/clarity on a small expert model
- `Summarizer API` — summarization with speed/capability preference
- `Translator API` — translate text between languages
- `Language Detector API` — detect the language of input text

**Note:** Chrome Built-in AI runs on the LiteRT-LM backend with speculative decoding for Gemma 4. These are browser-level features, not separate APIs.

**Important constraint:** These APIs are NOT suitable for factual accuracy tasks. Use them for transform tasks (summarize, rewrite, classify, proofread), not knowledge retrieval.

### 2. Device Plane — Android + LiteRT-LM

Android is the **action brain**. It handles:
- Offline private inference via LiteRT-LM v0.13.1
- On-device function calling via FunctionGemma 270M (Mobile Actions fine-tune, CPU backend)
- Larger model tasks via Gemma 4 E2B (GPU backend with MTP/speculative decoding)
- Streaming inference via Kotlin Flow for real-time token output
- Camera, microphone, sensors, notifications, local tools

LiteRT-LM v0.13+ exposes production inference primitives: Engine, Conversation, shared model loading, KV cache reuse, GPU/NPU backend selection, streaming responses via Flow, and annotated ToolSet function calling.

**Models:**
| Model | Size | Backend | MTP | Purpose |
|-------|------|---------|-----|---------|
| FunctionGemma 270M (Mobile Actions) | 289 MB | CPU | No | Function calling, tool use |
| Gemma 4 E2B IT | 2.59 GB | GPU | Yes | General inference, streaming |

**GPU Acceleration:** Requires OpenCL native libraries (`libOpenCL.so`, `libOpenCL-car.so`, `libOpenCL-pixel.so`) declared in AndroidManifest. MTP (Multi-Token Prediction) via speculative decoding is universally recommended for GPU backends — significantly accelerates decode speeds.

### 3. Memory Plane — PiecesOS

PiecesOS is the **memory cortex**. It captures workflow context locally:
- Code snippets, browser activity, notes, application context
- Long-Term Memory (LTM) engine
- MCP server for integration with other surfaces
- Blended local / cloud model routing

Design principle: **Memory → AI**, not AI → Memory. Context should be pre-fetched and ranked before the LLM sees it.

### 4. Ambient Plane — Pixel Watch 4

The watch is a **micro-context node**, not a reasoning node.
- Contributes: heart rate, activity state, timers, quick voice inputs
- Triggers: notification actions, confirmations, quick replies
- LiteRT-LM powers on-device AI features (Smart Replies) on the watch via a smaller modular pipeline

### 5. Cloud Plane — Escalation Only

Cloud LLMs (Gemini, OpenAI, Anthropic) are invoked only when:
- Task exceeds local context window
- Multi-step planning requires deep reasoning
- Local model fails confidence check
- Task explicitly requires factual accuracy

---

## Context Schema

Every request becomes a structured object:

```json
{
  "browser": {
    "url": "...",
    "selection": "...",
    "tab_group": "..."
  },
  "android": {
    "calendar": "...",
    "notifications": "...",
    "battery": "...",
    "network": "..."
  },
  "watch": {
    "heart_rate": "...",
    "activity": "...",
    "current_timer": "..."
  },
  "memory": {
    "recent_projects": "...",
    "research": "...",
    "todos": "...",
    "papers": "..."
  },
  "task": {
    "modality": "text|image|audio",
    "sensitivity": "private|normal",
    "length": "short|long",
    "type": "transform|action|reasoning|retrieval",
    "escalation_threshold": 0.7
  }
}
```
