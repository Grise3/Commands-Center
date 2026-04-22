package org.grise.commandscenter.data

import kotlinx.serialization.Serializable

@Serializable
data class DynamicButtonConfig(
    val iconName: String,
    val toggleIconName: String? = null,
    val command: String,
    val notificationText: String,
    val isToggle: Boolean = false,
    val isToggled: Boolean = false,
    val activeColor: String? = null
)

@Serializable
data class DynamicUIConfig(
    val buttons: List<DynamicButtonConfig> = emptyList()
)
