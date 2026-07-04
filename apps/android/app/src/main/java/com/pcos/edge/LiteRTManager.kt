package com.pcos.edge

import android.content.Context
import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Conversation
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.Tool
import com.google.ai.edge.litertlm.ToolParam
import com.google.ai.edge.litertlm.ToolSet
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.withContext
import java.io.File

/**
 * LiteRT-LM Manager — handles Engine → Conversation pipeline for Gemma 4 and FunctionGemma.
 *
 * Uses the official LiteRT-LM Kotlin API (v0.13+):
 * - Engine: model loading with CPU/GPU/NPU backend selection
 * - Conversation: per-chat inference with system instruction and sampling config
 * - ToolSet: annotated Kotlin functions for function calling (FunctionGemma)
 *
 * Models are stored in app-private external storage and downloaded on first use.
 * Model files use the .litertlm format from HuggingFace LiteRT Community.
 */
class LiteRTManager(private val context: Context) {

    companion object {
        private const val TAG = "PCOS-LiteRT"
        private const val MODELS_DIR = "models"
    }

    private var engine: Engine? = null
    private var conversation: Conversation? = null
    private var currentModel: PCOSModel? = null

    private val modelConfigs = mapOf(
        PCOSModel.FUNCTION_GEMMA to ModelConfig(
            fileName = "functiongemma_270m_it.litertlm",
            hfUrl = "https://huggingface.co/litert-community/functiongemma-270m-it/resolve/main/functiongemma-270m-it.litertlm",
            backend = Backend.CPU(),
            systemInstruction = "You are a helpful on-device assistant. Use tools when appropriate.",
        ),
        PCOSModel.GEMMA_FULL to ModelConfig(
            fileName = "gemma_4_e2b_it.litertlm",
            hfUrl = "https://huggingface.co/litert-community/gemma-4-e2b-it/resolve/main/gemma-4-e2b-it.litertlm",
            backend = Backend.GPU(),
            systemInstruction = "You are a helpful on-device assistant.",
        ),
    )

    data class ModelConfig(
        val fileName: String,
        val hfUrl: String,
        val backend: Backend,
        val systemInstruction: String,
    )

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

    suspend fun loadModel(model: PCOSModel): Boolean = withContext(Dispatchers.IO) {
        if (currentModel == model && engine != null) return@withContext true

        try {
            // Close existing conversation/engine
            conversation?.close()
            engine?.close()

            val file = getModelFile(model)
            if (!file.exists()) {
                Log.w(TAG, "Model file not found: ${file.absolutePath}")
                Log.w(TAG, "Call ensureModelDownloaded() first")
                return@withContext false
            }

            val config = modelConfigs[model]!!
            val engineConfig = EngineConfig(
                modelPath = file.absolutePath,
                backend = config.backend,
                cacheDir = context.cacheDir.path,
            )

            Log.i(TAG, "Initializing engine for ${config.fileName}…")
            engine = Engine(engineConfig)
            engine!!.initialize()

            currentModel = model
            Log.i(TAG, "Engine ready for $model")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load model", e)
            currentModel = null
            false
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
                response.toString()
            }
        } catch (e: Exception) {
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
            "[Error: ${e.message}]"
        }
    }

    /**
     * Function calling via LiteRT-LM Tool Use API.
     * Uses annotated Kotlin ToolSet — the model auto-executes tools and feeds results back.
     */
    suspend fun inferWithTools(prompt: String, tools: List<ToolSet>): String = withContext(Dispatchers.IO) {
        val eng = engine ?: return@withContext "[Model not loaded]"
        if (currentModel != PCOSModel.FUNCTION_GEMMA) {
            return@withContext "[FunctionGemma not loaded]"
        }

        try {
            val convConfig = ConversationConfig(
                systemInstruction = "You are a helpful on-device assistant. Use tools when appropriate.",
                tools = tools.map { tool(it) },
                samplerConfig = SamplerConfig(topK = 10, topP = 0.95, temperature = 0.8),
            )
            eng.createConversation(convConfig).use { conv ->
                val response = conv.sendMessage(prompt)
                response.toString()
            }
        } catch (e: Exception) {
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
