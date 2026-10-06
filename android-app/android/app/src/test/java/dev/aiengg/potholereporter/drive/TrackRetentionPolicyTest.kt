package dev.aiengg.potholereporter.drive

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TrackRetentionPolicyTest {
    private val now = 1_800_000_000L
    private val day = 86_400L

    @Test
    fun `retention is exactly thirty days`() {
        assertEquals(30L, TrackRetentionPolicy.RETENTION_DAYS)
        assertEquals(now - 30 * day, TrackRetentionPolicy.cutoffSeconds(now))
    }

    @Test
    fun `a drive that ended within thirty days is kept`() {
        assertFalse(TrackRetentionPolicy.isExpired(now - 29 * day, now - 29 * day - 600, now))
        assertFalse(TrackRetentionPolicy.isExpired(now - 30 * day, now - 31 * day, now))
    }

    @Test
    fun `a drive that ended more than thirty days ago expires`() {
        assertTrue(TrackRetentionPolicy.isExpired(now - 30 * day - 1, now - 31 * day, now))
        assertTrue(TrackRetentionPolicy.isExpired(now - 90 * day, now - 91 * day, now))
    }

    @Test
    fun `a drive without an end time ages from its start`() {
        assertFalse(TrackRetentionPolicy.isExpired(null, now - 10 * day, now))
        assertTrue(TrackRetentionPolicy.isExpired(null, now - 40 * day, now))
    }
}
