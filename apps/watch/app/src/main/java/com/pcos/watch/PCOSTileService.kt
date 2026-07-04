package com.pcos.watch

import androidx.wear.protolayout.DimensionBuilders
import androidx.wear.protolayout.LayoutElementBuilders
import androidx.wear.protolayout.LayoutElementBuilders.VERTICAL_ALIGN_CENTER
import androidx.wear.protolayout.MaterialColors
import androidx.wear.protolayout.TimelineBuilders
import androidx.wear.tiles.RequestBuilders
import androidx.wear.tiles.TileBuilders
import androidx.wear.tiles.TileService
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

class PCOSTileService : TileService() {

    companion object {
        private const val TILE_ID = "pcos_tile"
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onTileRequest(
        requestParams: RequestBuilders.TileRequest
    ): ListenableFuture<TileBuilders.Tile> {
        val future = Futures.immediateFuture(
            runBlocking(Dispatchers.Default) {
                val state = WatchState.state.first()
                buildTile(state)
            }
        )
        return future
    }

    private fun buildTile(state: WatchState.WatchData): TileBuilders.Tile {
        val layout = buildTileLayout(state)

        val timeline = TimelineBuilders.Timeline.Builder()
            .addTimelineEntry(
                TimelineBuilders.TimelineEntry.Builder()
                    .setLayout(layout)
                    .build()
            )
            .build()

        return TileBuilders.Tile.Builder()
            .setResourcesVersion("1")
            .setTimeline(timeline)
            .build()
    }

    override fun onTileResourcesRequest(
        requestParams: RequestBuilders.ResourcesRequest
    ): ListenableFuture<RequestBuilders.Resources> {
        return Futures.immediateFuture(
            RequestBuilders.Resources.Builder().setVersion("1").build()
        )
    }

    private fun buildTileLayout(state: WatchState.WatchData): LayoutElementBuilders.Layout {
        val hr = state.watchHeartRate ?: state.phoneHeartRate
        val hrText = if (hr > 0) "$hr BPM" else "—"
        val statusColor = if (state.brokerStatus == "ok") MaterialColors.PRIMARY
                          else MaterialColors.ERROR
        val stepsText = if (state.dailySteps > 0) "${state.dailySteps} steps" else ""

        val columnBuilder = LayoutElementBuilders.Column.Builder()
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText("PCOS")
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(16f))
                            .build()
                    )
                    .build()
            )
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText(hrText)
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(28f))
                            .build()
                    )
                    .build()
            )
            .addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText(state.activityState)
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(14f))
                            .setColor(statusColor)
                            .build()
                    )
                    .build()
            )

        if (stepsText.isNotEmpty()) {
            columnBuilder.addContent(
                LayoutElementBuilders.Text.Builder()
                    .setText(stepsText)
                    .setFontStyle(
                        LayoutElementBuilders.FontStyle.Builder()
                            .setSize(DimensionBuilders.sp(12f))
                            .build()
                    )
                    .build()
            )
        }

        return LayoutElementBuilders.Layout.Builder()
            .setRoot(
                columnBuilder
                    .setVerticalAlignment(VERTICAL_ALIGN_CENTER)
                    .build()
            )
            .build()
    }
}
