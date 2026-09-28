package dev.aiengg.potholereporter.drive

import java.net.URI

/** Native-only transport authorization. Parsing performs no DNS or network operations. */
internal object NativeRtspTransportPolicy {
    const val INVALID_ENDPOINT = "The dashcam endpoint is invalid"
    const val PLAINTEXT_REJECTED = "Unencrypted dashcam transport is blocked. Secure RTSP (rtsps://) is required. Select Phone camera."
    const val SECURE_UNAVAILABLE = "Dashcam is disabled: this app cannot provide verified secure RTSP (rtsps://). Select Phone camera."

    // Pinned Media3 1.10.1 uses SocketFactory.getDefault(), not verified RTSPS/TLS.
    // This is a native build capability, never a bridge or user setting. Enabling it
    // requires an audited encrypted/authenticated control AND media transport.
    private const val VERIFIED_SECURE_TRANSPORT_SUPPORTED = false

    fun requireProductionEndpoint(value: String?): String = withProductionEndpoint(value) { it }

    /** The sole gate for creation of any RTSP network/client resource. */
    fun <T> withProductionEndpoint(value: String?, connect: (String) -> T): T {
        val endpoint = validateSecureEndpoint(value)
        if (!VERIFIED_SECURE_TRANSPORT_SUPPORTED) {
            throw IllegalArgumentException(SECURE_UNAVAILABLE)
        }
        return connect(endpoint)
    }

    private fun validateSecureEndpoint(value: String?): String {
        val candidate = value?.trim().orEmpty()
        invalidUnless(candidate.isNotEmpty() && candidate.length <= 2048)
        invalidUnless(candidate.none { it.isWhitespace() || it.isISOControl() || it == '\\' || it.code > 127 })
        // URISyntaxException includes the credential-bearing input; discard its cause.
        val uri = try { URI(candidate) } catch (_: Exception) {
            throw IllegalArgumentException(INVALID_ENDPOINT)
        }
        if (uri.scheme.equals("rtsp", ignoreCase = true)) {
            throw IllegalArgumentException(PLAINTEXT_REJECTED)
        }
        invalidUnless(uri.scheme.equals("rtsps", ignoreCase = true) && !uri.isOpaque)
        invalidUnless(uri.fragment == null && !uri.host.isNullOrEmpty())
        invalidUnless(uri.port == -1 || uri.port in 1..65535)
        val authority = uri.rawAuthority ?: throw IllegalArgumentException(INVALID_ENDPOINT)
        invalidUnless(authority.count { it == '@' } <= 1)
        val userInfo = uri.rawUserInfo
        if (userInfo != null) {
            invalidUnless(userInfo.substringBefore(':').isNotEmpty())
            // Reject encoded control bytes and backslashes, including nested encodings.
            invalidUnless(!Regex("%(?:0[0-9a-f]|1[0-9a-f]|7f|5c|25)", RegexOption.IGNORE_CASE).containsMatchIn(userInfo))
        }
        val hostPort = authority.substringAfterLast('@')
        val host = uri.host ?: throw IllegalArgumentException(INVALID_ENDPOINT)
        if (host.startsWith("[")) {
            // URI validates IPv6 syntax. Scoped/percent-encoded addresses are ambiguous
            // across parsers and are intentionally unsupported. No name resolution.
            invalidUnless(!host.contains('%'))
            invalidUnless(hostPort == host || (uri.port != -1 && hostPort == "$host:${uri.port}"))
        } else {
            invalidUnless(host.length <= 253)
            val labels = host.split('.')
            invalidUnless(labels.all { it.length in 1..63 && Regex("[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?").matches(it) })
            // Reject numeric aliases, octal/hex/integer IPv4 forms and empty labels.
            if (labels.last().all { it.isDigit() } || host.startsWith("0x", ignoreCase = true)) {
                invalidUnless(labels.size == 4 && labels.all {
                    it.all(Char::isDigit) && (it == "0" || !it.startsWith('0')) && (it.toIntOrNull() ?: -1) in 0..255
                })
            }
            invalidUnless(hostPort == host || (uri.port != -1 && hostPort == "$host:${uri.port}"))
        }
        return candidate
    }

    private fun invalidUnless(condition: Boolean) {
        if (!condition) throw IllegalArgumentException(INVALID_ENDPOINT)
    }
}
