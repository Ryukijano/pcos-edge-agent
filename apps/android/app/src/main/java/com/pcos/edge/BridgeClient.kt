package com.pcos.edge

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import org.json.JSONObject
import java.net.URI

/**
 * Bridge Client — WebSocket connection to PCOS Context Broker.
 *
 * Enables Chrome ↔ Android relay:
 * - Chrome sends {context, task} → Android executes LiteRT-LM → result streams back
 * - Android registers as "android" role on the bridge
 */
class BridgeClient(private val context: Context) {

    private val brokerUrl = "http://localhost:8000"
    private val bridgeUrl = "ws://localhost:8000/bridge"
    private var ws: BridgeWebSocket? = null
    private var clientId: String? = null

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var keepaliveJob: Job? = null
    private var reconnectJob: Job? = null
    private var reconnectAttempts = 0

    private val keepaliveIntervalMs = 20_000L
    private val reconnectBaseMs = 3_000L
    private val reconnectMaxMs = 30_000L

    var onMessage: ((JSONObject) -> Unit)? = null

    fun connect() {
        if (ws != null && ws?.isOpen == true) return
        reconnectJob?.cancel()
        ws = BridgeWebSocket(URI(bridgeUrl))
        ws?.connect()
    }

    fun disconnect() {
        reconnectJob?.cancel()
        keepaliveJob?.cancel()
        ws?.close()
        ws = null
        clientId = null
        reconnectAttempts = 0
    }

    fun isConnected(): Boolean = ws?.isOpen == true

    fun send(message: JSONObject) {
        ws?.send(message.toString())
    }

    fun sendResult(target: String, result: String) {
        val msg = JSONObject().apply {
            put("type", "result")
            put("target", target)
            put("payload", JSONObject().put("result", result))
        }
        send(msg)
    }

    suspend fun checkBroker(): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = java.net.URL("$brokerUrl/health")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.connectTimeout = 2000
            conn.requestMethod = "GET"
            val ok = conn.responseCode == 200
            conn.disconnect()
            ok
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Route a task via the broker's /execute endpoint.
     * Returns the JSON response or null if broker is unavailable.
     */
    suspend fun routeViaBroker(text: String, model: PCOSModel): JSONObject? = withContext(Dispatchers.IO) {
        try {
            val task = JSONObject().apply {
                put("text", text)
                put("task_type", if (model == PCOSModel.FUNCTION_GEMMA) "action" else "transform")
                put("is_short", text.length < 2000)
                put("requires_action", model == PCOSModel.FUNCTION_GEMMA)
            }
            val body = JSONObject().apply {
                put("task", task)
                put("context", JSONObject())
            }

            val url = java.net.URL("$brokerUrl/execute")
            val conn = url.openConnection() as java.net.HttpURLConnection
            conn.connectTimeout = 3000
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            conn.outputStream.use { it.write(body.toString().toByteArray()) }

            if (conn.responseCode == 200) {
                val response = conn.inputStream.bufferedReader().readText()
                JSONObject(response)
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    private fun startKeepalive() {
        keepaliveJob?.cancel()
        keepaliveJob = scope.launch {
            while (true) {
                delay(keepaliveIntervalMs)
                if (ws?.isOpen == true) {
                    val ping = JSONObject().apply { put("type", "ping") }
                    ws?.send(ping.toString())
                }
            }
        }
    }

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        val delayMs = minOf(reconnectBaseMs * (1L shl reconnectAttempts), reconnectMaxMs)
        reconnectAttempts++
        Log.w("PCOS-Bridge", "Reconnecting in ${delayMs}ms (attempt $reconnectAttempts)")
        reconnectJob = scope.launch {
            delay(delayMs)
            connect()
        }
    }

    private inner class BridgeWebSocket(uri: URI) : WebSocketClient(uri) {
        override fun onOpen(handshake: ServerHandshake?) {
            reconnectAttempts = 0
            val register = JSONObject().apply {
                put("type", "register")
                put("role", "android")
            }
            send(register.toString())
            startKeepalive()
        }

        override fun onMessage(message: String?) {
            try {
                val msg = JSONObject(message ?: return)
                when (msg.optString("type")) {
                    "registered" -> clientId = msg.optString("client_id")
                    "pong" -> { /* keepalive response */ }
                    else -> onMessage?.invoke(msg)
                }
            } catch (e: Exception) {
                // Ignore malformed messages
            }
        }

        override fun onClose(code: Int, reason: String?, remote: Boolean) {
            clientId = null
            keepaliveJob?.cancel()
            scheduleReconnect()
        }

        override fun onError(e: Exception?) {
            Log.e("PCOS-Bridge", "WebSocket error", e)
        }
    }
}
