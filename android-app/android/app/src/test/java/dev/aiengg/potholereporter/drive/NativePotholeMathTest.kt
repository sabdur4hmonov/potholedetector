package dev.aiengg.potholereporter.drive

import org.junit.Assert.*
import org.junit.Test

class NativePotholeMathTest {
    private val config = NativePotholeMath.Config("yolox-test-v1", .6, .45, "0".repeat(64))
    @Test fun wholeFrameCornersStayInsideCanvasWithAspectKept() {
        for ((w,h) in listOf(1920 to 1080, 1080 to 1920, 416 to 416, 1 to 9000)) {
            val b = NativePotholeMath.letterbox(w,h)
            assertTrue(b.width in 1..416 && b.height in 1..416)
            assertTrue(w*b.scale <= 416.00001 && h*b.scale <= 416.00001)
            assertTrue(kotlin.math.abs(b.width-w*b.scale) <= 1 && kotlin.math.abs(b.height-h*b.scale) <= 1)
        }
    }
    @Test fun syntheticRawTensorDecodesGridStrideAndScore() {
        val raw = FloatArray(3549*6)
        val at = (10*52+20)*6
        raw[at] = .5f; raw[at+1] = .5f; raw[at+4] = .9f; raw[at+5] = .9f
        val box = NativePotholeMath.decode(raw,416,416,config).single()
        assertEquals(160.0,box.left,1e-6); assertEquals(80.0,box.top,1e-6)
        assertEquals(168.0,box.right,1e-6); assertEquals(88.0,box.bottom,1e-6)
        assertTrue(NativePotholeMath.decode(raw,416,416,config.copy(threshold=.85)).isEmpty())
    }
    @Test fun nmsSuppressesOverlapButPreservesSeparatePotholes() {
        fun b(x: Double, s: Double)=NativePotholeMath.Box(x,0.0,x+20,20.0,s)
        assertEquals(2, NativePotholeMath.nms(listOf(b(0.0,.9),b(1.0,.8),b(40.0,.7)),.45).size)
    }
    @Test fun invalidTensorIsRefusedAndNonfiniteRowsIgnored() {
        assertThrows(IllegalArgumentException::class.java) { NativePotholeMath.decode(FloatArray(1),416,416,config) }
        val raw=FloatArray(3549*6); raw[4]=Float.NaN
        assertTrue(NativePotholeMath.decode(raw,416,416,config).isEmpty())
    }
    @Test fun manifestThresholdIsAuthoritativeAndInvalidManifestRefused() {
        val json="""{"version":"yolox-test-v1","input_size":416,"opset":17,"output_format":"yolox_raw_bgr_0_255","score_threshold":0.73,"nms_iou":0.4,"sha256":"${"0".repeat(64)}","dataset_sha256":"${"1".repeat(64)}","yolox_commit":"6ddff4824372906469a7fae2dc3206c7aa4bbaee"}"""
        assertEquals(.73,NativePotholeMath.config(json).threshold,1e-9)
        assertThrows(IllegalArgumentException::class.java) { NativePotholeMath.config(json.replace("0.73","1.2")) }
    }
    @Test fun twoOfExactlyThreeIndependentViewsRequired() {
        assertTrue(NativePotholeMath.consistent(listOf(true,false,true)))
        assertFalse(NativePotholeMath.consistent(listOf(false,false,true)))
        assertFalse(NativePotholeMath.consistent(listOf(true,true)))
    }
    @Test fun absentAndPartialAssetsLeaveDetectorUnavailable() {
        assertEquals("not_installed",NativePotholeMath.assetStatus(emptySet()))
        assertEquals("not_installed",NativePotholeMath.assetStatus(setOf("pothole_model.json")))
    }
    @Test fun shaMismatchFailsClosed() {
        assertThrows(IllegalArgumentException::class.java) { NativePotholeMath.verifyModel(config,byteArrayOf(1,2,3)) }
        val hash=java.security.MessageDigest.getInstance("SHA-256").digest(byteArrayOf(1,2,3)).joinToString("") { "%02x".format(it) }
        NativePotholeMath.verifyModel(config.copy(sha256=hash),byteArrayOf(1,2,3))
    }
    @Test fun fusionTableAndInclusiveTimeDistanceBoundaries() {
        assertEquals("drive_camera_bump",NativePotholeFusion.source(true,true))
        assertEquals("drive_camera",NativePotholeFusion.source(true,false))
        assertEquals("drive_sensor",NativePotholeFusion.source(false,true))
        assertEquals("unconfirmed",NativePotholeFusion.kind("drive_camera"))
        assertEquals("confirmed",NativePotholeFusion.kind("drive_camera_bump"))
        assertTrue(NativePotholeFusion.matches(1000,1150,40.0))
        assertTrue(NativePotholeFusion.matches(1000,7000,40.0))
        assertFalse(NativePotholeFusion.matches(1000,1149,0.0))
        assertFalse(NativePotholeFusion.matches(1000,7001,0.0))
        assertFalse(NativePotholeFusion.matches(1000,2000,40.01))
        assertFalse(NativePotholeFusion.matches(1000,2000,Double.NaN))
    }
    @Test fun oneEventMergesOnlyWithinFifteenMetersInSameDrive() {
        assertTrue(NativePotholeFusion.merge(true,15.0))
        assertFalse(NativePotholeFusion.merge(true,15.01))
        assertFalse(NativePotholeFusion.merge(false,1.0))
    }
}
