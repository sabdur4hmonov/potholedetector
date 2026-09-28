package dev.aiengg.potholereporter.media

import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import dev.aiengg.potholereporter.security.NativeBridgeAuthorization

@CapacitorPlugin(name = "ManagedMedia")
class ManagedMediaPlugin : Plugin() {
    // Survive Activity/plugin recreation while the camera/composer owns its activity.
    private companion object { var snapshot: AndroidAppMediaCleanup.Snapshot? = null }

    override fun load() {
        // Retained locations are native-only. A failure is retried during begin/wipe.
        runCatching { AndroidAppMediaCleanup(context).rememberLocations() }
    }

    private fun authorize(call: PluginCall): Boolean {
        if (!NativeBridgeAuthorization.isTrustedMainDocument(bridge.webView.url)) {
            call.reject("Media operation is unavailable from this page")
            return false
        }
        return true
    }

    @PluginMethod
    fun beginOperation(call: PluginCall) {
        if (!authorize(call)) return
        var token: String? = null
        try {
            val kind = call.getString("kind") ?: throw IllegalArgumentException()
            token = AppMediaOperations.gate.begin(kind)
            snapshot = AndroidAppMediaCleanup(context).snapshot(kind)
            call.resolve(JSObject().apply { put("token", token) })
        } catch (_: Exception) {
            token?.let { AppMediaOperations.gate.end(it) }
            call.reject("Finish the active media operation before retrying")
        }
    }

    @PluginMethod
    fun endOperation(call: PluginCall) {
        if (!authorize(call)) return
        val token = call.getString("token")
        if (token == null || token.length != 36 || !AppMediaOperations.gate.owns(token)) {
            call.reject("Invalid media operation")
            return
        }
        var cleared = false
        try {
            val active = snapshot ?: throw IllegalStateException()
            cleared = AndroidAppMediaCleanup(context).finish(active).cleared
        } catch (_: Exception) {
            // Stale artifacts remain discoverable by the authoritative wipe.
        } finally {
            snapshot = null
            AppMediaOperations.gate.end(token)
        }
        if (cleared) call.resolve(JSObject().apply { put("cleaned", true) })
        else call.reject("Temporary media cleanup incomplete; use Delete All Data to retry")
    }
}
