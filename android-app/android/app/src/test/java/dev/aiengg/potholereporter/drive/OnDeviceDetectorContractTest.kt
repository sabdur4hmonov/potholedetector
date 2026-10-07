package dev.aiengg.potholereporter.drive

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class OnDeviceDetectorContractTest {
    private val fixture: JSONObject by lazy {
        val stream = requireNotNull(
            javaClass.classLoader?.getResourceAsStream("ondevice-detector-v1.json")
        )
        JSONObject(stream.bufferedReader().use { it.readText() })
    }

    private fun baseline(): OnDeviceModelSpec = requireNotNull(
        OnDeviceModelSpec.parse(fixture.getJSONArray("specs").getJSONObject(0)
            .getJSONObject("card").toString())
    )

    @Test fun sharedModelCardCases() {
        assertEquals(1, fixture.getInt("version"))
        val specs = fixture.getJSONArray("specs")
        assertEquals(33, specs.length())
        for (index in 0 until specs.length()) {
            val case = specs.getJSONObject(index)
            val parsed = OnDeviceModelSpec.parse(case.getJSONObject("card").toString())
            val name = case.getString("name")
            if (case.getBoolean("valid")) assertNotNull(name, parsed) else assertNull(name, parsed)
            case.optJSONObject("expected")?.let { expected ->
                val spec = requireNotNull(parsed)
                assertEquals(name, expected.getInt("input_width"), spec.inputWidth)
                assertEquals(name, expected.getInt("input_height"), spec.inputHeight)
                assertEquals(name, expected.getDouble("threshold"), spec.threshold, 0.0)
                assertEquals(name, expected.getInt("min_positive_frames"), spec.minPositiveFrames)
                assertEquals(name, expected.getBoolean("field_validated"), spec.fieldValidated)
            }
        }
        assertNull(OnDeviceModelSpec.parse("not json"))
    }

    @Test fun sharedBurstDecisionCases() {
        val bursts = fixture.getJSONArray("bursts")
        assertEquals(10, bursts.length())
        for (index in 0 until bursts.length()) {
            val case = bursts.getJSONObject(index)
            val name = case.getString("name")
            val spec = baseline().copy(
                threshold = case.getDouble("threshold"),
                minPositiveFrames = case.getInt("min_positive_frames")
            )
            val raw = case.getJSONArray("scores")
            val scores = (0 until raw.length()).map { at ->
                val value = raw.get(at)
                if (value is String) value.toDouble() else (value as Number).toDouble()
            }
            val verdict = OnDeviceDetectorContract.decideBurst(scores, spec)
            assertEquals(name, case.getString("decision"), verdict.decision.name.lowercase())
            assertEquals(name, case.getInt("positive_frames"), verdict.positiveFrames)
            if (case.isNull("max_score")) assertNull(name, verdict.maxScore)
            else assertEquals(name, case.getDouble("max_score"), verdict.maxScore!!, 0.0)
        }
    }

    @Test fun tensorKeepsEveryPixelInRgbOrder() {
        val pixels = fixture.getJSONObject("pixels")
        val width = pixels.getInt("width")
        val height = pixels.getInt("height")
        val argbJson = pixels.getJSONArray("argb")
        val argb = IntArray(argbJson.length()) { argbJson.getInt(it) }
        val rgbJson = pixels.getJSONArray("rgb")
        val spec = baseline().copy(inputWidth = width, inputHeight = height)
        val out = FloatArray(width * height * 3)
        OnDeviceDetectorContract.fillInputTensor(argb, width, height, spec, out)
        assertEquals(rgbJson.length(), out.size)
        for (index in out.indices) {
            assertEquals(rgbJson.getDouble(index).toFloat(), out[index], 0f)
        }
    }

    @Test fun tensorRejectsAnythingButTheWholeResizedFrame() {
        val spec = baseline().copy(inputWidth = 2, inputHeight = 2)
        assertThrows(IllegalArgumentException::class.java) {
            OnDeviceDetectorContract.fillInputTensor(IntArray(2), 2, 1, spec, FloatArray(6))
        }
        assertThrows(IllegalArgumentException::class.java) {
            OnDeviceDetectorContract.fillInputTensor(IntArray(3), 2, 2, spec, FloatArray(12))
        }
        assertThrows(IllegalArgumentException::class.java) {
            OnDeviceDetectorContract.fillInputTensor(IntArray(4), 2, 2, spec, FloatArray(11))
        }
    }
}
