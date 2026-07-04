# Chrome Extension

The PCOS Chrome extension provides a side panel UI and captures browser context for routing.

## Features

- **Side panel** — Task input, routing result display, context preview
- **Context capture** — URL, page title, DOM summary, selected text
- **Built-in AI calls** — Direct Chrome AI API invocation (Prompt, Summarizer, Translator, etc.)
- **WebSocket bridge** — Keepalive + relay to Android via broker

## Chrome Built-in AI APIs

| API | Method | Use Case |
|---|---|---|
| Prompt | `ai.prompt()` | General instructions |
| Summarizer | `ai.summarizer.create()` | Summarization |
| Translator | `ai.translator.create()` | Translation |
| Language Detector | `ai.languageDetector.detect()` | Language detection |
| Writer | `ai.writer.create()` | Generation |
| Rewriter | `ai.rewriter.create()` | Rewriting |
| Proofreader | `ai.proofreader.create()` | Grammar |

## WebSocket Keepalive

Chrome service workers are terminated after 30s of inactivity. The extension uses:
- Offscreen document for persistent WebSocket connection
- Ping/pong every 25s
- Reconnect on disconnect

## Build

```bash
cd apps/chrome-extension
# Load unpacked extension from chrome://extensions
```

Requires Chrome Canary 138+ for Translator and Language Detector APIs.
