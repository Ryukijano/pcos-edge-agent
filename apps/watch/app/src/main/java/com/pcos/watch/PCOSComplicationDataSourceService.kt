package com.pcos.watch

import android.app.PendingIntent
import android.content.Intent
import android.graphics.drawable.Icon
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.data.SmallImage
import androidx.wear.watchface.complications.data.SmallImageComplicationData
import androidx.wear.watchface.complications.data.SmallImageType
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import androidx.wear.watchface.complications.datasource.SuspendingComplicationDataSourceService

class PCOSComplicationDataSourceService : SuspendingComplicationDataSourceService() {

    companion object {
        const val COMPLICATION_ID = "pcos_complication"
    }

    override suspend fun onComplicationRequest(
        request: ComplicationRequest,
    ): ComplicationData? {
        val data = WatchState.state.value
        val hr = data.watchHeartRate ?: data.phoneHeartRate
        val hrText = if (hr > 0) "$hr bpm" else "—"
        val activityIcon = when (data.activityState) {
            "executing", "local" -> android.R.drawable.ic_media_play
            "chrome" -> android.R.drawable.ic_menu_compass
            "cloud" -> android.R.drawable.ic_menu_upload
            else -> android.R.drawable.ic_menu_recent_history
        }

        return when (request.complicationType) {
            ComplicationType.SHORT_TEXT -> ShortTextComplicationData.Builder(
                text = PlainComplicationText.Builder(hrText).build(),
                contentDescription = PlainComplicationText.Builder(
                    "PCOS: $hrText, ${data.activityState}"
                ).build(),
            )
                .setTitle(
                    PlainComplicationText.Builder(data.activityState.replaceFirstChar { it.uppercase() }).build()
                )
                .setIcon(Icon.createWithResource(this, android.R.drawable.ic_heart))
                .setTapAction(
                    PendingIntent.getActivity(
                        this, 0,
                        Intent(this, MainActivity::class.java)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                        PendingIntent.FLAG_IMMUTABLE,
                    )
                )
                .build()

            ComplicationType.SMALL_IMAGE -> SmallImageComplicationData.Builder(
                smallImage = SmallImage.Builder(
                    Icon.createWithResource(this, activityIcon),
                    SmallImageType.ICON,
                ).build(),
                contentDescription = PlainComplicationText.Builder(hrText).build(),
            )
                .setTapAction(
                    PendingIntent.getActivity(
                        this, 0,
                        Intent(this, MainActivity::class.java)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                        PendingIntent.FLAG_IMMUTABLE,
                    )
                )
                .build()

            else -> null
        }
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? {
        return when (type) {
            ComplicationType.SHORT_TEXT -> ShortTextComplicationData.Builder(
                text = PlainComplicationText.Builder("72 bpm").build(),
                contentDescription = PlainComplicationText.Builder("PCOS: 72 bpm, idle").build(),
            )
                .setTitle(PlainComplicationText.Builder("Idle").build())
                .setIcon(Icon.createWithResource(this, android.R.drawable.ic_heart))
                .build()

            ComplicationType.SMALL_IMAGE -> SmallImageComplicationData.Builder(
                smallImage = SmallImage.Builder(
                    Icon.createWithResource(this, android.R.drawable.ic_heart),
                    SmallImageType.ICON,
                ).build(),
                contentDescription = PlainComplicationText.Builder("72 bpm").build(),
            ).build()

            else -> null
        }
    }
}
