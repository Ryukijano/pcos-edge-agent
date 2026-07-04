# PCOS — 10 Ticket Implementation Plan

---

## Ticket 1 — Validate local Chrome AI stack
**Surface:** Chrome Canary
**Goal:** Confirm all enabled flags work end-to-end.
**Tasks:**
- Call `Prompt API`, `Summarizer API`, `Classifier API`, `Writer API` from a simple HTML test page
- Confirm Gemma 4 backend is active (check `chrome://on-device-internals`)
- Confirm LiteRT-LM backend is serving
- Confirm speculative decoding is active
**Acceptance:** All 5 APIs return responses locally with no network requests.

---

## Ticket 2 — Chrome extension side panel scaffold
**Surface:** Chrome Extension
**Goal:** Build a persistent side panel that can call Chrome Built-in AI APIs.
**Tasks:**
- Scaffold Chrome Extension with Manifest V3
- Add Side Panel API integration
- Build basic UI: text input, model selector (Summarizer / Classifier / Prompt), output display
- Wire calls to Chrome's `window.ai` and task-specific APIs
**Acceptance:** Extension side panel opens, accepts text, calls local model, returns response.

---

## Ticket 3 — Android LiteRT-LM app scaffold
**Surface:** Android
**Goal:** Run Gemma locally on the phone via LiteRT-LM.
**Tasks:**
- Scaffold Android app (Kotlin)
- Add LiteRT-LM dependency
- Load trained Gemma model
- Test Engine → Session → inference pipeline
- Add FunctionGemma (270M) for fast function-call mode
**Acceptance:** On-device chat with Gemma running fully offline on OnePlus 11R.

---

## Ticket 4 — Context Broker service
**Surface:** Shared service (can start as a Python FastAPI)
**Goal:** Build the routing brain.
**Tasks:**
- Define `ContextObject` schema (see `docs/architecture.md`)
- Implement task classification: private/normal, short/long, transform/action/reasoning/retrieval
- Implement routing decision tree (see `docs/routing-spec.md`)
- Return `{surface, model, context_payload}` per task
**Acceptance:** Given a sample task + context, broker returns correct routing decision.

---

## Ticket 5 — PiecesOS connector
**Surface:** PiecesOS MCP
**Goal:** Expose PiecesOS Long-Term Memory to the Context Broker.
**Tasks:**
- Install and configure PiecesOS
- Enable MCP server integration in PiecesOS
- Write a connector that queries PiecesOS for relevant context given a task description
- Return top-k ranked memory items to the Context Broker
**Acceptance:** Broker receives recent workflow context from PiecesOS automatically.

---

## Ticket 6 — On-device function calling (Android)
**Surface:** Android + FunctionGemma + AI Edge Gallery
**Goal:** Run real tool calls locally on the phone.
**Tasks:**
- Integrate AI Edge Gallery function-calling SDK
- Define 3 local tools: `save_note`, `create_task`, `search_memory`
- Wire FunctionGemma to call them
- Test offline function calling with no network
**Acceptance:** Phone executes tool calls locally using FunctionGemma, no cloud required.

---

## Ticket 7 — Chrome → Android bridge
**Surface:** Chrome Extension + Android App
**Goal:** Pass context from browser to phone for action execution.
**Tasks:**
- Define a simple local API (localhost or WebSocket) between Chrome extension and Android app
- Chrome sends `{context, task}` → Android executes LiteRT-LM inference
- Android returns result → Chrome displays in side panel
**Acceptance:** User highlights text in Chrome → Android summarizes or acts on it locally.

---

## Ticket 8 — Pixel Watch companion
**Surface:** Wear OS / Pixel Watch 4
**Goal:** Add ambient context from the watch to the system.
**Tasks:**
- Build lightweight Wear OS companion app
- Send watch signals to Android: activity state, heart rate (with permission), timers
- Enable quick reply / confirmation flows from watch
- Pass watch context into `ContextObject.watch` field
**Acceptance:** Watch state is visible in Context Broker and influences routing decisions.

---

## Ticket 9 — Cloud escalation layer
**Surface:** Cloud
**Goal:** Add a clean, policy-gated cloud fallback.
**Tasks:**
- Add Gemini / OpenAI API as escalation target
- Implement escalation policy: only trigger if confidence < threshold, task is long, or user explicitly escalates
- Log every escalation event with reason
- Implement context stripping before cloud send
**Acceptance:** Cloud only fires when local models fail. Every escalation is logged with reason.

---

## Ticket 10 — Observability + agent-skills packaging
**Surface:** All
**Goal:** Make the system measurable and reusable.
**Tasks:**
- Add latency tracking per surface
- Add local-vs-cloud hit rate dashboard (simple)
- Package routing logic and context schema into `agent-skills` repo
- Write a clean README that explains the PCOS philosophy
- Optional: publish a Hugging Face Space demo of the Context Broker
**Acceptance:** Can answer: what % of tasks stayed local? Which surface was slowest?

---

## Build Order
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

Tickets 1–4 can be done this week.
Tickets 5–7 complete the MVP.
Tickets 8–10 make it serious.
