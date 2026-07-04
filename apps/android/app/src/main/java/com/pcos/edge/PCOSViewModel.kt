package com.pcos.edge

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import com.google.ai.edge.litertlm.Backend

enum class PCOSModel {
    FUNCTION_GEMMA,
    GEMMA_4_E2B,
    GEMMA_4_E4B,
    GEMMA_4_E2B_MOBILE,
    GEMMA_4_E4B_MOBILE,
}

/** Recommended backend for each model based on benchmark data. */
fun PCOSModel.recommendedBackend(): Backend = when (this) {
    PCOSModel.FUNCTION_GEMMA -> Backend.CPU()
    PCOSModel.GEMMA_4_E2B -> Backend.GPU()
    PCOSModel.GEMMA_4_E4B -> Backend.GPU()
    PCOSModel.GEMMA_4_E2B_MOBILE -> Backend.GPU()
    PCOSModel.GEMMA_4_E4B_MOBILE -> Backend.GPU()
}

/** Human-readable model info for UI display. */
fun PCOSModel.displayName(): String = when (this) {
    PCOSModel.FUNCTION_GEMMA -> "FunctionGemma 270M (CPU)"
    PCOSModel.GEMMA_4_E2B -> "Gemma 4 E2B 2.3B (GPU)"
    PCOSModel.GEMMA_4_E4B -> "Gemma 4 E4B 4.5B (GPU)"
    PCOSModel.GEMMA_4_E2B_MOBILE -> "Gemma 4 E2B Mobile 1GB (QAT)"
    PCOSModel.GEMMA_4_E4B_MOBILE -> "Gemma 4 E4B Mobile 2.2GB (QAT)"
}

/** Model size in MB for download progress display. */
fun PCOSModel.sizeMb(): Int = when (this) {
    PCOSModel.FUNCTION_GEMMA -> 289
    PCOSModel.GEMMA_4_E2B -> 2583
    PCOSModel.GEMMA_4_E4B -> 3654
    PCOSModel.GEMMA_4_E2B_MOBILE -> 1100
    PCOSModel.GEMMA_4_E4B_MOBILE -> 2500
}

data class PCOSUiState(
    val brokerConnected: Boolean = false,
    val bridgeConnected: Boolean = false,
    val modelLoaded: Boolean = false,
    val modelDownloading: Boolean = false,
    val downloadProgress: String = "",
    val selectedModel: PCOSModel = PCOSModel.FUNCTION_GEMMA,
    val activeBackend: String = "unknown",
    val inputText: String = "",
    val outputLines: List<String> = emptyList(),
    val isExecuting: Boolean = false,
    val streamingText: String = "",
    val prefillTokensPerSec: Float = 0f,
    val decodeTokensPerSec: Float = 0f,
    val timeToFirstTokenMs: Long = 0L,
    val lastInferenceMs: Long = 0L,
)

class PCOSViewModel : AndroidViewModel(Application()) {
    private val _uiState = MutableStateFlow(PCOSUiState())
    val uiState: StateFlow<PCOSUiState> = _uiState.asStateFlow()

    private val litertManager = LiteRTManager(getApplication())
    private val bridgeClient = BridgeClient(getApplication())
    private val watchSync = WatchSyncManager(getApplication())

    init {
        checkConnections()
        warmLoadDefaultModel()
        setupBridgeRelay()
    }

    private fun setupBridgeRelay() {
        bridgeClient.onMessage = { msg ->
            when (msg.optString("type")) {
                "relay" -> {
                    val payload = msg.optJSONObject("payload") ?: return@onMessage
                    val fromClientId = msg.optString("from", "")
                    handleRelayTask(payload, fromClientId)
                }
            }
        }
        bridgeClient.connect()
    }

    private fun handleRelayTask(payload: JSONObject, fromClientId: String) {
        val task = payload.optJSONObject("task") ?: return
        val text = task.optString("text", "")
        if (text.isBlank()) return

        val decision = payload.optJSONObject("decision")
        val surface = decision?.optString("surface", "") ?: ""

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isExecuting = true, streamingText = "")
            addOutput("← Bridge relay: $text")

            // Send status update to Chrome
            bridgeClient.sendRelay(fromClientId, JSONObject().put("type", "status").put("message", "Executing on Android…"))

            val result = if (surface == "android_litert_functiongemma") {
                litertManager.inferWithTools(text, listOf(PCOSToolSet(getApplication())))
            } else {
                litertManager.inferStreaming(text) { chunk ->
                    _uiState.value = _uiState.value.copy(
                        streamingText = _uiState.value.streamingText + chunk
                    )
                    // Stream chunks to Chrome
                    bridgeClient.sendRelay(
                        fromClientId,
                        JSONObject().put("type", "streaming-chunk").put("chunk", chunk)
                    )
                }
            }

            addOutput("  Result: $result")

            // Send final result to Chrome
            bridgeClient.sendResult(fromClientId, result)

            syncToWatch(activityState = "executing", lastResult = result)
            _uiState.value = _uiState.value.copy(isExecuting = false, streamingText = "")
        }
    }

    /**
     * Warm-load the default model (E2B) on app startup for instant first response.
     * Falls back to FunctionGemma if E2B download fails.
     */
    private fun warmLoadDefaultModel() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                selectedModel = PCOSModel.GEMMA_4_E2B,
                modelDownloading = true,
                downloadProgress = "Warm-loading Gemma 4 E2B…",
            )
            val loaded = litertManager.warmLoad(PCOSModel.GEMMA_4_E2B)
            if (loaded) {
                _uiState.value = _uiState.value.copy(
                    modelLoaded = true,
                    modelDownloading = false,
                    downloadProgress = "",
                    activeBackend = litertManager.getActiveBackend(),
                )
            } else {
                // Fallback to FunctionGemma (smaller, faster download)
                _uiState.value = _uiState.value.copy(
                    selectedModel = PCOSModel.FUNCTION_GEMMA,
                    downloadProgress = "Falling back to FunctionGemma…",
                )
                val fgLoaded = litertManager.warmLoad(PCOSModel.FUNCTION_GEMMA)
                _uiState.value = _uiState.value.copy(
                    modelLoaded = fgLoaded,
                    modelDownloading = false,
                    downloadProgress = if (fgLoaded) "" else "Download failed",
                    activeBackend = if (fgLoaded) litertManager.getActiveBackend() else "none",
                )
            }
        }
    }

    /**
     * Dynamically switch model based on task type detected by the broker.
     * E2B for transforms (fast), E4B for reasoning (capable).
     */
    private suspend fun maybeSwitchModel(surface: String) {
        val targetModel = when {
            surface == "android_litert_functiongemma" -> PCOSModel.FUNCTION_GEMMA
            surface == "android_litert_gemma_e4b" -> PCOSModel.GEMMA_4_E4B
            surface == "android_litert_gemma_e2b" -> PCOSModel.GEMMA_4_E2B
            else -> return
        }
        if (_uiState.value.selectedModel != targetModel) {
            addOutput("  Switching model: ${_uiState.value.selectedModel.displayName()} → ${targetModel.displayName()}")
            _uiState.value = _uiState.value.copy(
                selectedModel = targetModel,
                modelLoaded = false,
            )
            if (!litertManager.isModelDownloaded(targetModel)) {
                _uiState.value = _uiState.value.copy(
                    modelDownloading = true,
                    downloadProgress = "Downloading ${targetModel.displayName()}…",
                )
                litertManager.ensureModelDownloaded(targetModel)
                _uiState.value = _uiState.value.copy(
                    modelDownloading = false,
                    downloadProgress = "",
                )
            }
            val loaded = litertManager.loadModel(targetModel)
            _uiState.value = _uiState.value.copy(
                modelLoaded = loaded,
                activeBackend = if (loaded) litertManager.getActiveBackend() else "none",
            )
        }
    }

    private fun checkConnections() {
        viewModelScope.launch {
            val brokerOk = bridgeClient.checkBroker()
            val bridgeOk = bridgeClient.isConnected()
            _uiState.value = _uiState.value.copy(
                brokerConnected = brokerOk,
                bridgeConnected = bridgeOk,
            )
            syncToWatch(brokerStatus = if (brokerOk) "ok" else "offline")
        }
    }

    private fun loadModel() {
        viewModelScope.launch {
            val model = _uiState.value.selectedModel
            val mgr = litertManager

            if (!mgr.isModelDownloaded(model)) {
                _uiState.value = _uiState.value.copy(
                    modelDownloading = true,
                    downloadProgress = "Downloading ${model.name}…",
                )
                val downloaded = mgr.ensureModelDownloaded(model)
                _uiState.value = _uiState.value.copy(
                    modelDownloading = false,
                    downloadProgress = if (downloaded) "" else "Download failed",
                )
                if (!downloaded) return@launch
            }

            val loaded = mgr.loadModel(model)
            _uiState.value = _uiState.value.copy(
                modelLoaded = loaded,
                activeBackend = if (loaded) mgr.getActiveBackend() else "none",
            )
        }
    }

    fun selectModel(model: PCOSModel) {
        _uiState.value = _uiState.value.copy(selectedModel = model, modelLoaded = false)
        loadModel()
    }

    fun updateInput(text: String) {
        _uiState.value = _uiState.value.copy(inputText = text)
    }

    fun clearOutput() {
        _uiState.value = _uiState.value.copy(outputLines = emptyList())
    }

    fun execute() {
        val input = _uiState.value.inputText.trim()
        if (input.isBlank()) return
        if (_uiState.value.isExecuting) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isExecuting = true, streamingText = "")
            addOutput("→ $input")

            val routing = bridgeClient.routeViaBroker(input, _uiState.value.selectedModel)

            if (routing != null) {
                val decision = routing.optJSONObject("decision")
                val surface = decision?.optString("surface") ?: ""
                addOutput("  Routed to: $surface")

                if (surface.startsWith("android_litert")) {
                    // Dynamic model switching based on broker's routing decision
                    maybeSwitchModel(surface)
                    val plan = routing.optJSONObject("plan")
                    val tools = plan?.optJSONArray("tools")
                    val inferStart = System.nanoTime()
                    val result = if (tools != null && tools.length() > 0 && surface == "android_litert_functiongemma") {
                        addOutput("  Tools available: ${tools.length()}")
                        litertManager.inferWithTools(input, listOf(PCOSToolSet(getApplication())))
                    } else {
                        addOutput("  Using ${_uiState.value.selectedModel.displayName()}")
                        litertManager.inferStreaming(input) { chunk ->
                            _uiState.value = _uiState.value.copy(
                                streamingText = _uiState.value.streamingText + chunk
                            )
                        }
                    }
                    val inferElapsedMs = (System.nanoTime() - inferStart) / 1_000_000
                    // Estimate tokens: ~4 chars per token for English text
                    val outputTokens = maxOf(1, result.length / 4)
                    val decodeTkSec = if (inferElapsedMs > 0) (outputTokens.toFloat() / inferElapsedMs * 1000) else 0f
                    val inputTokens = maxOf(1, input.length / 4)
                    val prefillTkSec = if (inferElapsedMs > 0) (inputTokens.toFloat() / (inferElapsedMs / 1000f)) else 0f
                    _uiState.value = _uiState.value.copy(
                        prefillTokensPerSec = prefillTkSec,
                        decodeTokensPerSec = decodeTkSec,
                        lastInferenceMs = inferElapsedMs,
                    )
                    addOutput("  Result: $result")
                    addOutput("  ⚡ ${String.format("%.0f", prefillTkSec)} tk/s prefill, ${String.format("%.1f", decodeTkSec)} tk/s decode, ${inferElapsedMs}ms")
                    syncToWatch(activityState = "executing", lastResult = result)
                } else if (surface == "chrome_builtin_ai") {
                    addOutput("  (Chrome should handle this locally)")
                    syncToWatch(activityState = "chrome")
                } else if (surface == "cloud_llm_escalation") {
                    addOutput("  (Cloud escalation — stripped & logged)")
                    syncToWatch(activityState = "cloud")
                }
            } else {
                addOutput("  Broker offline, running locally…")
                val result = litertManager.inferStreaming(input) { chunk ->
                    _uiState.value = _uiState.value.copy(
                        streamingText = _uiState.value.streamingText + chunk
                    )
                }
                addOutput("  Result: $result")
                syncToWatch(brokerStatus = "offline", activityState = "local", lastResult = result)
            }

            _uiState.value = _uiState.value.copy(isExecuting = false, streamingText = "")
        }
    }

    private fun addOutput(line: String) {
        _uiState.value = _uiState.value.copy(
            outputLines = _uiState.value.outputLines + line
        )
    }

    private fun syncToWatch(
        activityState: String = "idle",
        brokerStatus: String = "unknown",
        lastResult: String = "",
    ) {
        watchSync.syncContext(
            activityState = activityState,
            brokerStatus = brokerStatus,
            lastResult = lastResult.take(200),
            urgent = true,
        )
    }
}
