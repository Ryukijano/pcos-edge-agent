package com.pcos.watch

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import androidx.wear.compose.material.MaterialTheme
import androidx.wear.compose.material.Text
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var healthMonitor: HealthMonitor
    private var ongoingActivity: PCOSOngoingActivity? = null

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        val allGranted = results.values.all { it }
        if (allGranted) {
            startHealthMonitoring()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        healthMonitor = HealthMonitor(this)
        ongoingActivity = PCOSOngoingActivity(this)

        PCOSOngoingActivity.createChannel(this)

        val requiredPerms = mutableListOf(
            Manifest.permission.BODY_SENSORS,
            Manifest.permission.ACTIVITY_RECOGNITION,
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requiredPerms.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        if (HealthMonitor.hasPermissions(this)) {
            startHealthMonitoring()
        } else {
            permissionLauncher.launch(requiredPerms.toTypedArray())
        }

        setContent {
            MaterialTheme {
                PCOSWatchApp()
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        ongoingActivity?.stop()
    }

    private fun startHealthMonitoring() {
        PassiveHealthService.register(this)

        ongoingActivity?.start()

        lifecycleScope.launch {
            healthMonitor.heartRateFlow().collect { bpm ->
                WatchState.update(watchHeartRate = bpm)
            }
        }

        lifecycleScope.launch {
            WatchState.state.collect { state ->
                val hr = state.watchHeartRate ?: state.phoneHeartRate
                ongoingActivity?.update(
                    heartRate = if (hr > 0) hr else null,
                    activityState = state.activityState
                )
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
        Text("PCOS", style = MaterialTheme.typography.title2)

        val hr = state.watchHeartRate ?: state.phoneHeartRate
        Text(
            if (hr > 0) "$hr BPM" else "— BPM",
            style = MaterialTheme.typography.body1
        )

        Text(
            state.activityState.replaceFirstChar { it.uppercase() },
            style = MaterialTheme.typography.body2
        )

        if (state.dailySteps > 0) {
            Text(
                "${state.dailySteps} steps",
                style = MaterialTheme.typography.caption1
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            val color = if (state.brokerStatus == "ok") MaterialTheme.colors.primary
                         else MaterialTheme.colors.error
            Text("●", color = color, style = MaterialTheme.typography.caption1)
            Text(state.brokerStatus, style = MaterialTheme.typography.caption1)
        }

        if (state.lastResult.isNotBlank()) {
            Text(
                state.lastResult.take(60),
                style = MaterialTheme.typography.caption2,
                maxLines = 3
            )
        }
    }
}
