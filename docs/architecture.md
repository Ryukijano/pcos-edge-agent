# PCOS Architecture

## The Five Planes

### 1. Browser Plane — Chrome Canary

Chrome is the **browser intelligence surface**. It knows the current URL, selected text, DOM, tab groups, and browsing session. Its Built-in AI APIs operate on that context.

**Enabled APIs:**
- `Prompt API` — natural language instructions to Gemma 4 locally
- `Multimodal Prompt API` — adds image + audio inputs
- `Writer API` — long-form generation
- `Rewriter API` — transformation of existing text
- `Proofreader API` — grammar/clarity on a small expert model
- `Classifier API` — text classification on a small expert model
- `Summarizer API` — summarization with speed/capability preference
- `LiteRT-LM backend` — production-grade local inference runtime
- `Speculative decoding` — latency optimisation for Gemma 4

**Important constraint:** These APIs are NOT suitable for factual accuracy tasks. Use them for transform tasks (summarize, rewrite, classify, proofread), not knowledge retrieval.

### 2. Device Plane — Android + LiteRT-LM

Android is the **action brain**. It handles:
- Offline private inference via LiteRT-LM
- On-device function calling via FunctionGemma (270M, fast)
- Larger model tasks via AI Edge Gallery (Gemma 4 etc.)
- Camera, microphone, sensors, notifications, local tools

LiteRT-LM exposes production inference primitives: Engine, Session, shared model loading, KV cache reuse, multimodal encoders, session cloning, prompt caching.

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
