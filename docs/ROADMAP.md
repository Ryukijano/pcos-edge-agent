# PCOS Long-Term Roadmap (M20–M25)

> **Purpose**: This is an executable, self-contained plan. Any agent (human or model) should be able to pick up a milestone, read its section, and implement it without additional context. Each milestone lists: goal, prerequisites, step-by-step tasks (breadth), implementation detail (depth), files to touch, verification commands, and definition of done.

## Current State (M18–M19 complete, pushed to `main`)

- **M18**: OpenAI SDK compat (`get_openai_client()`), agent skill (`agents/skills/create-litert-lm-android-demo-app/`), benchmark CLI (`scripts/run_benchmarks.py`), QAT toggle (Android UI Switch), Chrome extension SSE streaming (`executeViaLiteRTServer()`).
- **M19**: NPU SM8475/SM8450/SM8850 detection, Gemma 4 12B desktop surface (`LITERT_SERVER_12B`), multimodal E4B (`inferWithImage` / `inferStreamingWithImage`), LoRA adapter wiring (download + cache, C++ API documented), `docs/NPU_SETUP.md`.
- **Tests**: 92 passing.

## How to work on this roadmap

1. Pick the lowest-numbered incomplete milestone (they are dependency-ordered).
2. Create a branch: `git checkout -b m<NN>-<slug>`.
3. Implement tasks in order. Each task lists exact files and APIs.
4. Verify: run `/test` workflow (`python -m pytest tests/ -v`) — all tests must pass.
5. Lint: run `/lint` workflow.
6. Review: invoke the `review` skill before committing.
7. PR: run `/pr` workflow to open a pull request.
8. For privacy-sensitive changes (context, escalation, cloud), run the `security-audit` skill.

**Relevant skills** (in `.windsurf/skills/`):
- `add-model` — use when adding any new on-device model to `LiteRTManager`
- `add-surface` — use when adding any new routing surface to the broker
- `create-litert-lm-android-demo-app` — standalone Android demo app generation
- `review` — pre-commit code review
- `security-audit` — privacy/security audit for broker changes

**Relevant workflows** (in `.windsurf/workflows/`): `/test`, `/lint`, `/pr`, `/benchmark`, `/deploy`, `/release`.

**MCP servers available**: `fetch` (web content), `deepwiki` (LiteRT-LM API questions), `mcp-playwright` (browser E2E), `memory` (knowledge graph for cross-session state), `git` (repo operations), `sequential-thinking` (complex planning), `perplexity-ask` (web Q&A), `cloudflare-docs` (deployment).

---

## M20 — PiecesOS MCP Memory Integration

**Goal**: The broker queries PiecesOS Long-Term Memory (LTM) via MCP before routing, so `piecesos_memory_then_local` surface actually retrieves workflow context.

**Prerequisites**: None (independent of M21–M25).

**Background**: PiecesOS exposes an MCP server over SSE at `http://localhost:39300/model_context_protocol/2024-11-05/sse`. It exposes an `ask_pieces_ltm` tool that queries locally-stored workflow memory (code snippets, chats, links). LTM data is stored locally — no cloud egress, consistent with PCOS privacy posture. See [Pieces MCP docs](https://docs.pieces.app/products/mcp).

### Tasks (Breadth)

1. Create `broker/memory/pieces_client.py` — async MCP SSE client.
2. Add `/memory/query` proxy endpoint in `broker/routers/route_router.py`.
3. Wire LTM enrichment into the router before routing decisions.
4. Add config: `PIECES_MCP_URL` env var (default `http://localhost:39300/model_context_protocol/2024-11-05/sse`).
5. Write tests in `tests/test_pieces_client.py` with mocked SSE responses.
6. Run `security-audit` skill — LTM data must pass `strip_pii()` before cloud escalation.

### Implementation Detail (Depth)

**`broker/memory/pieces_client.py`** (new file):
```python
"""Async MCP client for PiecesOS Long-Term Memory."""
import httpx
import json
import os
import structlog

_log = structlog.get_logger()

PIECES_MCP_URL = os.getenv(
    "PIECES_MCP_URL",
    "http://localhost:39300/model_context_protocol/2024-11-05/sse",
)

class PiecesMCPClient:
    """Connects to PiecesOS MCP server via SSE, queries LTM."""

    def __init__(self, url: str = PIECES_MCP_URL):
        self._url = url
        self._initialized = False

    async def initialize(self) -> bool:
        """Send JSON-RPC initialize to MCP server. Returns True if available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(self._url, json={
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05",
                               "capabilities": {}},
                })
                if resp.status_code == 200:
                    self._initialized = True
                    return True
        except Exception as e:
            _log.warning("pieces_mcp_unavailable", error=str(e))
        return False

    async def query_ltm(self, query: str, top_k: int = 5) -> list[dict]:
        """Query LTM via ask_pieces_ltm tool. Returns list of memory snippets."""
        if not self._initialized:
            ok = await self.initialize()
            if not ok:
                return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._url, json={
                    "jsonrpc": "2.0", "id": 2,
                    "method": "tools/call",
                    "params": {"name": "ask_pieces_ltm",
                               "arguments": {"query": query, "top_k": top_k}},
                })
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("result", {}).get("content", [])
        except Exception as e:
            _log.warning("pieces_ltm_query_failed", error=str(e))
        return []

    async def close(self):
        self._initialized = False
```

**`broker/routers/route_router.py`** — add endpoint:
```python
@router.get("/memory/query")
async def memory_query(q: str, top_k: int = 5):
    """Query PiecesOS LTM via MCP."""
    from broker.memory.pieces_client import PiecesMCPClient
    client = PiecesMCPClient()
    results = await client.query_ltm(q, top_k)
    return {"query": q, "results": results}
```

**`broker/router/router.py`** — enrich context before routing:
- In the `route()` function, before step 4 (PiecesOS memory surface), call `PiecesMCPClient.query_ltm(task.text)` and inject results into `context_payload["ltm_results"]`.
- If LTM returns relevant snippets, add them to the planner's system prompt as context.
- **Critical**: LTM results must NOT flow into `cloud_llm_escalation` payloads without `strip_pii()` — run `security-audit` skill to verify.

**Tests** (`tests/test_pieces_client.py`):
- Mock SSE responses for `initialize` and `tools/call`.
- Test graceful offline fallback (connection refused → empty list).
- Test PII stripping on LTM results before cloud escalation.

### Verification

```bash
python -m pytest tests/test_pieces_client.py -v
python -m pytest tests/ -v  # full suite must still pass
```

### Definition of Done

- [ ] `broker/memory/pieces_client.py` with async MCP SSE client
- [ ] `/memory/query` endpoint in route_router.py
- [ ] Router enriches context with LTM results before routing
- [ ] `PIECES_MCP_URL` env var support
- [ ] Tests pass (92 + new tests ≥ 97)
- [ ] `security-audit` skill run — no PII leaks via LTM
- [ ] PR merged via `/pr` workflow

---

## M21 — Desktop 12B Automation + Context Reporter

**Goal**: Automate `litert-lm import` + `litert-lm serve` setup and populate `DesktopContext.total_ram_mb` so M19's 12B routing actually works.

**Prerequisites**: M19 (12B surface exists in router).

**Background**: `litert-lm import --from-huggingface-repo=litert-community/gemma-4-12B-it-litert-lm gemma-4-12B-it.litertlm gemma4-12b` registers the model. `litert-lm serve --api openai --host localhost --port 9379` starts the server. See [CLI docs](https://developers.google.com/edge/litert-lm/cli).

### Tasks (Breadth)

1. Create `scripts/setup_litert_server.py` — one-command desktop setup.
2. Create `broker/context/desktop_reporter.py` — detects RAM, GPU, 12B model availability.
3. Add tests for 12B routing decision (RAM ≥ 16384 + REASONING → `LITERT_SERVER_12B`).
4. Update `broker/config.py` with `litert_server_12b_model_id` setting.

### Implementation Detail (Depth)

**`scripts/setup_litert_server.py`** (new file):
```python
"""One-command setup for local LiteRT-LM server with model import."""
import subprocess
import psutil
import argparse
import sys

MODELS = [
    ("gemma4-e2b", "litert-community/gemma-4-E2B-it-litert-lm", "gemma-4-E2B-it.litertlm"),
    ("gemma4-e4b", "litert-community/gemma-4-E4B-it-litert-lm", "gemma-4-E4B-it.litertlm"),
    ("gemma4-12b", "litert-community/gemma-4-12B-it-litert-lm", "gemma-4-12B-it.litertlm"),
]

def import_model(model_id, hf_repo, filename):
    print(f"Importing {model_id} from HuggingFace…")
    subprocess.run([
        "litert-lm", "import",
        f"--from-huggingface-repo={hf_repo}",
        filename, model_id,
    ], check=True)

def serve(port=9379, api="openai"):
    print(f"Starting lit serve on port {port} ({api} API)…")
    subprocess.run([
        "litert-lm", "serve",
        f"--api={api}", "--host", "localhost", "--port", str(port),
    ])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", default=["e2b", "e4b"])
    parser.add_argument("--port", type=int, default=9379)
    parser.add_argument("--serve", action="store_true", help="Start server after import")
    parser.add_argument("--include-12b", action="store_true",
                        help="Import 12B model (requires 16GB+ RAM)")
    args = parser.parse_args()

    ram_mb = psutil.virtual_memory().total // (1024 * 1024)
    print(f"Detected RAM: {ram_mb} MB")

    to_import = []
    for mid, repo, fn in MODELS:
        if "12b" in mid and (not args.include_12b or ram_mb < 16384):
            print(f"Skipping {mid} (need --include-12b and 16GB+ RAM)")
            continue
        if any(m in mid for m in args.models) or args.include_12b:
            to_import.append((mid, repo, fn))

    for mid, repo, fn in to_import:
        import_model(mid, repo, fn)

    if args.serve:
        serve(args.port)

if __name__ == "__main__":
    main()
```

**`broker/context/desktop_reporter.py`** (new file):
```python
"""Detects desktop capabilities and populates DesktopContext."""
import psutil
import httpx
import structlog

_log = structlog.get_logger()

async def detect_desktop_context(server_url: str = "http://localhost:9379") -> dict:
    """Detect RAM, GPU, and available models from lit serve."""
    ram_mb = psutil.virtual_memory().total // (1024 * 1024)
    has_12b = False
    litert_available = False

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{server_url}/v1/models")
            if resp.status_code == 200:
                litert_available = True
                models = resp.json().get("data", [])
                has_12b = any("12b" in m.get("id", "").lower() for m in models)
    except Exception:
        pass

    return {
        "litert_server_available": litert_available,
        "total_ram_mb": ram_mb,
        "has_12b_model": has_12b,
        "os_type": _detect_os(),
        "has_gpu": _detect_gpu(),
    }

def _detect_os() -> str:
    import platform
    return {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(
        platform.system(), platform.system().lower())

def _detect_gpu() -> bool:
    try:
        import subprocess
        result = subprocess.run(["lspci"], capture_output=True, timeout=2)
        return b"VGA" in result.stdout or b"3D" in result.stdout
    except Exception:
        return False
```

**Tests** (`tests/test_desktop_12b.py`):
```python
def test_12b_routing_high_ram_reasoning():
    """RAM >= 16384 + REASONING → LITERT_SERVER_12B"""
    ctx = PCOSContext(
        desktop=DesktopContext(litert_server_available=True, total_ram_mb=32768, has_12b_model=True),
        task=TaskObject(text="Prove the Riemann hypothesis", task_type=TaskType.REASONING, is_short=False),
    )
    decision = route(ctx)
    assert decision.surface == Surface.LITERT_SERVER_12B

def test_12b_routing_low_ram_falls_back():
    """RAM < 16384 + REASONING → LITERT_SERVER (not 12B)"""
    ctx = PCOSContext(
        desktop=DesktopContext(litert_server_available=True, total_ram_mb=8192),
        task=TaskObject(text="Complex reasoning", task_type=TaskType.REASONING, is_short=False),
    )
    decision = route(ctx)
    assert decision.surface == Surface.LITERT_SERVER
```

### Verification

```bash
python scripts/setup_litert_server.py --models e2b e4b --include-12b --serve
python -m pytest tests/test_desktop_12b.py -v
python -m pytest tests/ -v  # full suite
```

### Definition of Done

- [ ] `scripts/setup_litert_server.py` imports models and starts server
- [ ] `broker/context/desktop_reporter.py` detects RAM, GPU, 12B availability
- [ ] 12B routing tests pass (2+ new tests)
- [ ] `DesktopContext.total_ram_mb` populated by reporter
- [ ] PR merged

---

## M22 — NPU Model Auto-Download (SoC-Specific Variants)

**Goal**: LiteRTManager auto-detects SoC and downloads the correct NPU-specific `.litertlm` model variant.

**Prerequisites**: M19 (NPU detection). Use `add-model` skill.

**Background**: NPU models are SoC-specific. The file naming convention is `Model_q4_ekv1280_{SOC_MODEL}.litertlm` (e.g. `Gemma3-1B-IT_q4_ekv1280_sm8550.litertlm`). Wrong variant fails at runtime. See [NPU docs](https://developers.google.com/edge/litert/next/litert_lm_npu). The SoC model can be read via `adb shell getprop ro.soc.model` or `Build.SOC_MODEL` on Android.

### Tasks (Breadth)

1. Add SoC → NPU model URL mapping table in `LiteRTManager.kt`.
2. Update `ensureModelDownloaded()` to fetch SoC-specific variant when NPU is selected.
3. Add QAIRT library presence check before selecting `Backend.NPU`.
4. Fallback to GPU model if NPU model unavailable for the SoC.
5. Use `add-model` skill for each NPU variant.
6. Update `scripts/run_benchmarks.py` with NPU model entries.
7. Update `docs/NPU_SETUP.md` with auto-download section.

### Implementation Detail (Depth)

**`LiteRTManager.kt`** — add SoC mapping:
```kotlin
/** NPU model variant mapping: SoC model → HuggingFace file suffix */
private val npuModelVariants: Map<String, String> = mapOf(
    "sm8550" to "sm8550",
    "sm8650" to "sm8650",
    "sm8750" to "sm8750",
    "sm8850" to "sm8850",
    // SM8450 and SM8475 use sm8550 variant (compatible DSP)
    "sm8450" to "sm8550",
    "sm8475" to "sm8550",
)

/** Get the NPU-specific model file for the current device's SoC. */
private fun getNpuModelFile(model: PCOSModel): File? {
    val socModel = Build.SOC_MODEL?.lowercase() ?: return null
    val suffix = npuModelVariants[socModel] ?: return null
    val config = modelConfigs[model] ?: return null
    // NPU variant filename: base name without .litertlm + _{suffix}.litertlm
    val baseName = config.fileName.removeSuffix(".litertlm")
    val npuFileName = "${baseName}_q4_ekv1280_${suffix}.litertlm"
    return File(getModelDir(), npuFileName)
}

/** Check if QAIRT libraries are bundled. */
private fun isQairtAvailable(): Boolean {
    val nativeDir = context.applicationInfo.nativeLibraryDir
    val qnnHtp = File(nativeDir, "libQnnHtp.so")
    return qnnHtp.exists()
}
```

Update `loadModel()` to try NPU model file first, then fallback to GPU model:
```kotlin
// In loadModel(), before backend resolution:
if (config.preferredBackend is Backend.NPU) {
    val npuFile = getNpuModelFile(model)
    if (npuFile?.exists() == true && isQairtAvailable()) {
        // Use NPU-specific model file
        engineConfig = EngineConfig(modelPath = npuFile.absolutePath, ...)
    } else {
        Log.w(TAG, "NPU model or QAIRT unavailable, falling back to GPU model")
        // Continue with standard model file + GPU backend
    }
}
```

### Verification

```bash
python -m pytest tests/ -v  # all pass
# On device: verify NPU model auto-download
adb shell getprop ro.soc.model  # e.g. sm8550
# App should download gemma-4-E2B-it_q4_ekv1280_sm8550.litertlm
```

### Definition of Done

- [ ] SoC → NPU model variant mapping table
- [ ] `getNpuModelFile()` returns correct variant for detected SoC
- [ ] `isQairtAvailable()` checks for `libQnnHtp.so`
- [ ] Fallback to GPU model when NPU variant unavailable
- [ ] `add-model` skill invoked for NPU variants
- [ ] `docs/NPU_SETUP.md` updated with auto-download section
- [ ] PR merged

---

## M23 — iOS Multimodal Parity

**Goal**: iOS `LiteRTManager.swift` gains `inferWithImage` / `inferStreamingWithImage` mirroring M19's Kotlin implementation.

**Prerequisites**: M19 (Android multimodal complete). Use `add-model` skill.

**Background**: LiteRT-LM Swift API supports multimodal via `Contents` with image data. E4B model supports vision inputs. See [Swift API docs](https://ai.google.dev/edge/litert-lm/swift).

### Tasks (Breadth)

1. Add `inferWithImage(prompt:imageData:)` to `LiteRTManager.swift`.
2. Add `inferStreamingWithImage(prompt:imageData:onChunk:)` to `LiteRTManager.swift`.
3. Add `isVisionSupported()` / `isAudioSupported()` capability checks.
4. Add PhotosPicker to `ContentView.swift` for image selection.
5. Wire image input to inference pipeline in ContentView.
6. Verify broker routes iOS multimodal to `IOS_GEMMA_E4B` (already done in M17).

### Implementation Detail (Depth)

**`apps/ios/PCOSEdge/LiteRTManager.swift`** — add:
```swift
// MARK: - Multimodal Inference

func inferWithImage(prompt: String, imageData: Data) async -> String {
    guard let engine = engine else { return "[Model not loaded]" }
    guard let config = modelConfigs[currentModel],
          config.visionBackend != nil else {
        return "[Vision not supported on current model. Use E4B.]"
    }
    do {
        let convConfig = ConversationConfig(
            systemInstruction: config.systemInstruction,
            samplerConfig: SamplerConfig(topK: 10, topP: 0.95, temperature: 0.8)
        )
        let conversation = try engine.createConversation(convConfig)
        let contents = Contents.of(text: prompt, images: [imageData])
        let response = try conversation.sendMessage(contents)
        return response.text
    } catch {
        return "[Error: \(error.localizedDescription)]"
    }
}

func inferStreamingWithImage(
    prompt: String, imageData: Data, onChunk: @escaping (String) -> Void
) async -> String {
    guard let engine = engine else { return "[Model not loaded]" }
    guard let config = modelConfigs[currentModel],
          config.visionBackend != nil else {
        return "[Vision not supported on current model. Use E4B.]"
    }
    do {
        let convConfig = ConversationConfig(
            systemInstruction: config.systemInstruction,
            samplerConfig: SamplerConfig(topK: 10, topP: 0.95, temperature: 0.8)
        )
        let conversation = try engine.createConversation(convConfig)
        let contents = Contents.of(text: prompt, images: [imageData])
        var result = ""
        for try await message in conversation.sendMessageAsync(contents) {
            let text = message.toString()
            result += text
            onChunk(text)
        }
        return result
    } catch {
        return "[Error: \(error.localizedDescription)]"
    }
}

func isVisionSupported() -> Bool {
    guard let model = currentModel, let config = modelConfigs[model] else { return false }
    return config.visionBackend != nil
}

func isAudioSupported() -> Bool {
    guard let model = currentModel, let config = modelConfigs[model] else { return false }
    return config.audioBackend != nil
}
```

**`apps/ios/PCOSEdge/ContentView.swift`** — add PhotosPicker:
```swift
import PhotosUI

// In ContentView body:
PhotosPicker(selection: $selectedItem, matching: .images) {
    Label("Select Image", systemImage: "photo")
}
.onChange(of: selectedImage) { _, newImage in
    if let image = newImage {
        Task {
            if let imageData = image.jpegData(compressionQuality: 0.8) {
                let result = await litertManager.inferWithImage(
                    prompt: "Describe this image",
                    imageData: imageData
                )
                // Display result
            }
        }
    }
}
```

### Verification

```bash
# Build in Xcode (no pytest for iOS)
# Verify: select image → E4B model → streaming description appears
python -m pytest tests/ -v  # broker tests still pass
```

### Definition of Done

- [ ] `inferWithImage` and `inferStreamingWithImage` in `LiteRTManager.swift`
- [ ] `isVisionSupported()` / `isAudioSupported()` in Swift
- [ ] PhotosPicker in `ContentView.swift`
- [ ] Image input wired to inference pipeline
- [ ] `add-model` skill invoked for E4B vision config
- [ ] PR merged

---

## M24 — E2E Test Harness

**Goal**: Comprehensive end-to-end tests using Playwright MCP for browser UI and pytest for backend routing.

**Prerequisites**: M20 (PiecesOS), M21 (12B routing tests needed).

### Tasks (Breadth)

1. Write Playwright MCP tests for Chrome extension sidepanel (SSE streaming, routing display).
2. Write Playwright MCP tests for HF Space UI (routing demo, surface descriptions).
3. Add pytest cases for 12B routing (from M21).
4. Add pytest cases for `DesktopContext` fields and `desktop_reporter.py`.
5. Add pytest cases for `PiecesMCPClient` (from M20).
6. Add pytest cases for multimodal surface selection (E4B → vision routing).
7. Target: 110+ total tests.

### Implementation Detail (Depth)

**Playwright tests** (use `mcp7_browser_*` tools):
- Navigate to `http://localhost:8000` (broker) → verify routing API responds.
- Navigate to HF Space URL → verify surface descriptions render.
- Test Chrome extension sidepanel: mock broker response, verify SSE streaming display.

**pytest additions** (`tests/test_routing_12b.py`, `tests/test_multimodal_routing.py`):
```python
# tests/test_routing_12b.py
def test_12b_routing_high_ram_reasoning():
    ctx = PCOSContext(
        desktop=DesktopContext(litert_server_available=True, total_ram_mb=32768, has_12b_model=True),
        task=TaskObject(text="Complex proof", task_type=TaskType.REASONING, is_short=False),
    )
    assert route(ctx).surface == Surface.LITERT_SERVER_12B

def test_12b_routing_no_server_falls_to_cloud():
    ctx = PCOSContext(
        desktop=DesktopContext(litert_server_available=False, total_ram_mb=32768),
        task=TaskObject(text="Complex proof", task_type=TaskType.REASONING, is_short=False),
    )
    assert route(ctx).surface == Surface.CLOUD_LLM

# tests/test_multimodal_routing.py
def test_multimodal_routes_to_e4b():
    ctx = PCOSContext(
        android=AndroidContext(total_ram_mb=8192, has_gpu=True),
        task=TaskObject(text="Describe this image", task_type=TaskType.MULTIMODAL, is_short=True),
    )
    decision = route(ctx)
    assert "e4b" in decision.surface.value
```

### Verification

```bash
python -m pytest tests/ -v  # 110+ tests
# Playwright: use mcp7_browser_navigate + mcp7_browser_snapshot
```

### Definition of Done

- [ ] Playwright tests for Chrome extension sidepanel
- [ ] Playwright tests for HF Space UI
- [ ] 12B routing tests (2+ cases)
- [ ] DesktopContext reporter tests
- [ ] PiecesMCPClient tests
- [ ] Multimodal routing tests
- [ ] Total test count ≥ 110
- [ ] PR merged

---

## M25 — v1.0 Release

**Goal**: Production-ready v1.0.0 release with security audit, benchmark baseline, and deployment.

**Prerequisites**: M20–M24 all merged.

### Tasks (Breadth)

1. Run `security-audit` skill — full pass on all broker policies, escalation, PII stripping.
2. Run `/benchmark` workflow — capture baseline JSON, commit to `benchmarks/baseline-v1.0.json`.
3. Write `CHANGELOG.md` for v1.0.0 (all milestones M1–M25).
4. Run `/release` workflow — create git tag `v1.0.0`.
5. Run `/deploy` workflow — deploy to HuggingFace Spaces.
6. Record release state in memory MCP knowledge graph.
7. Update `README.md` with v1.0.0 badge and full feature list.

### Implementation Detail (Depth)

**Security audit checklist** (invoke `security-audit` skill):
- `broker/policies/escalation.py`: PII stripping before cloud calls, `is_safe_for_cloud()` enforced.
- `broker/policies/privacy.py`: regex patterns comprehensive, `_REPLACEMENTS` covers all types.
- `broker/memory/pieces_client.py`: LTM results stripped before cloud escalation.
- API keys: all from env vars, no hardcoding.
- `AndroidManifest.xml`: permissions minimal, `uses-native-library` correct.
- Chrome extension: no external data exfiltration, CSP headers correct.

**Benchmark baseline** (`/benchmark` workflow):
```bash
python scripts/run_benchmarks.py --model all --backends cpu,gpu --output benchmarks/baseline-v1.0.json
```

**CHANGELOG.md** (new file):
```markdown
# Changelog

## v1.0.0 (2026-07-XX)

### Added
- Five-plane edge AI broker: Chrome, Android, iOS, desktop, cloud
- LiteRT-LM integration with Gemma 4 E2B/E4B/12B, FunctionGemma 270M
- NPU backend (Qualcomm QNN) for Snapdragon 8 Gen 1+ with auto-fallback
- Multimodal inference (vision + audio) for E4B on Android and iOS
- LoRA adapter infrastructure for task-specific fine-tuning
- OpenAI SDK compatibility via `get_openai_client()`
- PiecesOS MCP memory integration
- Chrome extension with SSE streaming from litert_server
- Flutter cross-platform app
- Agent skill for Android demo app generation
- Benchmark CLI for automated regression testing
- Model quantization toggle (QAT mobile variants)
- Desktop 12B automation with RAM-based routing

### Known Limitations
- LiteRT-LM Kotlin API does not yet expose LoRA loading (C++ only)
- Web JS API is text-only (no browser multimodal yet)
- NPU models are SoC-specific (wrong variant fails at runtime)
```

### Verification

```bash
python -m pytest tests/ -v  # all 110+ pass
python scripts/run_benchmarks.py --model all --backends cpu,gpu --output benchmarks/baseline-v1.0.json
# security-audit skill: no Critical or High findings
```

### Definition of Done

- [ ] `security-audit` skill run — no Critical/High findings
- [ ] Benchmark baseline JSON committed
- [ ] `CHANGELOG.md` written
- [ ] Git tag `v1.0.0` created via `/release` workflow
- [ ] Deployed to HF Spaces via `/deploy` workflow
- [ ] Memory MCP knowledge graph updated with release state
- [ ] `README.md` updated with v1.0.0 features
- [ ] PR merged

---

## Tooling Matrix

| Milestone | Skills | Workflows | MCP servers |
|---|---|---|---|
| M20 | security-audit, review | /test, /lint, /pr | fetch (Pieces docs), sequential-thinking |
| M21 | review | /test, /pr, /benchmark | deepwiki (CLI questions) |
| M22 | add-model, review | /test, /pr, /benchmark | deepwiki, fetch |
| M23 | add-model, review | /test, /pr | deepwiki |
| M24 | review | /test, /lint, /pr | mcp-playwright |
| M25 | security-audit, review | /release, /deploy, /benchmark, /test | git, memory |

## Dependency Graph

```
M19 (done) ─┬─→ M20 (PiecesOS MCP) ──┬─→ M24 (E2E tests) ─→ M25 (v1.0 release)
            ├─→ M21 (12B automation) ─┘
            └─→ M22 (NPU auto-download)
            └─→ M23 (iOS multimodal)
```

M20, M21, M22, M23 are independent of each other and can be parallelized.
M24 depends on M20 and M21 (needs their test cases).
M25 depends on all prior milestones.
