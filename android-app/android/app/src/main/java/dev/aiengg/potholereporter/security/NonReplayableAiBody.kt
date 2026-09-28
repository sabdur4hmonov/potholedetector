package dev.aiengg.potholereporter.security

import java.util.concurrent.atomic.AtomicBoolean
import okhttp3.RequestBody
import okio.BufferedSink

/** Prevent implicit 503/421 follow-ups as well as connection recovery from resending paid input. */
internal class NonReplayableAiBody(private val delegate: RequestBody) : RequestBody() {
    private val written = AtomicBoolean(false)
    override fun contentType() = delegate.contentType()
    override fun contentLength() = delegate.contentLength()
    override fun isOneShot() = true
    override fun writeTo(sink: BufferedSink) {
        if (!written.compareAndSet(false, true)) throw AiUsageLimitException()
        delegate.writeTo(sink)
    }
}
