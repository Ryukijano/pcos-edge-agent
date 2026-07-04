package com.pcos.watch

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import androidx.wear.compose.material.Chip
import androidx.wear.compose.material.ChipDefaults
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.Text
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var healthMonitor: HealthMonitor

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        healthMonitor = HealthMonitor(this)

        // Start collecting heart rate
        lifecycleScope.launch {
            healthMonitor.heartRateFlow().collect { bpm ->
                WatchState.update(watchHeartRate = bpm)
            }
        }

        setContent {
            MaterialTheme {
                PCOSWatchApp()
            }
        }
    }
}

@Composable
fun PCOSWatchApp() {
    val state by WatchState.state.collectAsState()

    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Title
        Text("PCOS", style = MaterialTheme.typography.title2)

        // Heart rate
        val hr = state.watchHeartRate ?: state.phoneHeartRate
        Text(
            if (hr > 0) "$hr BPM" else "— BPM",
            style = MaterialTheme.typography.body1
        )

        // Activity state
        Text(
            state.activityState.replaceFirstChar { it.uppercase() },
            style = MaterialTheme.typography.body2
        )

        // Broker status
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            val color = if (state.brokerStatus == "ok") MaterialTheme.colors.primary
                         else MaterialTheme.colors.error
            Text("●", color = color, style = MaterialTheme.typography.caption1)
            Text(state.brokerStatus, style = MaterialTheme.typography.caption1)
        }

        // Last result preview
        if (state.lastResult.isNotBlank()) {
            Text(
                state.lastResult.take(60),
                style = MaterialTheme.typography.caption2,
                maxLines = 3
            )
        }
    }
}
