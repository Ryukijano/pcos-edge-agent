package com.pcos.watch

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.runBlocking

class RegisterPassiveDataWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(appContext, workerParams) {

    companion object {
        private const val TAG = "PCOS-Worker"
    }

    override suspend fun doWork(): Result {
        return try {
            Log.i(TAG, "Re-registering passive monitoring after boot")
            PassiveHealthService.register(applicationContext)
            Result.success()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to re-register passive monitoring", e)
            Result.retry()
        }
    }
}
