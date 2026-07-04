# Compliance Checklist: Inference

- [ ] Engine initialized with correct Backend (CPU/GPU/NPU)
- [ ] EngineConfig includes modelPath, backend, and cacheDir
- [ ] System instruction set on ConversationConfig
- [ ] Streaming inference via sendMessageStreaming() implemented
- [ ] MTP/speculative decoding enabled for GPU backend
- [ ] ExperimentalFlags.optIntoExperimentalAPIs() called before engine init
- [ ] Error handling for missing model files (graceful fallback)
- [ ] Conversation cleaned up (close/delete) on model switch
- [ ] Engine cleaned up on app destroy
- [ ] Multimodal inputs (image/audio) handled for E4B model
- [ ] Backend auto-fallback: GPU → CPU if init fails
- [ ] Inference runs on background thread (Dispatchers.IO)
- [ ] Cancellation support during streaming
- [ ] Token counting / benchmark metrics tracked
- [ ] KV cache size configured (maxNumTokens)
