package dev.aiengg.potholereporter.drive

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DriveCaptureTuningTest {
    @Test fun analysisTargetIsFourByThree() {
        assertEquals(4 * DriveCaptureTuning.ANALYSIS_HEIGHT, 3 * DriveCaptureTuning.ANALYSIS_WIDTH)
    }

    @Test fun fixedThirtyIsPreferredWhenOffered() {
        val typical = listOf(15 to 15, 15 to 30, 24 to 24, 24 to 30, 30 to 30, 60 to 60)
        assertEquals(30 to 30, DriveCaptureTuning.pickAeFpsRange(typical))
    }

    @Test fun otherwiseTheHighestFloorWins() {
        assertEquals(24 to 30, DriveCaptureTuning.pickAeFpsRange(listOf(7 to 30, 15 to 30, 24 to 30)))
        assertEquals(24 to 30, DriveCaptureTuning.pickAeFpsRange(listOf(24 to 24, 24 to 30)))
        assertEquals(20 to 24, DriveCaptureTuning.pickAeFpsRange(listOf(15 to 30, 20 to 24)))
    }

    @Test fun rangesThatMayDropTooLowOrNeedMoreThanThirtyAreLeftAlone() {
        assertNull(DriveCaptureTuning.pickAeFpsRange(listOf(7 to 30, 15 to 30, 15 to 15)))
        assertNull(DriveCaptureTuning.pickAeFpsRange(listOf(60 to 60, 30 to 60)))
        assertNull(DriveCaptureTuning.pickAeFpsRange(emptyList()))
        assertNull(DriveCaptureTuning.pickAeFpsRange(listOf(30 to 24)))
    }

    @Test fun continuousVideoFocusOnlyWhenAvailable() {
        val continuousVideo = 3
        assertEquals(3, DriveCaptureTuning.pickAfMode(intArrayOf(0, 1, 3, 4), continuousVideo))
        assertNull(DriveCaptureTuning.pickAfMode(intArrayOf(0, 1, 4), continuousVideo))
        assertNull(DriveCaptureTuning.pickAfMode(null, continuousVideo))
    }
}
