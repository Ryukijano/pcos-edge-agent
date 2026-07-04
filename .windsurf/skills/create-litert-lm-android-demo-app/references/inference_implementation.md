# Inference Implementation

## Engine Initialization

```kotlin
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Conversation
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ExperimentalFlags

class LiteRTManager(context: Context) {
    private var engine: Engine? = null
    private var conversation: Conversation? = null

    suspend fun loadModel(modelPath: String, backend: Backend): Boolean {
        ExperimentalFlags.enableSpeculativeDecoding = (backend is Backend.GPU)

        val config = EngineConfig(
            modelPath = modelPath,
            backend = backend,
            cacheDir = context.cacheDir.path,
        )
        engine = Engine(config)
        engine!!.initialize()

        val convConfig = ConversationConfig(
            systemInstruction = Contents.of("You are a helpful assistant.")
        )
        conversation = engine!!.createConversation(convConfig)
        return true
    }
}
```

## Streaming Inference

```kotlin
suspend fun inferStreaming(prompt: String, onChunk: (String) -> Unit): String {
    val conv = conversation ?: return ""
    val result = StringBuilder()

    conv.sendMessageStreaming(prompt).collect { chunk ->
        for (item in chunk.content) {
            if (item.type == ContentType.TEXT) {
                result.append(item.text)
                onChunk(item.text)
            }
        }
    }
    return result.toString()
}
```

## Multimodal (E4B only)

```kotlin
// Add image to conversation
val imageContent = Contents.of(
    text = "Describe this image",
    images = listOf(imageBitmap)
)
conversation?.sendMessage(imageContent)
```

## Backend Selection

```kotlin
fun resolveBackend(choice: String): Backend = when (choice) {
    "cpu" -> Backend.CPU()
    "gpu" -> Backend.GPU()
    "npu" -> Backend.NPU()  // Requires Snapdragon 8 Gen 2+
    else -> Backend.GPU()   // Default to GPU
}
```

## Compliance Checklist

- [ ] Engine initialized with correct backend
- [ ] System instruction set on conversation
- [ ] Streaming via sendMessageStreaming() implemented
- [ ] MTP/speculative decoding enabled for GPU
- [ ] Error handling for missing model files
- [ ] Conversation cleaned up on model switch
- [ ] Multimodal inputs handled for E4B (if applicable)
