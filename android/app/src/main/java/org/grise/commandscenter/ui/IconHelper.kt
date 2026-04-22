package org.grise.commandscenter.ui

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Help
import androidx.compose.ui.graphics.vector.ImageVector

object IconHelper {
    fun getIconByName(name: String): ImageVector {
        if (name.isEmpty()) return Icons.Default.Help
        
        val sanitizedName = if (name[0].isDigit()) "_$name" else name
        
        return try {
            val packageName = "androidx.compose.material.icons.filled"
            val className = "${packageName}.${sanitizedName}Kt"
            val cl = Class.forName(className)
            val getterName = "get$sanitizedName"
            val method = cl.methods.find { it.name == getterName }
            
            if (method != null) {
                method.invoke(null, Icons.Filled) as ImageVector
            } else {
                Icons.Default.Help
            }
        } catch (e: Exception) {
            Icons.Default.Help
        }
    }

    fun isEmoji(s: String): Boolean {
        if (s.isEmpty()) return false
        // Real emojis are non-ASCII characters or start with a surrogate pair
        val firstCodePoint = s.codePointAt(0)
        return firstCodePoint > 127
    }
}
