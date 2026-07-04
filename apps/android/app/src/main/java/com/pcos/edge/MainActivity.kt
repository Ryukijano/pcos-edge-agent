package com.pcos.edge

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                PCOSApp()
            }
        }
    }
}

@Composable
fun PCOSApp(viewModel: PCOSViewModel = viewModel()) {
    val uiState by viewModel.uiState.collectAsState()

    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Header
        Text("PCOS", style = MaterialTheme.typography.headlineMedium)
        Text("Local-first AI runtime", style = MaterialTheme.typography.bodySmall)

        // Status row
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatusChip("Broker", uiState.brokerConnected)
            StatusChip("Bridge", uiState.bridgeConnected)
            StatusChip("LiteRT-LM", uiState.modelLoaded)
        }

        // Backend info
        if (uiState.modelLoaded) {
            Text(
                "Backend: ${uiState.activeBackend}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        // Benchmark dashboard
        if (uiState.lastInferenceMs > 0) {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    "TTFT: ${uiState.timeToFirstTokenMs}ms",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.tertiary
                )
                Text(
                    "⚡ ${String.format("%.0f", uiState.prefillTokensPerSec)} tk/s prefill",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(
                    "${String.format("%.1f", uiState.decodeTokensPerSec)} tk/s decode",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary
                )
                Text(
                    "${uiState.lastInferenceMs}ms",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        // Download progress
        if (uiState.modelDownloading) {
            Text(
                uiState.downloadProgress,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.tertiary
            )
        }

        // Model selector
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            FilterChip(
                selected = uiState.selectedModel == PCOSModel.FUNCTION_GEMMA,
                onClick = { viewModel.selectModel(PCOSModel.FUNCTION_GEMMA) },
                label = { Text("FG 270M") }
            )
            FilterChip(
                selected = uiState.selectedModel == PCOSModel.GEMMA_4_E2B,
                onClick = { viewModel.selectModel(PCOSModel.GEMMA_4_E2B) },
                label = { Text("E2B") }
            )
            FilterChip(
                selected = uiState.selectedModel == PCOSModel.GEMMA_4_E4B,
                onClick = { viewModel.selectModel(PCOSModel.GEMMA_4_E4B) },
                label = { Text("E4B") }
            )
            FilterChip(
                selected = uiState.selectedModel == PCOSModel.GEMMA_4_E2B_MOBILE,
                onClick = { viewModel.selectModel(PCOSModel.GEMMA_4_E2B_MOBILE) },
                label = { Text("E2B Mobile") }
            )
            FilterChip(
                selected = uiState.selectedModel == PCOSModel.GEMMA_4_E4B_MOBILE,
                onClick = { viewModel.selectModel(PCOSModel.GEMMA_4_E4B_MOBILE) },
                label = { Text("E4B Mobile") }
            )
        }
        Text(
            "${uiState.selectedModel.displayName()} · ${uiState.selectedModel.sizeMb()}MB",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        // Input
        OutlinedTextField(
            value = uiState.inputText,
            onValueChange = viewModel::updateInput,
            label = { Text("Ask PCOS…") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 2
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = viewModel::execute, enabled = uiState.inputText.isNotBlank()) {
                Text("Execute")
            }
            OutlinedButton(onClick = viewModel::clearOutput) {
                Text("Clear")
            }
        }

        Divider()

        // Output
        LazyColumn(
            modifier = Modifier.fillMaxWidth().weight(1f),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            items(uiState.outputLines) { line ->
                Text(line, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun StatusChip(label: String, connected: Boolean) {
    AssistChip(
        onClick = {},
        label = { Text(label, style = MaterialTheme.typography.labelSmall) },
        leadingIcon = {
            Box(
                modifier = Modifier.size(8.dp),
                contentAlignment = Alignment.Center
            ) {
                Surface(
                    modifier = Modifier.size(8.dp),
                    shape = MaterialTheme.shapes.small,
                    color = if (connected) MaterialTheme.colorScheme.primary
                           else MaterialTheme.colorScheme.outline
                ) {}
            }
        }
    )
}
