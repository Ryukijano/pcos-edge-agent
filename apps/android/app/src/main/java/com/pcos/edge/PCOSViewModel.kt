package com.pcos.edge

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class PCOSModel { FUNCTION_GEMMA, GEMMA_FULL }

data class PCOSUiState(
    val brokerConnected: Boolean = false,
    val bridgeConnected: Boolean = false,
    val modelLoaded: Boolean = false,
    val modelDownloading: Boolean = false,
    val downloadProgress: String = "",
    val selectedModel: PCOSModel = PCOSModel.FUNCTION_GEMMA,
    val inputText: String = "",
    val outputLines: List<String> = emptyList(),
    val isExecuting: Boolean = false,
    val streamingText: String = "",
)

class PCOSViewModel : AndroidViewModel(Application()) {
    private val _uiState = MutableStateFlow(PCOSUiState())
    val uiState: StateFlow<PCOSUiState> = _uiState.asStateFlow()

    private val litertManager = LiteRTManager(getApplication())
    private val bridgeClient = BridgeClient(getApplication())
    private val watchSync = WatchSyncManager(getApplication())

    init {
        checkConnections()
        loadModel()
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
            _uiState.value = _uiState.value.copy(modelLoaded = loaded)
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

                if (surface == "android_litert_functiongemma" || surface == "android_litert_gemma_full") {
                    val plan = routing.optJSONObject("plan")
                    val tools = plan?.optJSONArray("tools")
                    val result = if (tools != null && tools.length() > 0 && surface == "android_litert_functiongemma") {
                        addOutput("  Tools available: ${tools.length()}")
                        litertManager.inferWithTools(input, listOf(PCOSToolSet(getApplication())))
                    } else {
                        litertManager.inferStreaming(input) { chunk ->
                            _uiState.value = _uiState.value.copy(
                                streamingText = _uiState.value.streamingText + chunk
                            )
                        }
                    }
                    addOutput("  Result: $result")
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
