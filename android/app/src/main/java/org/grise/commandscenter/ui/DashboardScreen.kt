package org.grise.commandscenter.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.grise.commandscenter.data.DynamicButtonConfig
import kotlin.math.min

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    viewModel: CommandsViewModel,
    onNavigateToSettings: () -> Unit
) {
    val dynamicConfig by viewModel.dynamicConfig.collectAsState()
    val serverStatus by viewModel.serverStatus.collectAsState()
    val connectedClients by viewModel.connectedClients.collectAsState()

    val backgroundColor = Color(0xFF0F111A)
    val surfaceColor = Color(0xFF1A1D2E)
    val accentColor = Color(0xFF00E5FF)

    Scaffold(
        containerColor = backgroundColor,
        topBar = {
            CenterAlignedTopAppBar(
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent,
                    titleContentColor = Color.White
                ),
                title = {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            "COMMANDS CENTER",
                            style = MaterialTheme.typography.titleSmall
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(RoundedCornerShape(50))
                                    .background(if (serverStatus == "Running") Color.Green else Color.Red)
                            )
                            Spacer(Modifier.width(6.dp))
                            Text(
                                text = if (connectedClients > 0) "$connectedClients CLIENTS" else "WAITING...",
                                style = MaterialTheme.typography.labelSmall,
                                color = Color.Gray
                            )
                        }
                    }
                },
                navigationIcon = {
                    Column(Modifier.padding(start = 16.dp)) {
                        Text("IP", style = MaterialTheme.typography.labelSmall, color = Color.Gray)
                        Text(viewModel.localIp, style = MaterialTheme.typography.labelMedium, color = Color.White)
                    }
                },
                actions = {
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings", tint = Color.Gray)
                    }
                }
            )
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
                .padding(24.dp),
            contentAlignment = Alignment.Center
        ) {
            val buttons = dynamicConfig.buttons.take(9)

            BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
                val spacing = 16.dp

                val availableWidth = maxWidth - (spacing * 2)
                val availableHeight = maxHeight - (spacing * 2)
                val cellSize = if (availableWidth < availableHeight) availableWidth / 3 else availableHeight / 3

                if (buttons.isEmpty()) {
                    Surface(
                        color = surfaceColor,
                        shape = RoundedCornerShape(24.dp),
                        modifier = Modifier.padding(32.dp)
                    ) {
                        Text(
                            "Awaiting Host Configuration...",
                            modifier = Modifier.padding(32.dp),
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color.LightGray
                        )
                    }
                } else {
                    Column(
                        verticalArrangement = Arrangement.spacedBy(spacing),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        for (row in 0 until 3) {
                            Row(
                                horizontalArrangement = Arrangement.spacedBy(spacing),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                for (col in 0 until 3) {
                                    val index = row * 3 + col
                                    if (index < buttons.size) {
                                        val button = buttons[index]
                                        CommandButton(
                                            config = button,
                                            size = cellSize,
                                            onClick = { viewModel.onButtonClick(button.command, button.notificationText) }
                                        )
                                    } else {
                                        Spacer(modifier = Modifier.size(cellSize))
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

private val AccentColor = Color(0xFF00E5FF)
private val SurfaceColor = Color(0xFF1A1D2E)
private val GradientStart = Color(0xFF2A2D3E)

@Composable
fun CommandButton(
    config: DynamicButtonConfig,
    size: Dp,
    onClick: () -> Unit
) {
    val iconName = if (config.isToggled && !config.toggleIconName.isNullOrEmpty()) config.toggleIconName else config.iconName
    val isEmoji = IconHelper.isEmoji(iconName)
    val targetColor = config.activeColor?.let {
        try { Color(android.graphics.Color.parseColor(it)) } catch (_: Exception) { Color(0xFFFF5252) }
    } ?: AccentColor

    val accent by animateColorAsState(if (config.isToggled) targetColor else AccentColor, label = "c")
    val glowWidth by animateFloatAsState(if (config.isToggled) 0.8f else 0.3f, label = "g")
    val shape = RoundedCornerShape(24.dp)

    Box(
        modifier = Modifier
            .size(size)
            .shadow(if (config.isToggled) 20.dp else 12.dp, shape, ambientColor = accent, spotColor = accent)
            .clip(shape)
            .background(SurfaceColor)
            .background(
                Brush.linearGradient(
                    if (config.isToggled) listOf(accent.copy(0.2f), SurfaceColor) else listOf(GradientStart, SurfaceColor)
                )
            )
            .border(1.dp, if (config.isToggled) accent.copy(0.5f) else Color.White.copy(0.1f), shape)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        if (isEmoji) {
            Text(iconName, fontSize = (size.value * 0.45f).sp)
        } else {
            Icon(IconHelper.getIconByName(iconName), null, Modifier.size(size * 0.45f), accent)
        }
        Box(
            Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 8.dp)
                .width(size * glowWidth)
                .height(4.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(accent.copy(0.7f))
        )
    }
}
