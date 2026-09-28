package dev.aiengg.potholereporter.drive

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeRtspTransportPolicyTest {
    private fun rejected(value: String?, message: String) {
        var clientCreations = 0
        val error = runCatching {
            NativeRtspTransportPolicy.withProductionEndpoint(value) { clientCreations++; it }
        }.exceptionOrNull()
        assertTrue(error is IllegalArgumentException)
        assertEquals(message, error?.message)
        assertNull(error?.cause)
        assertEquals(0, clientCreations)
    }

    @Test fun `plaintext and saved plaintext endpoints never create a client`() {
        for (value in listOf("rtsp://camera.example/live", "RTSP://camera.example/live",
            "  rtsp://camera.example:554/live  ")) {
            rejected(value, NativeRtspTransportPolicy.PLAINTEXT_REJECTED)
            assertTrue(NativeFrameSourceConfig.create("dashcam", value).isFailure)
        }
    }

    @Test fun `valid secure endpoints fail closed because stack lacks verified TLS`() {
        for (value in listOf("rtsps://camera.example/live", "RTSPS://Camera.Example:322/live?channel=1",
            "rtsps://192.168.1.1:65535/live", "rtsps://[2001:db8::7]:322/live",
            "rtsps://user:synthetic-secret@camera.example/live")) {
            rejected(value, NativeRtspTransportPolicy.SECURE_UNAVAILABLE)
        }
    }

    @Test fun `missing malformed and unsupported schemes are rejected`() {
        for (value in listOf(null, "", " ", "/live", "rtsps:live", "rtsps:///live",
            "https://camera.example/live", "rtspt://camera.example/live", "ftp://camera.example/live",
            "rtsps://camera.example/live stream", "rtsps://camera.example\\live",
            "rtsps://camera.example/%zz", "rtsps://camera.example/live#fragment")) {
            rejected(value, NativeRtspTransportPolicy.INVALID_ENDPOINT)
        }
    }

    @Test fun `ports must be unambiguous valid decimal ports`() {
        for (port in listOf("0", "65536", "-1", "", "abc", "0554", "999999999999999999")) {
            rejected("rtsps://camera.example:$port/live", NativeRtspTransportPolicy.INVALID_ENDPOINT)
        }
    }

    @Test fun `ambiguous hosts are rejected without DNS resolution`() {
        for (host in listOf("", "camera..example", "camera.example.", "_camera.example", "-camera.example",
            "127.1", "2130706433", "0177.0.0.1", "0x7f000001", "256.0.0.1",
            "[fe80::1%25wlan0]", "[invalid]", "camera.example:322:554")) {
            rejected("rtsps://$host/live", NativeRtspTransportPolicy.INVALID_ENDPOINT)
        }
    }

    @Test fun `unsafe userinfo is rejected with fixed credential free errors`() {
        for (authority in listOf("user:synthetic-secret@other@camera.example", ":synthetic-secret@camera.example",
            "user:synthetic-secret%0a@camera.example", "user:synthetic-secret%255c@camera.example")) {
            rejected("rtsps://$authority/live", NativeRtspTransportPolicy.INVALID_ENDPOINT)
        }
    }

    @Test fun `parser exception and stack trace never contain credentials`() {
        val error = runCatching {
            NativeRtspTransportPolicy.requireProductionEndpoint("rtsps://user:synthetic-secret@camera.example/%zz")
        }.exceptionOrNull()!!
        assertEquals(NativeRtspTransportPolicy.INVALID_ENDPOINT, error.message)
        assertTrue(!error.stackTraceToString().contains("synthetic-secret"))
        assertTrue(!error.stackTraceToString().contains("rtsps://user"))
    }

    @Test fun `repeated secure failures cannot retry plaintext or create resources`() {
        repeat(3) {
            rejected("rtsps://camera.example/live", NativeRtspTransportPolicy.SECURE_UNAVAILABLE)
            rejected("rtsp://camera.example/live", NativeRtspTransportPolicy.PLAINTEXT_REJECTED)
        }
    }

    @Test fun `bridge options cannot authorize any dashcam connection`() {
        assertTrue(NativeFrameSourceConfig.create("dashcam", "rtsps://camera.example/live").isFailure)
        assertTrue(NativeFrameSourceConfig.create("dashcam", null).isFailure)
        assertTrue(NativeFrameSourceConfig.create("unknown", "rtsps://camera.example/live").isFailure)
        assertNull(NativeFrameSourceConfig.create("phone_camera", "rtsp://camera.example/live").getOrThrow().rtspUrl)
    }
}
