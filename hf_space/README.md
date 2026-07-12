---
title: PCOS Context Broker
emoji: 🧠
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
custom:
  release: v1.0.0
tags:
  - ai
  - routing
  - edge
  - chrome
  - android
  - gemini
---

# PCOS Context Broker Demo (v1.0.0)

Interactive demo of the **Personal Context Operating System** — a local-first hybrid AI runtime that routes tasks across Chrome Built-in AI, Android LiteRT-LM, PiecesOS memory, and cloud LLMs (Gemini/OpenAI).

## Tabs

1. **Route Explorer** — Enter a task and see which surface PCOS routes it to
2. **Privacy Inspector** — See PII stripping before cloud escalation
3. **Cloud Escalation** — Try actual cloud LLM calls (set API keys as Space secrets)
4. **Metrics Dashboard** — Local-vs-cloud hit rate and surface breakdown
5. **System Health** — Latency budgets and configuration

## Secrets

Set these as Space secrets to enable cloud escalation:

| Secret | Description |
|--------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key (free tier available) |
| `OPENAI_API_KEY` | OpenAI API key (fallback) |
