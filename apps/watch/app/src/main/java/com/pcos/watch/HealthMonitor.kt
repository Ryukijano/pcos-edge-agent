package com.pcos.watch

import android.content.Context
import android.util.Log
import androidx.health.services.client.HealthServicesClient
import androidx.health.services.client.MeasureCallback
import androidx.health.services.client.MeasureClient
import androidx.health.services.client.data.Availability
import androidx.health.services.client.data.DataPoint
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.Value
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

/**
 * Health Services wrapper — heart rate monitoring and passive activity tracking.
 *
 * Uses MeasureClient for on-screen rapid updates and PassiveMonitoringClient
 * for background activity state changes.
 */
class HealthMonitor(context: Context) {

    companion object {
        private const val TAG = "PCOS-Health"
    }

    private val healthClient = HealthServicesClient.getClient(context)
    private val measureClient: MeasureClient = healthClient.measureClient

    /**
     * Stream heart rate updates via Flow.
     * Call this only while the app is in the foreground to save battery.
     */
    fun heartRateFlow(): Flow<Int?> = callbackFlow {
        val callback = object : MeasureCallback {
            override fun onAvailabilityChanged(
                dataType: DataType<*, *>,
                availability: Availability
            ) {
                if (availability == Availability.UNAVAILABLE) {
                    Log.w(TAG, "Heart rate sensor unavailable")
                    trySend(null)
                }
            }

            override fun onDataReceived(data: List<DataPoint<*, *>>) {
                val hrPoint = data.firstOrNull { it.dataType == DataType.HEART_RATE_BPM }
                val bpm = hrPoint?.values?.firstOrNull()?.let { (it as? Value.IntValue)?.int }
                trySend(bpm)
            }
        }

        measureClient.registerMeasureCallback(DataType.HEART_RATE_BPM, callback)

        awaitClose {
            measureClient.unregisterMeasureCallback(DataType.HEART_RATE_BPM, callback)
        }
    }

    /**
     * Check if heart rate monitoring is available on this device.
     */
    suspend fun isHeartRateAvailable(): Boolean {
        return try {
            val capabilities = measureClient.getCapabilities()
            DataType.HEART_RATE_BPM in capabilities.supportedDataTypesMeasure
        } catch (e: Exception) {
            Log.e(TAG, "Failed to check HR capabilities", e)
            false
        }
    }
}
