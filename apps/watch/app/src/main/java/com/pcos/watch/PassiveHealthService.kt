package com.pcos.watch

import android.content.Context
import android.util.Log
import androidx.health.services.client.HealthServicesClient
import androidx.health.services.client.PassiveListenerService
import androidx.health.services.client.PassiveMonitoringClient
import androidx.health.services.client.data.DataPointContainer
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.PassiveListenerConfig
import androidx.health.services.client.data.UserActivityInfo
import androidx.health.services.client.data.UserActivityState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class PassiveHealthService : PassiveListenerService() {

    companion object {
        private const val TAG = "PCOS-Passive"

        fun register(context: Context) {
            val healthClient = HealthServicesClient.getClient(context)
            val passiveClient: PassiveMonitoringClient = healthClient.passiveMonitoringClient

            val config = PassiveListenerConfig.builder()
                .setDataTypes(setOf(
                    DataType.HEART_RATE_BPM,
                    DataType.STEPS_DAILY,
                    DataType.DISTANCE_DAILY,
                ))
                .setShouldUserActivityInfoBeRequested(true)
                .build()

            CoroutineScope(Dispatchers.IO + SupervisorJob()).launch {
                try {
                    passiveClient.setPassiveListenerServiceAsync(
                        PassiveHealthService::class.java,
                        config
                    )
                    Log.i(TAG, "Passive listener service registered")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to register passive listener", e)
                }
            }
        }

        fun unregister(context: Context) {
            val healthClient = HealthServicesClient.getClient(context)
            CoroutineScope(Dispatchers.IO + SupervisorJob()).launch {
                try {
                    healthClient.passiveMonitoringClient
                        .clearPassiveListenerServiceAsync()
                    Log.i(TAG, "Passive listener service unregistered")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to unregister passive listener", e)
                }
            }
        }
    }

    override fun onNewDataPointsReceived(dataPoints: DataPointContainer) {
        val hrPoint = dataPoints.getData(DataType.HEART_RATE_BPM)
        hrPoint?.firstOrNull()?.let { dp ->
            val bpm = dp.value.asInt()
            Log.d(TAG, "Background HR: $bpm BPM")
            WatchState.update(watchHeartRate = bpm)
        }

        val stepsPoint = dataPoints.getData(DataType.STEPS_DAILY)
        stepsPoint?.firstOrNull()?.let { dp ->
            val steps = dp.value.asInt()
            Log.d(TAG, "Daily steps: $steps")
            WatchState.update(dailySteps = steps)
        }
    }

    override fun onUserActivityInfoReceived(info: UserActivityInfo) {
        val state = when (info.userActivityState) {
            UserActivityState.USER_ACTIVITY_ASLEEP -> "asleep"
            UserActivityState.USER_ACTIVITY_AWAKE -> "awake"
            UserActivityState.USER_ACTIVITY_EXERCISE -> "exercise"
            else -> "unknown"
        }
        Log.d(TAG, "Activity state: $state")
        WatchState.update(activityState = state)
    }
}
