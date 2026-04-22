package org.grise.commandscenter.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class PreferencesManager(private val context: Context) {
    private val key = stringPreferencesKey("app_settings")

    val appSettingsFlow: Flow<AppSettings> = context.dataStore.data.map { prefs ->
        prefs[key]?.let { json ->
            try {
                Json.decodeFromString<AppSettings>(json)
            } catch (_: Exception) {
                AppSettings()
            }
        } ?: AppSettings()
    }

    suspend fun updateSettings(settings: AppSettings) {
        context.dataStore.edit { it[key] = Json.encodeToString(settings) }
    }
}
