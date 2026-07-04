package com.pcos.edge

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

/**
 * PCOS Foreground Service — keeps the LiteRT-LM model warm and
 * WebSocket bridge connected even when the app is backgrounded.
 *
 * Notification shows PCOS status so the user knows local AI is active.
 */
class PCOSService : Service() {

    companion object {
        private const val CHANNEL_ID = "pcos_service"
        private const val NOTIFICATION_ID = 1
    }

    private var bridgeClient: BridgeClient? = null
    private var litertManager: LiteRTManager? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        bridgeClient = BridgeClient(applicationContext)
        litertManager = LiteRTManager(applicationContext)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("PCOS Active")
            .setContentText("Local AI runtime running — model warm, bridge connected")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .build()

        startForeground(NOTIFICATION_ID, notification)

        // Connect bridge
        bridgeClient?.connect()

        // Pre-download and load FunctionGemma for fast function calls
        Thread {
            try {
                if (litertManager?.isModelDownloaded(PCOSModel.FUNCTION_GEMMA) != true) {
                    kotlinx.coroutines.runBlocking {
                        litertManager?.ensureModelDownloaded(PCOSModel.FUNCTION_GEMMA)
                    }
                }
                kotlinx.coroutines.runBlocking {
                    litertManager?.loadModel(PCOSModel.FUNCTION_GEMMA)
                }
            } catch (e: Exception) {
                android.util.Log.w("PCOS-Service", "Model preload failed", e)
            }
        }.start()

        return START_STICKY
    }

    override fun onDestroy() {
        bridgeClient?.disconnect()
        litertManager?.close()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "PCOS Service",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "PCOS local AI runtime status"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }
}
