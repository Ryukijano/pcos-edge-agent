package com.pcos.watch

import android.content.Context
import android.util.Log
import com.google.android.gms.wearable.DataClient
import com.google.android.gms.wearable.DataEvent
import com.google.android.gms.wearable.DataEventBuffer
import com.google.android.gms.wearable.DataMapItem
import com.google.android.gms.wearable.Wearable
import com.google.android.gms.wearable.WearableListenerService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Data Layer listener — receives context updates from the phone app.
 *
 * The phone sends PCOS context (activity state, broker status, task results)
 * via DataItems at path /pcos-context.
 *
 * This service runs on the watch and updates the shared WatchState so
 * the UI and tile can reflect current phone/broker status.
 */
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
        dataEvents.forEach { event ->
            if (event.type == DataEvent.TYPE_CHANGED) {
                val item = event.dataItem
                if (item.uri.path == PATH_CONTEXT) {
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
    )

    fun update(
        activityState: String? = null,
        brokerStatus: String? = null,
        lastResult: String? = null,
        phoneHeartRate: Int? = null,
        watchHeartRate: Int? = null,
    ) {
        _state.value = _state.value.copy(
            activityState = activityState ?: _state.value.activityState,
            brokerStatus = brokerStatus ?: _state.value.brokerStatus,
            lastResult = lastResult ?: _state.value.lastResult,
            phoneHeartRate = phoneHeartRate ?: _state.value.phoneHeartRate,
            watchHeartRate = watchHeartRate ?: _state.value.watchHeartRate,
        )
    }
}
