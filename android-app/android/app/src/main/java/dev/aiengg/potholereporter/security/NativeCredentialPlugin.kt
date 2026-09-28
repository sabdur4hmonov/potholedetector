package dev.aiengg.potholereporter.security

import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import java.util.concurrent.TimeUnit
import java.net.URI
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okio.Buffer
import org.json.JSONObject

internal object NativeBridgeAuthorization {
    fun isTrustedMainDocument(url: String?): Boolean {
        val parsed = runCatching { URI(url ?: return false) }.getOrNull() ?: return false
        return parsed.scheme == "https" && parsed.host == "localhost" && parsed.userInfo == null &&
            parsed.port == -1 && parsed.fragment == null
    }
}

internal data class ValidatedOpenAiRequest(val body: String, val stream: Boolean, val identity: AiRequestIdentity)

internal object NativeOpenAiRequestPolicy {
    private const val MAX_REQUEST_BYTES = 40 * 1024 * 1024
    private val allowedModels = setOf("gpt-5-mini", "gpt-5.6")
    private val allowedFields = setOf("model", "input", "store", "stream", "text", "reasoning", "max_output_tokens")

    fun validate(body: String, stream: Boolean): ValidatedOpenAiRequest {
        require(body.toByteArray(Charsets.UTF_8).size in 2..MAX_REQUEST_BYTES) {
            "OpenAI request is invalid"
        }
        val json = runCatching { JSONObject(body) }.getOrElse {
            throw IllegalArgumentException("OpenAI request is invalid")
        }
        require(json.optString("model") in allowedModels && json.has("input")) {
            "OpenAI request is invalid"
        }
        require(json.opt("store") == false && json.optBoolean("stream", false) == stream) {
            "OpenAI request is invalid"
        }
        // Extra paid tools, conversations/background continuations and alternate pricing
        // parameters are not application operations and cannot enter the budget boundary.
        require(json.keys().asSequence().all { it in allowedFields }) { "OpenAI request is invalid" }
        val name = json.optJSONObject("text")?.optJSONObject("format")?.opt("name")
        require(name == null || name is String) { "OpenAI request is invalid" }
        val purpose = name as? String ?: "general"
        val rawLimit = json.opt("max_output_tokens")
        require(!json.has("max_output_tokens") || rawLimit is Int || rawLimit is Long) { "OpenAI request is invalid" }
        val limit = try {
            AiOutputPolicy.outputLimit(purpose, (rawLimit as? Number)?.toLong())
        } catch (_: AiUsageLimitException) { throw IllegalArgumentException("OpenAI request is invalid") }
        json.put("max_output_tokens", limit)
        val identity = AiRequestIdentity("openai", AiOutputPolicy.ENDPOINT, json.getString("model"), purpose, limit)
        return ValidatedOpenAiRequest(json.toString(), stream, identity)
    }
}

@CapacitorPlugin(name = "SecureCredentials")
class NativeCredentialPlugin : Plugin() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val http = OkHttpClient.Builder()
        .retryOnConnectionFailure(false)
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .callTimeout(35, TimeUnit.SECONDS)
        .followRedirects(false)
        .followSslRedirects(false)
        .build()

    @PluginMethod
    fun getStatus(call: PluginCall) {
        if (!authorize(call)) return
        try {
            resolveStatus(call, store().status())
        } catch (_: Exception) {
            call.reject("Credential status is unavailable")
        }
    }

    @PluginMethod
    fun migrateLegacyCredentials(call: PluginCall) {
        if (!authorize(call)) return
        try {
            val result = store().migrateLegacy(
                openAi = call.getString("openAiKey"),
                dashcamRtsp = call.getString("dashcamRtspUrl")
            )
            call.resolve(statusObject(result.status).apply {
                put("openAiMigrated", result.openAiMigrated)
                put("dashcamRtspMigrated", result.dashcamRtspMigrated)
            })
        } catch (_: Exception) {
            call.reject("Credential migration failed; open Settings and save the credential again")
        }
    }

    @PluginMethod
    fun storeCredentials(call: PluginCall) {
        if (!authorize(call)) return
        try {
            val openAi = call.getString("openAiKey")
            val dashcam = call.getString("dashcamRtspUrl")
            if (openAi == null && dashcam == null) {
                call.reject("No credential was supplied")
                return
            }
            resolveStatus(call, store().put(openAi, dashcam))
        } catch (_: Exception) {
            call.reject("The credential is invalid or could not be stored")
        }
    }

    @PluginMethod
    fun clearCredentials(call: PluginCall) {
        if (!authorize(call)) return
        try {
            store().clearAll()
            resolveStatus(call, SecretStatus(false, false))
        } catch (_: Exception) {
            call.reject("Credentials could not be cleared")
        }
    }

    @PluginMethod
    fun openAiRequest(call: PluginCall) {
        if (!authorize(call, requireVisible = true)) return
        val request = try {
            NativeOpenAiRequestPolicy.validate(
                call.getString("body") ?: "",
                call.getBoolean("stream") ?: false
            )
        } catch (_: Exception) {
            call.reject("OpenAI request is invalid")
            return
        }
        scope.launch {
            try {
                val apiKey = store().readForNativeUse(NativeSecret.OPENAI)
                    ?: throw SecretUnavailableException()
                val httpRequest = Request.Builder()
                    .url(OPENAI_RESPONSES_URL)
                    .header("Authorization", "Bearer $apiKey")
                    .header("Content-Type", "application/json")
                    .post(NonReplayableAiBody(request.body.toRequestBody(JSON_MEDIA_TYPE)))
                    .build()
                NativeAiUsageBudget.reserve(context, request.identity)
                http.newCall(httpRequest).execute().use { response ->
                    // Authentication errors may echo a supplied credential. Return
                    // only their HTTP status; JavaScript already maps it to safe text.
                    val responseText = if (response.isSuccessful) {
                        readBounded(response.body?.source())
                    } else ""
                    call.resolve(JSObject().apply {
                        put("status", response.code)
                        put("ok", response.isSuccessful)
                        put("body", responseText)
                    })
                }
            } catch (_: AiUsageLimitException) {
                call.reject("AI usage limit reached.", "AI_USAGE_LIMIT")
            } catch (_: Exception) {
                call.reject("OpenAI request failed")
            }
        }
    }

    override fun handleOnDestroy() {
        scope.cancel()
        http.dispatcher.cancelAll()
        super.handleOnDestroy()
    }

    private fun authorize(call: PluginCall, requireVisible: Boolean = false): Boolean {
        if (!NativeBridgeAuthorization.isTrustedMainDocument(bridge.webView.url)) {
            call.reject("Credential operation is not allowed from this document")
            return false
        }
        if (requireVisible) {
            val lifecycle = activity as? LifecycleOwner
            if (lifecycle == null || !lifecycle.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
                call.reject("Credential operation requires the visible app")
                return false
            }
        }
        return true
    }

    private fun store(): NativeSecretStore = NativeSecretStore.create(context)

    private fun resolveStatus(call: PluginCall, status: SecretStatus) {
        call.resolve(statusObject(status))
    }

    private fun statusObject(status: SecretStatus): JSObject = JSObject().apply {
        put("openAiConfigured", status.openAiConfigured)
        put("dashcamRtspConfigured", status.dashcamRtspConfigured)
    }

    private fun readBounded(source: okio.BufferedSource?): String {
        if (source == null) return ""
        val output = Buffer()
        var total = 0L
        while (true) {
            val remaining = MAX_RESPONSE_BYTES + 1L - total
            if (remaining <= 0L) throw IllegalStateException("OpenAI response exceeded the limit")
            val count = source.read(output, minOf(8_192L, remaining))
            if (count == -1L) break
            total += count
        }
        if (total > MAX_RESPONSE_BYTES) throw IllegalStateException("OpenAI response exceeded the limit")
        return output.readUtf8()
    }

    private companion object {
        const val OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
        const val MAX_RESPONSE_BYTES = 1024 * 1024L
        val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }
}
