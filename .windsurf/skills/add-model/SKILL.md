---
name: add-model
description: Add a new on-device model to the PCOS LiteRTManager
allowed-tools:
  - read
  - grep
  - glob
  - edit
  - exec
triggers:
  - user
  - model
---

Add a new LiteRT-LM model to the PCOS edge agent:

1. Read `apps/android/app/src/main/java/com/pcos/edge/PCOSModel.kt` to see existing model enum entries.

2. Add the new model to the `PCOSModel` enum with:
   - Model name
   - Parameter count
   - File size
   - RAM requirement
   - Supported backends (CPU/GPU/NPU)
   - Multimodal support (vision/audio)

3. Add a `ModelConfig` entry in `LiteRTManager.kt` with:
   - `fileName`: the .litertlm file name
   - `hfUrl`: HuggingFace download URL
   - `preferredBackend`: CPU/GPU/NPU
   - `systemInstruction`: appropriate system prompt
   - `enableMtp`: true if MTP/speculative decoding is supported
   - `visionBackend`: Backend.GPU() if vision is supported, null otherwise
   - `audioBackend`: Backend.CPU() if audio is supported, null otherwise

4. Update `recommendModelForDevice()` if the model should be auto-selected.

5. Update the QAT toggle logic in `PCOSModel.kt` if a QAT variant exists.

6. Add the model to `scripts/run_benchmarks.py` model list.

7. Update README.md model table with benchmarks.

8. Run tests to verify nothing broke.
