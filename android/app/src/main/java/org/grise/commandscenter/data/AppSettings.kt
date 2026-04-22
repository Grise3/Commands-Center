package org.grise.commandscenter.data

import kotlinx.serialization.Serializable

@Serializable
data class AppSettings(
    val password: String = "admin"
)
