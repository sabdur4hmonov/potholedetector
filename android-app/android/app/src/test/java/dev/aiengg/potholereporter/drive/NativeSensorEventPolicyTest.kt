package dev.aiengg.potholereporter.drive

import org.junit.Assert.*
import org.junit.Test

class NativeSensorEventPolicyTest {
    @Test fun exactInclusiveWindowAndNewestEligibleFrame() {
        assertNull(NativeSensorEventPolicy.selectFrame(10000, emptyList()))
        assertEquals(0, NativeSensorEventPolicy.selectFrame(10000, listOf(6000L)))
        assertEquals(0, NativeSensorEventPolicy.selectFrame(10000, listOf(9850L)))
        assertNull(NativeSensorEventPolicy.selectFrame(10000, listOf(5999L, 9851L, 10001L)))
        assertEquals(2, NativeSensorEventPolicy.selectFrame(10000, listOf(7000L, 6000L, 9800L, 9999L, 11000L)))
    }
    @Test fun mergeOnlySensorReportsInSameDriveWithin15Meters() {
        assertTrue(NativeSensorEventPolicy.canMerge(true, true, 15.0))
        assertTrue(NativeSensorEventPolicy.canMerge(true, true, 0.0))
        assertFalse(NativeSensorEventPolicy.canMerge(true, true, 15.01))
        assertFalse(NativeSensorEventPolicy.canMerge(false, true, 1.0))
        assertFalse(NativeSensorEventPolicy.canMerge(true, false, 1.0))
        assertFalse(NativeSensorEventPolicy.canMerge(true, true, Double.NaN))
    }
}
