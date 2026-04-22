package org.grise.commandscenter.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import org.grise.commandscenter.data.AppSettings
import org.grise.commandscenter.data.DynamicUIConfig
import org.grise.commandscenter.data.PreferencesManager
import org.grise.commandscenter.network.CommandServer
import org.grise.commandscenter.network.NetworkUtils
import kotlinx.serialization.json.Json

class CommandsViewModel(application: Application) : AndroidViewModel(application) {
    private val prefsManager = PreferencesManager(application)
    private val server = CommandServer()
    private val json = Json { ignoreUnknownKeys = true; coerceInputValues = true }

    val appSettings: StateFlow<AppSettings> = prefsManager.appSettingsFlow.stateIn(
        viewModelScope, SharingStarted.WhileSubscribed(5000), AppSettings()
    )

    private val _dynamicConfig = MutableStateFlow(DynamicUIConfig())
    val dynamicConfig = _dynamicConfig.asStateFlow()

    val serverStatus = server.status
    val connectedClients = server.connectedClients
    val localIp = NetworkUtils.getLocalIpAddress() ?: "Unknown IP"

    init {
        viewModelScope.launch(Dispatchers.IO) {
            launch {
                appSettings.collect { if (server.status.value == "Stopped") server.start(password = it.password) }
            }
            launch {
                server.incomingMessages.collect { msg ->
                    try {
                        _dynamicConfig.value = json.decodeFromString<DynamicUIConfig>(msg)
                    } catch (_: Exception) { }
                }
            }
        }
    }

    fun onButtonClick(command: String, notificationText: String) =
        server.sendMessage("CMD:$command|NOTIF:$notificationText")

    fun updateSettings(settings: AppSettings) = viewModelScope.launch {
        prefsManager.updateSettings(settings)
        server.stop()
        server.start(password = settings.password)
    }

    override fun onCleared() = server.stop()
}
