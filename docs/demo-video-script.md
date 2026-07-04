# PCOS Demo Video Script

**Duration:** ~2 minutes
**Format:** Screen recording + voiceover

---

## Scene 1: Introduction (0:00–0:15)

**Visual:** PCOS architecture diagram (from docs site)

**Voiceover:**
> PCOS — the Personal Context Operating System — is a local-first AI runtime that routes tasks across Chrome, Android, Pixel Watch, and the cloud. It's not a chatbot. It's a context router that keeps your data on-device whenever possible.

---

## Scene 2: Chrome Extension — Summarize (0:15–0:40)

**Visual:** Open a long article in Chrome Canary. Click PCOS side panel. Type "Summarize this article". Show routing decision: Chrome Summarizer API.

**Voiceover:**
> When you're reading an article and want a summary, PCOS routes it to Chrome's Built-in AI Summarizer API — running entirely in your browser, zero network latency. The routing decision is deterministic: short, browser-grounded transform tasks go to Chrome.

---

## Scene 3: Android — Function Calling (0:40–1:05)

**Visual:** Switch to Android emulator. Open PCOS app. Type "Save a note: meeting at 3pm tomorrow". Show routing to FunctionGemma, tool call execution.

**Voiceover:**
> On Android, PCOS uses LiteRT-LM with FunctionGemma for on-device function calling. When you ask it to save a note, it routes to FunctionGemma — a 270-million-parameter model that runs entirely on your phone. No data leaves the device.

---

## Scene 4: Privacy + Cloud Escalation (1:05–1:30)

**Visual:** Type a long research request. Show routing decision changing to cloud escalation. Then toggle "private" and show it routing back to Android.

**Voiceover:**
> For tasks that exceed local model limits — like a 50-page research report — PCOS escalates to cloud LLMs as a last resort. But if the task is sensitive, it stays on-device regardless of size. Privacy wins over capability.

---

## Scene 5: Pixel Watch + Health (1:30–1:50)

**Visual:** Show Wear OS tile with heart rate and activity state. Swipe to see PCOS tile.

**Voiceover:**
> The Pixel Watch companion provides ambient context — heart rate, activity state — that feeds into routing decisions. If you're running, PCOS knows to keep responses short. The watch tile shows your current status at a glance.

---

## Scene 6: Observability + Close (1:50–2:00)

**Visual:** Terminal showing `curl localhost:8000/health` and `/metrics` with JSON output.

**Voiceover:**
> PCOS includes structured logging, health checks, and latency budgets for every surface. It's production-ready, open-source, and built for developers who care about privacy and latency. Check it out on GitHub.

---

## Production Notes

- Record at 1920x1080, 30fps
- Use Chrome Canary 138+ for Translator/Language Detector
- Android emulator with Play Services for LiteRT-LM
- Wear OS emulator for watch tile
- Add subtle background music (lo-fi, low volume)
- End card: GitHub URL + "Star us on GitHub"
