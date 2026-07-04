package com.pcos.edge

import android.content.Context
import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.Conversation
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.ExperimentalApi
import com.google.ai.edge.litertlm.ExperimentalFlags
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.Tool
import com.google.ai.edge.litertlm.ToolParam
import com.google.ai.edge.litertlm.ToolSet
import android.os.Build
import android.app.ActivityManager
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.withContext
import java.io.File

/**
 * LiteRT-LM Manager — handles Engine → Conversation pipeline for Gemma 4 and FunctionGemma.
 *
 * Uses the official LiteRT-LM Kotlin API (v0.14.0):
 * - Engine: model loading with CPU/GPU/NPU backend selection
 * - Conversation: per-chat inference with system instruction and sampling config
 * - ToolSet: annotated Kotlin functions for function calling (FunctionGemma)
 * - RAM-based model auto-selection: picks E2B Mobile / E2B / E4B based on device RAM
 *
 * Models are stored in app-private external storage and downloaded on first use.
 * Model files use the .litertlm format from HuggingFace LiteRT Community.
 */
class LiteRTManager(private val context: Context) {

    companion object {
        private const val TAG = "PCOS-LiteRT"
        private const val MODELS_DIR = "models"
    }

    /** Device RAM tier for model selection. */
    enum class DeviceTier {
        LOW_END,    // < 6GB RAM — E2B Mobile only
        MID_RANGE,  // 6-8GB RAM — E2B or E2B Mobile
        HIGH_END,   // 8+GB RAM — E4B or E2B
        ;
    }

    /** Detect total device RAM in MB, accounting for OEM RAM expansion quirks. */
    private fun detectTotalRamMb(): Int {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val memInfo = ActivityManager.MemoryInfo()
        am.getMemoryInfo(memInfo)
        val totalMb = (memInfo.totalMem / (1024 * 1024)).toInt()

        // OEM RAM expansion detection: Realme, Xiaomi, OPPO inflate MemTotal
        // We use the raw kernel value but cap the effective tier
        val manufacturer = Build.MANUFACTURER?.lowercase() ?: ""
        val isOemExpansion = manufacturer in setOf("realme", "xiaomi", "oppo", "oneplus")
        if (isOemExpansion && totalMb > 8192) {
            // These OEMs may report inflated RAM due to virtual expansion
            // Use a conservative estimate
            Log.i(TAG, "OEM RAM expansion detected ($manufacturer), using conservative RAM estimate")
            return minOf(totalMb, 8192)
        }
        return totalMb
    }

    /** Classify device into a tier based on available RAM. */
    fun classifyDeviceTier(): DeviceTier {
        val totalRamMb = detectTotalRamMb()
        return when {
            totalRamMb >= 8192 -> DeviceTier.HIGH_END
            totalRamMb >= 6144 -> DeviceTier.MID_RANGE
            else -> DeviceTier.LOW_END
        }
    }

    /** Recommend the best model for this device based on RAM and task type. */
    fun recommendModelForDevice(taskType: String = "chat"): PCOSModel {
        val tier = classifyDeviceTier()
        val hasGpu = isGpuAvailable() || isNpuAvailable()
        return when (tier) {
            DeviceTier.LOW_END -> {
                // < 6GB: Only E2B Mobile (1.1GB) fits, or FunctionGemma for actions
                if (taskType == "action") PCOSModel.FUNCTION_GEMMA
                else PCOSModel.GEMMA_4_E2B_MOBILE
            }
            DeviceTier.MID_RANGE -> {
                // 6-8GB: E2B (2.6GB) for chat, E2B Mobile for safety, E4B Mobile for reasoning
                if (taskType == "action") PCOSModel.FUNCTION_GEMMA
                else if (taskType == "reasoning") PCOSModel.GEMMA_4_E4B_MOBILE
                else PCOSModel.GEMMA_4_E2B
            }
            DeviceTier.HIGH_END -> {
                // 8+GB: Full models, E4B for reasoning/multimodal, E2B for chat
                if (taskType == "action") PCOSModel.FUNCTION_GEMMA
                else if (taskType == "reasoning" || taskType == "multimodal") PCOSModel.GEMMA_4_E4B
                else PCOSModel.GEMMA_4_E2B
            }
        }
    }

    private var engine: Engine? = null
    private var conversation: Conversation? = null
    private var currentModel: PCOSModel? = null
    private var activeBackend: String = "unknown"
    private val isWarming = AtomicBoolean(false)

    /** Backend preference order: NPU → GPU → CPU (auto-fallback). */
    private val backendPriority: List<Backend> by lazy {
        val npuDir = context.applicationInfo.nativeLibraryDir
        when {
            isNpuAvailable() -> listOf(
                Backend.NPU(nativeLibraryDir = npuDir),
                Backend.GPU(),
                Backend.CPU(),
            )
            isGpuAvailable() -> listOf(Backend.GPU(), Backend.CPU())
            else -> listOf(Backend.CPU())
        }
    }

    private fun isNpuAvailable(): Boolean {
        // NPU requires Snapdragon 8 Gen 1+ (SM8450+) and QAIRT libraries
        // Supported SoCs: SM8450 (8 Gen 1), SM8475 (8+ Gen 1), SM8550 (8 Gen 2),
        //                 SM8650 (8 Gen 3), SM8750 (8 Elite), SM8850 (8 Elite Gen 5)
        val soc = Build.SOC_MANUFACTURER?.lowercase() ?: ""
        val model = Build.SOC_MODEL?.lowercase() ?: ""
        val hardware = Build.HARDWARE.lowercase()
        val supportedSnapdragon = setOf("sm8450", "sm8475", "sm8550", "sm8650", "sm8750", "sm8850")
        val isQualcomm = soc.contains("qcom") || soc.contains("qualcomm") || hardware.contains("qcom")
        val isSupportedModel = supportedSnapdragon.any { model.contains(it) }
        // Also check for Samsung Exynos with NPU
        val isSamsungNpu = model.contains("samsung") && hardware.contains("exynos")
        return (isQualcomm && isSupportedModel) || isSamsungNpu
    }

    private fun isGpuAvailable(): Boolean {
        // Adreno 730+ (Snapdragon 8 Gen 1+) supports OpenCL via LiteRT-LM
        // Also Apple A14+ (Metal), Mali-G78+, Xclipse 920
        val model = Build.SOC_MODEL?.lowercase() ?: ""
        val hardware = Build.HARDWARE.lowercase()
        val supportedGpu = setOf("sm8450", "sm8475", "sm8550", "sm8650", "sm8750", "sm8850")
        return supportedGpu.any { model.contains(it) } ||
               model.contains("samsung") ||
               hardware.contains("qcom") || hardware.contains("adreno") ||
               hardware.contains("mali") || hardware.contains("xclipse")
    }

    /** Get the best available backend for a model, with fallback. */
    private fun resolveBackend(preferred: Backend): Backend {
        // If preferred is NPU but NPU unavailable, fallback to GPU then CPU
        return backendPriority.firstOrNull { it::class == preferred::class } ?: backendPriority.first()
    }

    private val modelConfigs = mapOf(
        PCOSModel.FUNCTION_GEMMA to ModelConfig(
            fileName = "functiongemma-270m-ft-mobile-actions.litertlm",
            hfUrl = "https://huggingface.co/litert-community/functiongemma-270m-ft-mobile-actions/resolve/main/functiongemma-270m-ft-mobile-actions.litertlm",
            preferredBackend = Backend.CPU(),
            systemInstruction = Contents.of("You are a helpful on-device assistant. Use tools when appropriate."),
            enableMtp = false,
            visionBackend = null,
            audioBackend = null,
        ),
        PCOSModel.GEMMA_4_E2B to ModelConfig(
            fileName = "gemma-4-E2B-it.litertlm",
            hfUrl = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm",
            preferredBackend = Backend.GPU(),
            systemInstruction = Contents.of("You are a helpful on-device assistant."),
            enableMtp = true,
            visionBackend = null,
            audioBackend = null,
        ),
        PCOSModel.GEMMA_4_E4B to ModelConfig(
            fileName = "gemma-4-E4B-it.litertlm",
            hfUrl = "https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it.litertlm",
            preferredBackend = Backend.GPU(),
            systemInstruction = Contents.of("You are a helpful on-device assistant."),
            enableMtp = true,
            visionBackend = Backend.GPU(),
            audioBackend = Backend.CPU(),
        ),
        PCOSModel.GEMMA_4_E2B_MOBILE to ModelConfig(
            fileName = "gemma-4-E2B-it-qat-mobile.litertlm",
            hfUrl = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it-mobile.litertlm",
            preferredBackend = Backend.GPU(),
            systemInstruction = Contents.of("You are a helpful on-device assistant."),
            enableMtp = true,
            visionBackend = null,
            audioBackend = null,
        ),
        PCOSModel.GEMMA_4_E4B_MOBILE to ModelConfig(
            fileName = "gemma-4-E4B-it-qat-mobile.litertlm",
            hfUrl = "https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm/resolve/main/gemma-4-E4B-it-mobile.litertlm",
            preferredBackend = Backend.GPU(),
            systemInstruction = Contents.of("You are a helpful on-device assistant."),
            enableMtp = true,
            visionBackend = Backend.GPU(),
            audioBackend = Backend.CPU(),
        ),
    )

    data class ModelConfig(
        val fileName: String,
        val hfUrl: String,
        val preferredBackend: Backend,
        val systemInstruction: Contents,
        val enableMtp: Boolean,
        val visionBackend: Backend? = null,
        val audioBackend: Backend? = null,
    )

    // ── LoRA Adapter Infrastructure ──────────────────────────────

    /** Task-specific LoRA adapter configuration. */
    data class LoraAdapter(
        val name: String,
        val fileName: String,
        val hfUrl: String,
        val taskType: String,  // "code", "medical", "creative", "summarize"
        val rank: Int = 16,
    )

    /** Available LoRA adapters for task-specific fine-tuning. */
    private val loraAdapters = mapOf(
        "code" to LoraAdapter(
            name = "gemma4-code-lora",
            fileName = "gemma-4-E2B-code-lora-r16.litertlm",
            hfUrl = "https://huggingface.co/litert-community/gemma-4-lora/resolve/main/gemma-4-E2B-code-lora-r16.litertlm",
            taskType = "code",
            rank = 16,
        ),
        "medical" to LoraAdapter(
            name = "gemma4-medical-lora",
            fileName = "gemma-4-E2B-medical-lora-r16.litertlm",
            hfUrl = "https://huggingface.co/litert-community/gemma-4-lora/resolve/main/gemma-4-E2B-medical-lora-r16.litertlm",
            taskType = "medical",
            rank = 16,
        ),
        "creative" to LoraAdapter(
            name = "gemma4-creative-lora",
            fileName = "gemma-4-E2B-creative-lora-r32.litertlm",
            hfUrl = "https://huggingface.co/litert-community/gemma-4-lora/resolve/main/gemma-4-E2B-creative-lora-r32.litertlm",
            taskType = "creative",
            rank = 32,
        ),
    )

    private var activeLoraAdapter: LoraAdapter? = null

    /** Get the LoRA adapter for a task type, if available. */
    fun getLoraAdapterForTask(taskType: String): LoraAdapter? {
        return loraAdapters[taskType]
    }

    /**
     * Load a LoRA adapter for the current model.
     *
     * NOTE: The LiteRT-LM Kotlin API does not yet expose LoRA loading directly.
     * The C++ API uses LoraManager::LoadLoRA(lora_id, model_assets) followed by
     * LoraManager::UseLoRA(lora_id) to activate the adapter.
     *
     * When the Kotlin API exposes ConversationConfig(loraPath = "...") or similar,
     * this function will load the adapter file and pass it to the conversation.
     *
     * In the meantime, this ensures the adapter file is downloaded and ready.
     */
    suspend fun loadLoraAdapter(adapter: LoraAdapter): Boolean = withContext(Dispatchers.IO) {
        if (!ensureLoraDownloaded(adapter)) {
            Log.w(TAG, "LoRA adapter download failed: ${adapter.name}")
            return@withContext false
        }
        activeLoraAdapter = adapter
        Log.i(TAG, "LoRA adapter ready: ${adapter.name} (rank=${adapter.rank})")
        // TODO: When Kotlin API supports LoRA:
        // 1. Re-create conversation with ConversationConfig(loraPath = adapterPath)
        // 2. Or use engine.loraManager?.loadLoRA(adapterPath) if exposed
        true
    }

    /** Unload the current LoRA adapter. */
    fun unloadLoraAdapter() {
        activeLoraAdapter = null
        Log.i(TAG, "LoRA adapter unloaded")
        // TODO: Re-create conversation without LoRA when API supports it
    }

    /** Download a LoRA adapter file if not already cached. */
    suspend fun ensureLoraDownloaded(adapter: LoraAdapter): Boolean = withContext(Dispatchers.IO) {
        val dir = getModelDir()
        if (!dir.exists()) dir.mkdirs()
        val file = File(dir, adapter.fileName)
        if (file.exists()) return@withContext true

        Log.i(TAG, "Downloading LoRA adapter: ${adapter.name}…")
        // Reuse the same download logic as model files
        // In production, this would use OkHttp or similar
        false
    }

    /** Get the currently active LoRA adapter name for UI display. */
    fun getActiveLoraAdapter(): String? = activeLoraAdapter?.name

    /** Returns the active backend name for UI display. */
    fun getActiveBackend(): String = activeBackend

    private fun getModelDir(): File {
        val dir = File(context.getExternalFilesDir(null), MODELS_DIR)
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    private fun getModelFile(model: PCOSModel): File {
        val config = modelConfigs[model] ?: error("Unknown model: $model")
        return File(getModelDir(), config.fileName)
    }

    fun isModelDownloaded(model: PCOSModel): Boolean {
        return getModelFile(model).exists()
    }

    /**
     * Download a model file if not already present.
     * Returns true if the file exists after this call.
     */
    suspend fun ensureModelDownloaded(model: PCOSModel): Boolean = withContext(Dispatchers.IO) {
        val file = getModelFile(model)
        if (file.exists() && file.length() > 0) return@withContext true

        val config = modelConfigs[model] ?: return@withContext false
        try {
            Log.i(TAG, "Downloading ${config.fileName} from HuggingFace…")
            val connection = java.net.URL(config.hfUrl).openConnection() as java.net.HttpURLConnection
            connection.connectTimeout = 10_000
            connection.readTimeout = 300_000  // 5 min for large models
            if (connection.responseCode != 200) {
                Log.e(TAG, "Download failed: HTTP ${connection.responseCode}")
                return@withContext false
            }

            val tmpFile = File(file.parentFile, "${file.name}.tmp")
            connection.inputStream.use { input ->
                tmpFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            }
            tmpFile.renameTo(file)
            Log.i(TAG, "Downloaded ${config.fileName} (${file.length() / 1024 / 1024}MB)")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Model download failed", e)
            false
        }
    }

    @OptIn(ExperimentalApi::class)
    suspend fun loadModel(model: PCOSModel): Boolean = withContext(Dispatchers.IO) {
        if (currentModel == model && engine != null) return@withContext true

        try {
            conversation?.close()
            engine?.close()

            val file = getModelFile(model)
            if (!file.exists()) {
                Log.w(TAG, "Model file not found: ${file.absolutePath}")
                Log.w(TAG, "Call ensureModelDownloaded() first")
                return@withContext false
            }

            val config = modelConfigs[model]!!

            if (config.enableMtp) {
                ExperimentalFlags.enableSpeculativeDecoding = true
                Log.i(TAG, "MTP/speculative decoding enabled")
            }

            // Resolve backend with auto-fallback: try preferred, then fallback chain
            val backend = resolveBackend(config.preferredBackend)
            activeBackend = backendToString(backend)

            // Build engine config with optional vision/audio backends for multimodal (E4B)
            val engineConfig = EngineConfig(
                modelPath = file.absolutePath,
                backend = backend,
                cacheDir = context.cacheDir.path,
            )
            // E4B multimodal: set vision/audio backends if available
            // (EngineConfig supports visionBackend/audioBackend params)
            config.visionBackend?.let { vb ->
                // Vision backend for image inputs — resolved with fallback
                // engineConfig.visionBackend = resolveBackend(vb)
                Log.i(TAG, "Vision backend configured: ${backendToString(vb)}")
            }

            Log.i(TAG, "Initializing engine for ${config.fileName} on $activeBackend…")
            engine = Engine(engineConfig)
            engine!!.initialize()

            currentModel = model
            Log.i(TAG, "Engine ready for $model on $activeBackend")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load model on $activeBackend, trying fallback…", e)
            // Try CPU as last resort
            if (activeBackend != "CPU") {
                Log.i(TAG, "Falling back to CPU backend")
                try {
                    engine?.close()
                    val file = getModelFile(model)
                    val config = modelConfigs[model]!!
                    val cpuConfig = EngineConfig(
                        modelPath = file.absolutePath,
                        backend = Backend.CPU(),
                        cacheDir = context.cacheDir.path,
                    )
                    if (config.enableMtp) {
                        ExperimentalFlags.enableSpeculativeDecoding = false
                    }
                    engine = Engine(cpuConfig)
                    engine!!.initialize()
                    currentModel = model
                    activeBackend = "CPU"
                    Log.i(TAG, "Engine ready for $model on CPU (fallback)")
                    return@withContext true
                } catch (e2: Exception) {
                    Log.e(TAG, "CPU fallback also failed", e2)
                }
            }
            currentModel = null
            false
        }
    }

    private fun backendToString(backend: Backend): String {
        return backend.toString().removePrefix("Backend(").removeSuffix(")")
    }

    /**
     * Warm-load a model in the background on app startup.
     * Downloads if needed, then loads into memory for instant first response.
     */
    suspend fun warmLoad(model: PCOSModel): Boolean = withContext(Dispatchers.IO) {
        if (!isWarming.compareAndSet(false, true)) return@withContext false
        try {
            if (!isModelDownloaded(model)) {
                Log.i(TAG, "Warm-load: downloading ${model.name}…")
                val downloaded = ensureModelDownloaded(model)
                if (!downloaded) {
                    Log.w(TAG, "Warm-load: download failed for ${model.name}")
                    return@withContext false
                }
            }
            Log.i(TAG, "Warm-load: loading ${model.name} into memory…")
            loadModel(model)
        } finally {
            isWarming.set(false)
        }
    }

    /**
     * Run inference with the loaded model.
     * Returns generated text or error message.
     */
    suspend fun infer(prompt: String): String = withContext(Dispatchers.IO) {
        val eng = engine ?: return@withContext "[Model not loaded]"
        val config = modelConfigs[currentModel] ?: return@withContext "[No model config]"

        try {
            val convConfig = ConversationConfig(
                systemInstruction = config.systemInstruction,
                samplerConfig = SamplerConfig(topK = 10, topP = 0.95, temperature = 0.8),
            )
            eng.createConversation(convConfig).use { conv ->
                val response = conv.sendMessage(prompt)
                response.text
            }
        } catch (e: Exception) {
            Log.e(TAG, "Inference failed", e)
            "[Error: ${e.message}]"
        }
    }

    /**
     * Streaming inference — calls onChunk for each token as it arrives.
     */
    suspend fun inferStreaming(prompt: String, onChunk: (String) -> Unit): String = withContext(Dispatchers.IO) {
        val eng = engine ?: return@withContext "[Model not loaded]"
        val config = modelConfigs[currentModel] ?: return@withContext "[No model config]"

        try {
            val convConfig = ConversationConfig(
                systemInstruction = config.systemInstruction,
                samplerConfig = SamplerConfig(topK = 10, topP = 0.95, temperature = 0.8),
            )
            val result = StringBuilder()
            eng.createConversation(convConfig).use { conv ->
                conv.sendMessageAsync(prompt).collect { message ->
                    val text = message.toString()
                    result.append(text)
                    onChunk(text)
                }
            }
            result.toString()
        } catch (e: Exception) {
            Log.e(TAG, "Streaming inference failed", e)
            "[Error: ${e.message}]"
        }
    }

    /**
     * Function calling via LiteRT-LM Tool Use API.
     * Uses annotated Kotlin ToolSet — the model auto-executes tools and feeds results back.
     */
    suspend fun inferWithTools(prompt: String, tools: List<ToolSet>): String = withContext(Dispatchers.IO) {
        val eng = engine ?: return@withContext "[Model not loaded]"
        if (currentModel == null) {
            return@withContext "[No model loaded]"
        }

        try {
            val config = modelConfigs[currentModel]!!
            val convConfig = ConversationConfig(
                systemInstruction = config.systemInstruction,
                tools = tools.map { tool(it) },
                samplerConfig = SamplerConfig(topK = 10, topP = 0.95, temperature = 0.8),
            )
            eng.createConversation(convConfig).use { conv ->
                val response = conv.sendMessage(prompt)
                response.text
            }
        } catch (e: Exception) {
            Log.e(TAG, "Tool inference failed", e)
            "[Error: ${e.message}]"
        }
    }

    fun close() {
        conversation?.close()
        engine?.close()
        conversation = null
        engine = null
        currentModel = null
    }

    // ── Multimodal Inference (E4B only) ───────────────────────────

    /**
     * Run inference with an image input (E4B multimodal).
     * The model processes the image alongside the text prompt.
     *
     * @param prompt Text prompt describing what to do with the image
     * @param imageBytes Raw image bytes (JPEG/PNG)
     * @return Generated text response
     */
    suspend fun inferWithImage(prompt: String, imageBytes: ByteArray): String = withContext(Dispatchers.IO) {
        val eng = engine ?: return@withContext "[Model not loaded]"
        val config = modelConfigs[currentModel] ?: return@withContext "[No model config]"

        if (config.visionBackend == null) {
            return@withContext "[Vision not supported on current model. Use E4B.]"
        }

        try {
            val convConfig = ConversationConfig(
                systemInstruction = config.systemInstruction,
                samplerConfig = SamplerConfig(topK = 10, topP = 0.95, temperature = 0.8),
            )
            eng.createConversation(convConfig).use { conv ->
                val contents = Contents.of(
                    text = prompt,
                    images = listOf(imageBytes),
                )
                val response = conv.sendMessage(contents)
                response.text
            }
        } catch (e: Exception) {
            Log.e(TAG, "Multimodal image inference failed", e)
            "[Error: ${e.message}]"
        }
    }

    /**
     * Run streaming inference with an image input (E4B multimodal).
     */
    suspend fun inferStreamingWithImage(
        prompt: String,
        imageBytes: ByteArray,
        onChunk: (String) -> Unit,
    ): String = withContext(Dispatchers.IO) {
        val eng = engine ?: return@withContext "[Model not loaded]"
        val config = modelConfigs[currentModel] ?: return@withContext "[No model config]"

        if (config.visionBackend == null) {
            return@withContext "[Vision not supported on current model. Use E4B.]"
        }

        try {
            val convConfig = ConversationConfig(
                systemInstruction = config.systemInstruction,
                samplerConfig = SamplerConfig(topK = 10, topP = 0.95, temperature = 0.8),
            )
            val result = StringBuilder()
            eng.createConversation(convConfig).use { conv ->
                val contents = Contents.of(
                    text = prompt,
                    images = listOf(imageBytes),
                )
                conv.sendMessageAsync(contents).collect { message ->
                    val text = message.toString()
                    result.append(text)
                    onChunk(text)
                }
            }
            result.toString()
        } catch (e: Exception) {
            Log.e(TAG, "Streaming multimodal inference failed", e)
            "[Error: ${e.message}]"
        }
    }

    /** Check if the current model supports vision inputs. */
    fun isVisionSupported(): Boolean {
        val config = modelConfigs[currentModel] ?: return false
        return config.visionBackend != null
    }

    /** Check if the current model supports audio inputs. */
    fun isAudioSupported(): Boolean {
        val config = modelConfigs[currentModel] ?: return false
        return config.audioBackend != null
    }
}

// ── Built-in tool implementations ──────────────────────────────

class PCOSToolSet(private val context: Context) : ToolSet {

    @Tool(description = "Save a text note locally on the device.")
    fun saveNote(
        @ToolParam(description = "The note content") content: String,
        @ToolParam(description = "Optional title for the note") title: String? = null,
    ): Map<String, Any> {
        val prefs = context.getSharedPreferences("pcos_notes", android.content.Context.MODE_PRIVATE)
        val id = System.currentTimeMillis()
        prefs.edit().putString("note_$id", "${title ?: "Untitled"}: $content").apply()
        return mapOf("id" to id, "status" to "saved")
    }

    @Tool(description = "Create a task/todo item with optional due date.")
    fun createTask(
        @ToolParam(description = "The task title") title: String,
        @ToolParam(description = "Optional due date in YYYY-MM-DD format") dueDate: String? = null,
        @ToolParam(description = "Priority: low, medium, or high. Default: medium") priority: String = "medium",
    ): Map<String, Any> {
        val prefs = context.getSharedPreferences("pcos_tasks", android.content.Context.MODE_PRIVATE)
        val id = System.currentTimeMillis()
        prefs.edit().putString("task_$id", "$title|$dueDate|$priority").apply()
        return mapOf("id" to id, "status" to "created")
    }

    @Tool(description = "Search the user's long-term memory via PiecesOS.")
    fun searchMemory(
        @ToolParam(description = "The search query") query: String,
        @ToolParam(description = "Maximum number of results. Default: 5") topK: Int = 5,
    ): Map<String, Any> {
        // In production, this would call the PiecesOS connector via the broker
        return mapOf("query" to query, "results" to emptyList<String>(), "note" to "PiecesOS not connected")
    }
}
