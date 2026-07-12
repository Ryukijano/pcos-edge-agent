# Changelog

All notable PCOS releases are documented here.

## [1.0.0] - 2026-07-12

### Added

- Five-plane edge AI broker across Chrome, Android, iOS, desktop, and cloud fallback.
- Deterministic routing for private, offline, multimodal, browser-grounded, memory, action, and reasoning tasks.
- LiteRT-LM integration with Gemma 4 E2B/E4B, FunctionGemma 270M, and desktop Gemma 4 12B routing.
- Qualcomm QAIRT/NPU support with SoC-specific model auto-download and NPU → GPU → CPU fallback.
- Android vision/audio multimodal inference and iOS E4B multimodal inference with PhotosPicker.
- PiecesOS MCP memory integration with PII stripping before cloud escalation.
- Chrome extension with Chrome Built-in AI, WebGPU, local LiteRT-LM server streaming, and Android bridge relay.
- QAT mobile model toggle and RAM-based desktop 12B selection.
- OpenAI-compatible LiteRT-LM server client and cloud Gemini/OpenAI escalation adapters.
- LoRA adapter download/cache infrastructure.
- Playwright E2E specifications and 235-test Python regression suite.
- Reproducible LiteRT-LM benchmark runner with structured JSON output.

### Security

- Cloud payloads are stripped and validated with `is_safe_for_cloud()` before provider calls.
- Release defaults restrict CORS to local development origins rather than wildcard origins.
- WebSocket bridge supports mandatory token authentication for public deployments.
- Chrome host permissions are limited to the local broker; current-page access uses `activeTab`.
- Added release security regression tests covering versions, secrets, permissions, PII, and configuration.

### Documentation

- Added NPU auto-download and SoC compatibility documentation.
- Added iOS multimodal setup and E2E testing coverage.
- Added M25 security audit evidence and release verification guidance.

### Known limitations

- LiteRT-LM Kotlin API does not yet expose LoRA loading directly; the C++ API does.
- Browser JavaScript inference remains text-focused for the current release.
- NPU model files remain SoC-specific; an unsupported or incorrect variant falls back to GPU/CPU.
- Device benchmark values require the LiteRT-LM CLI or a connected Android device; unavailable environments are recorded as such rather than fabricated.

[1.0.0]: https://github.com/Ryukijano/pcos-edge-agent/releases/tag/v1.0.0
