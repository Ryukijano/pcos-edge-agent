# Skill: Create LiteRT-LM Android Demo App

## Overview
This skill guides the agent to implement, build, and package a standalone LiteRT-LM Android demo application with backend selection and multi-modality support.

## Execution Process

### 1. Gather Parameters
Extract the following from the user's trigger prompt:
- **root**: Root directory path for the project (e.g., `~/litert_lm_litert_lm_maven_integration`)
- **Integration scenario**: Either "Maven Integration" or "Source Build"
- **Target**: Target device (e.g., "pixel 10", "pixel 9 pro", etc.)
- **Model**: Model name (e.g., "gemma 4", "gemma 4 E2B", "gemma 4 E4B")

### 2. Set Up Project Structure
Create the Android project with the following structure:
```
root/
├── BUILD
├── AndroidManifest.xml
├── build.gradle.kts
├── settings.gradle.kts
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/example/litertlm/
│       │   ├── MainActivity.kt
│       │   ├── LiteRTManager.kt
│       │   └── ViewModel.kt
│       └── res/
│           ├── layout/
│           └── values/
```

### 3. Configure Dependencies
Follow the appropriate integration scenario:

#### Maven Integration
- Add `com.google.ai.edge.litertlm:litertlm-android:0.14.0` to `app/build.gradle.kts`
- Ensure Maven Central repository is configured

#### Source Build
- Clone LiteRT-LM repository
- Configure Bazel 9 build targets
- Link native libraries via JNI

### 4. Implement UI Layout
Follow the reference in `references/ui_layout_and_state.md`:
- Chat interface with message list
- Backend selector (CPU/GPU/NPU)
- Model selector dropdown
- Send button and input field
- Progress indicator for model loading

### 5. Implement Inference
Follow the reference in `references/inference_implementation.md`:
- Initialize `Engine` with `EngineConfig`
- Create `Conversation` with system instruction
- Stream tokens via `sendMessageStreaming()`
- Handle multimodal inputs (image/audio) for E4B

### 6. Verify Compliance
Run through all compliance checklists:
- `references/compliance_checklist_dependency.md`
- `references/compliance_checklist_ui.md`
- `references/compliance_checklist_inference.md`

### 7. Build and Deploy
```bash
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## References
- [LiteRT-LM Android Guide](https://developers.google.com/edge/litert-lm/android)
- [LiteRT-LM GitHub](https://github.com/google-ai-edge/LiteRT-LM)
- [Gemma 4 Models](https://huggingface.co/litert-community)
