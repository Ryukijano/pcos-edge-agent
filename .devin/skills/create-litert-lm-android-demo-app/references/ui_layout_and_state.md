# UI Layout and State

## Compose UI Structure

```kotlin
@Composable
fun ChatScreen(viewModel: ChatViewModel) {
    val state by viewModel.state.collectAsState()

    Column {
        // Top bar with backend selector
        TopAppBar(
            title = { Text("LiteRT-LM Demo") },
            actions = {
                BackendSelector(
                    selected = state.backend,
                    onSelect = viewModel::changeBackend
                )
            }
        )

        // Message list
        LazyColumn(
            modifier = Modifier.weight(1f),
            state = viewModel.listState
        ) {
            items(state.messages) { msg ->
                MessageBubble(msg)
            }
            if (state.isStreaming) {
                item { StreamingIndicator(state.partialText) }
            }
        }

        // Input bar
        InputBar(
            text = state.inputText,
            onTextChange = viewModel::updateInput,
            onSend = viewModel::sendMessage,
            enabled = state.engineReady && !state.isStreaming
        )
    }
}
```

## State Management

```kotlin
data class ChatState(
    val messages: List<ChatMessage> = emptyList(),
    val inputText: String = "",
    val isStreaming: Boolean = false,
    val partialText: String = "",
    val engineReady: Boolean = false,
    val backend: String = "gpu",
    val modelPath: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
)

class ChatViewModel : ViewModel() {
    private val _state = MutableStateFlow(ChatState())
    val state: StateFlow<ChatState> = _state.asStateFlow()
}
```

## Backend Selector

```kotlin
@Composable
fun BackendSelector(selected: String, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        TextButton(onClick = { expanded = true }) {
            Text("Backend: ${selected.uppercase()}")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            listOf("cpu", "gpu", "npu").forEach { backend ->
                DropdownMenuItem(
                    text = { Text(backend.uppercase()) },
                    onClick = { onSelect(backend); expanded = false }
                )
            }
        }
    }
}
```

## Message Bubble

```kotlin
@Composable
fun MessageBubble(msg: ChatMessage) {
    val alignment = if (msg.isUser) Alignment.End else Alignment.Start
    val color = if (msg.isUser) MaterialTheme.colorScheme.primary
                else MaterialTheme.colorScheme.surfaceVariant

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp),
        contentAlignment = alignment
    ) {
        Surface(color = color, shape = RoundedCornerShape(12.dp)) {
            Text(
                text = msg.content,
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}
```

## Compliance Checklist

- [ ] Chat messages displayed in scrollable list
- [ ] Backend selector with CPU/GPU/NPU options
- [ ] Model selector or path input
- [ ] Streaming indicator during generation
- [ ] Input field with send button
- [ ] Send button disabled during streaming
- [ ] Error messages displayed to user
- [ ] Loading indicator during model initialization
- [ ] Material 3 theme applied
- [ ] Responsive layout (works in portrait and landscape)
