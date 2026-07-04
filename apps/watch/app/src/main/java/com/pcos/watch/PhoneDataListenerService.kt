package com.pcos.watch

import android.util.Log
import com.google.android.gms.common.ConnectionResult
import com.google.android.gms.common.GoogleApiAvailability
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.WearableListenerService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class PhoneDataListenerService : WearableListenerService() {

    companion object {
        private const val TAG = "PCOS-DataLayer"
        private const val PATH_CONTEXT = "/pcos-context"
        const val KEY_ACTIVITY_STATE = "activity_state"
        const val KEY_BROKER_STATUS = "broker_status"
        const val KEY_LAST_RESULT = "last_result"
        const val KEY_HEART_RATE = "heart_rate"
    }

    override fun onDataChanged(dataEvents: DataEventBuffer) {
        if (GoogleApiAvailability.getInstance()
            .isGooglePlayServicesAvailable(this) != ConnectionResult.SUCCESS) {
            Log.w(TAG, "Google Play Services unavailable, ignoring data events")
            return
        }

        dataEvents.forEach { event ->
            if (event.type == DataEvent.TYPE_CHANGED) {
                val item = event.dataItem
                if (item.uri.path == PATH_CONTEXT) {
                    try {
                        val dataMap = DataMapItem.fromDataItem(item).dataMap
                        val activityState = dataMap.getString(KEY_ACTIVITY_STATE, "idle")
                        val brokerStatus = dataMap.getString(KEY_BROKER_STATUS, "unknown")
                        val lastResult = dataMap.getString(KEY_LAST_RESULT, "")
                        val heartRate = dataMap.getInt(KEY_HEART_RATE, 0)

                        Log.i(TAG, "Context update: activity=$activityState broker=$brokerStatus hr=$heartRate")

                        WatchState.update(
                            activityState = activityState,
                            brokerStatus = brokerStatus,
                            lastResult = lastResult,
                            phoneHeartRate = heartRate,
                        )
                    } catch (e: Exception) {
                        Log.e(TAG, "Failed to parse data item", e)
                    }
                }
            }
        }
    }
}

/**
 * Shared state between Data Layer listener, UI, and tile.
 */
object WatchState {
    private val _state = MutableStateFlow(WatchData())
    val state: StateFlow<WatchData> = _state.asStateFlow()

    data class WatchData(
        val activityState: String = "idle",
        val brokerStatus: String = "unknown",
        val lastResult: String = "",
        val phoneHeartRate: Int = 0,
        val watchHeartRate: Int? = null,
        val dailySteps: Int = 0,
    )

    fun update(
        activityState: String? = null,
        brokerStatus: String? = null,
        lastResult: String? = null,
        phoneHeartRate: Int? = null,
        watchHeartRate: Int? = null,
        dailySteps: Int? = null,
    ) {
        _state.value = _state.value.copy(
            activityState = activityState ?: _state.value.activityState,
            brokerStatus = brokerStatus ?: _state.value.brokerStatus,
            lastResult = lastResult ?: _state.value.lastResult,
            phoneHeartRate = phoneHeartRate ?: _state.value.phoneHeartRate,
            watchHeartRate = watchHeartRate ?: _state.value.watchHeartRate,
            dailySteps = dailySteps ?: _state.value.dailySteps,
        )
    }
}
