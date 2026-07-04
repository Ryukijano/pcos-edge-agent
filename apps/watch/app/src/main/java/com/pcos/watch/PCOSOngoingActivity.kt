package com.pcos.watch

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.wear.ongoing.OngoingActivity
import androidx.wear.ongoing.Status

class PCOSOngoingActivity(private val context: Context) {

    companion object {
        private const val TAG = "PCOS-Ongoing"
        private const val CHANNEL_ID = "pcos_health_monitoring"
        private const val NOTIFICATION_ID = 1001

        fun createChannel(context: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val manager = context.getSystemService(NotificationManager::class.java)
                if (manager?.getNotificationChannel(CHANNEL_ID) == null) {
                    val channel = NotificationChannel(
                        CHANNEL_ID,
                        context.getString(R.string.notification_channel_name),
                        NotificationManager.IMPORTANCE_LOW
                    ).apply {
                        description = context.getString(R.string.notification_channel_desc)
                        setShowBadge(false)
                    }
                    manager?.createNotificationChannel(channel)
                }
            }
        }
    }

    fun start() {
        createChannel(context)

        val launchIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notificationBuilder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setContentTitle(context.getString(R.string.ongoing_activity_title))
            .setContentText(context.getString(R.string.ongoing_activity_text))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setContentIntent(pendingIntent)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOngoing(true)

        val status = Status.Builder()
            .addTemplate("#state# · #hr#")
            .addPart("state", Status.TextPart("Monitoring"))
            .addPart("hr", Status.TextPart("— BPM"))
            .build()

        val ongoingActivity = OngoingActivity.Builder(
            context, NOTIFICATION_ID, notificationBuilder
        )
            .setStaticIcon(android.R.drawable.ic_dialog_info)
            .setTouchIntent(pendingIntent)
            .setStatus(status)
            .build()

        ongoingActivity.apply(context)

        val manager = context.getSystemService(NotificationManager::class.java)
        manager?.notify(NOTIFICATION_ID, notificationBuilder.build())

        Log.i(TAG, "Ongoing activity started")
    }

    fun update(heartRate: Int?, activityState: String) {
        val hrText = if (heartRate != null && heartRate > 0) "$heartRate BPM" else "— BPM"
        val stateText = activityState.replaceFirstChar { it.uppercase() }

        val status = Status.Builder()
            .addTemplate("#state# · #hr#")
            .addPart("state", Status.TextPart(stateText))
            .addPart("hr", Status.TextPart(hrText))
            .build()

        val launchIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notificationBuilder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setContentTitle(context.getString(R.string.ongoing_activity_title))
            .setContentText("$stateText · $hrText")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setContentIntent(pendingIntent)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOngoing(true)

        val ongoingActivity = OngoingActivity.Builder(
            context, NOTIFICATION_ID, notificationBuilder
        )
            .setStaticIcon(android.R.drawable.ic_dialog_info)
            .setTouchIntent(pendingIntent)
            .setStatus(status)
            .build()

        ongoingActivity.apply(context)

        val manager = context.getSystemService(NotificationManager::class.java)
        manager?.notify(NOTIFICATION_ID, notificationBuilder.build())

        Log.d(TAG, "Ongoing activity updated: $stateText · $hrText")
    }

    fun stop() {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager?.cancel(NOTIFICATION_ID)
        Log.i(TAG, "Ongoing activity stopped")
    }
}
