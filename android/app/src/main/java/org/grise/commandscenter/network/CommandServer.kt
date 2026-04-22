package org.grise.commandscenter.network

import io.ktor.server.application.*
import io.ktor.server.engine.*
import io.ktor.server.netty.*
import io.ktor.server.routing.*
import io.ktor.server.websocket.*
import io.ktor.websocket.*
import io.ktor.serialization.kotlinx.*
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.*
import kotlinx.serialization.json.Json
import java.util.concurrent.ConcurrentHashMap

class CommandServer {
    private var server: EmbeddedServer<*, *>? = null
    private val sessions = ConcurrentHashMap.newKeySet<DefaultWebSocketServerSession>()
    private val _status = MutableStateFlow("Stopped")
    private val _clients = MutableStateFlow(0)
    private val _messages = MutableSharedFlow<String>(replay = 1, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    val status = _status.asStateFlow()
    val connectedClients = _clients.asStateFlow()
    val incomingMessages = _messages.asSharedFlow()

    fun start(port: Int = 8080, password: String) {
        if (server != null) return
        server = embeddedServer(Netty, port, "0.0.0.0") {
            install(WebSockets) { contentConverter = KotlinxWebsocketSerializationConverter(Json) }
            routing {
                webSocket("/ws") {
                    try {
                        send("AUTH_REQUIRED")
                        for (frame in incoming) {
                            if (frame !is Frame.Text) continue
                            val text = frame.readText()
                            if (text.startsWith("AUTH:")) {
                                if (text.substringAfter("AUTH:") == password) {
                                    sessions.add(this); _clients.value = sessions.size; send("AUTH_SUCCESS")
                                } else {
                                    send("AUTH_FAILED"); close(CloseReason(CloseReason.Codes.CANNOT_ACCEPT, "Invalid password"))
                                }
                            } else if (sessions.contains(this)) {
                                _messages.emit(text)
                            }
                        }
                    } catch (_: Exception) {
                    } finally {
                        sessions.remove(this); _clients.value = sessions.size
                    }
                }
            }
        }.start(wait = false)
        _status.value = "Running"
    }

    fun stop() {
        server?.stop(1000, 2000); server = null
        _status.value = "Stopped"; _clients.value = 0; sessions.clear()
    }

    fun sendMessage(msg: String) = scope.launch {
        sessions.forEach { try { it.send(msg) } catch (_: Exception) {} }
    }
}
