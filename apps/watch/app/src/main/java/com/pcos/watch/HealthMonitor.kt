package com.pcos.watch

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.util.Log
import androidx.core.content.ContextCompat
import androidx.health.services.client.HealthServicesClient
import androidx.health.services.client.MeasureCallback
import androidx.health.services.client.MeasureClient
import androidx.health.services.client.PassiveMonitoringClient
import androidx.health.services.client.data.Availability
import androidx.health.services.client.data.DataPoint
import androidx.health.services.client.data.DataType
import androidx.health.services.client.data.Value
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow

class HealthMonitor(context: Context) {

    companion object {
        private const val TAG = "PCOS-Health"

        fun hasPermissions(context: Context): Boolean {
            val bodySensors = ContextCompat.checkSelfPermission(
                context, Manifest.permission.BODY_SENSORS
            ) == PackageManager.PERMISSION_GRANTED
            val activityRecog = ContextCompat.checkSelfPermission(
                context, Manifest.permission.ACTIVITY_RECOGNITION
            ) == PackageManager.PERMISSION_GRANTED
            return bodySensors && activityRecog
        }
    }

    private val healthClient = HealthServicesClient.getClient(context)
    private val measureClient: MeasureClient = healthClient.measureClient
    private val passiveClient: PassiveMonitoringClient = healthClient.passiveMonitoringClient

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

        try {
            measureClient.registerMeasureCallback(DataType.HEART_RATE_BPM, callback)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to register measure callback", e)
            trySend(null)
        }

        awaitClose {
            try {
                measureClient.unregisterMeasureCallback(DataType.HEART_RATE_BPM, callback)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to unregister measure callback", e)
            }
        }
    }

    suspend fun isHeartRateAvailable(): Boolean {
        return try {
            val capabilities = measureClient.getCapabilities()
            DataType.HEART_RATE_BPM in capabilities.supportedDataTypesMeasure
        } catch (e: Exception) {
            Log.e(TAG, "Failed to check HR capabilities", e)
            false
        }
    }

    suspend fun isPassiveHeartRateAvailable(): Boolean {
        return try {
            val capabilities = passiveClient.getCapabilities()
            DataType.HEART_RATE_BPM in capabilities.supportedDataTypesPassiveMonitoring
        } catch (e: Exception) {
            Log.e(TAG, "Failed to check passive HR capabilities", e)
            false
        }
    }
}
