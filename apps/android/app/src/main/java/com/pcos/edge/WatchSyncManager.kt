package com.pcos.edge

import android.content.Context
import android.util.Log
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.common.GoogleApiAvailability
import com.google.android.gms.wearable.DataClient
import com.google.android.gms.wearable.PutDataMapRequest
import com.google.android.gms.wearable.Wearable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

class WatchSyncManager(private val context: Context) {

    companion object {
        private const val TAG = "PCOS-WatchSync"
        private const val PATH_CONTEXT = "/pcos-context"

        const val KEY_ACTIVITY_STATE = "activity_state"
        const val KEY_BROKER_STATUS = "broker_status"
        const val KEY_LAST_RESULT = "last_result"
        const val KEY_HEART_RATE = "heart_rate"
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    fun isDataLayerAvailable(): Boolean {
        return GoogleApiAvailability.getInstance()
            .isGooglePlayServicesAvailable(context) == ConnectionResult.SUCCESS
    }

    fun syncContext(
        activityState: String,
        brokerStatus: String,
        lastResult: String,
        heartRate: Int = 0,
        urgent: Boolean = true,
    ) {
        if (!isDataLayerAvailable()) {
            Log.w(TAG, "Data Layer unavailable, skipping sync")
            return
        }

        scope.launch {
            try {
                val dataMap = PutDataMapRequest.create(PATH_CONTEXT).apply {
                    dataMap.putString(KEY_ACTIVITY_STATE, activityState)
                    dataMap.putString(KEY_BROKER_STATUS, brokerStatus)
                    dataMap.putString(KEY_LAST_RESULT, lastResult)
                    dataMap.putInt(KEY_HEART_RATE, heartRate)
                    if (urgent) {
                        setUrgent()
                    }
                }

                val dataClient: DataClient = Wearable.getDataClient(context)
                dataClient.putDataItem(dataMap.asPutDataRequest()).await()
                Log.d(TAG, "Context synced: activity=$activityState broker=$brokerStatus urgent=$urgent")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to sync context to watch", e)
            }
        }
    }
}
