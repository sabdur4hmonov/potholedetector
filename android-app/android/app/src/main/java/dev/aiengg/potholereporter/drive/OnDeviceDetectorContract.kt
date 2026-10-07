package dev.aiengg.potholereporter.drive

import org.json.JSONObject

/**
 * Pure contract for a future on-device pothole classifier. It contains no ML runtime: it
 * validates the model card written by `ml/train_on_device_detector.py`, converts an already
 * whole-frame-resized bitmap's pixels into the model's input tensor, and turns per-frame
 * scores into one burst decision. The shared vectors live in
 * `src/test/resources/ondevice-detector-v1.json` and are also executed by the Python tool.
 *
 * Every model input is the complete camera frame resized edge to edge; the card must say so
 * (`resize = whole_frame_stretch`, `crop = false`) or it is rejected.
 */
internal data class OnDeviceModelSpec(
    val modelFile: String,
    val inputWidth: Int,
    val inputHeight: Int,
    val threshold: Double,
    val minPositiveFrames: Int,
    /** False until a human has validated the model on real Uzbekistan roads. */
    val fieldValidated: Boolean
) {
    companion object {
        const val SCHEMA_VERSION = "pothole-ondevice-model-v1"
        const val TASK = "binary_full_frame_pothole"
        const val RESIZE = "whole_frame_stretch"
        const val MIN_INPUT_DIMENSION = 32
        const val MAX_INPUT_DIMENSION = 640
        const val MAX_MIN_POSITIVE_FRAMES = 8
        private val MODEL_FILE = Regex("^[A-Za-z0-9_.-]{1,64}\\.tflite$")

        /** Returns null for any card this app version cannot run safely. */
        fun parse(text: String): OnDeviceModelSpec? = try {
            parse(JSONObject(text))
        } catch (_: Exception) {
            null
        }

        private fun parse(json: JSONObject): OnDeviceModelSpec? {
            if (json.optString("schema_version") != SCHEMA_VERSION) return null
            if (json.optString("task") != TASK) return null
            val labels = json.optJSONArray("labels") ?: return null
            if (labels.length() != 2 || labels.optString(0) != "not_pothole" ||
                labels.optString(1) != "pothole"
            ) return null
            val modelFile = json.optString("model_file")
            if (!MODEL_FILE.matches(modelFile) || modelFile.contains("..")) return null

            val input = json.optJSONObject("input") ?: return null
            val width = input.opt("width") as? Int ?: return null
            val height = input.opt("height") as? Int ?: return null
            if (width !in MIN_INPUT_DIMENSION..MAX_INPUT_DIMENSION ||
                height !in MIN_INPUT_DIMENSION..MAX_INPUT_DIMENSION
            ) return null
            if (input.opt("channels") != 3 || input.optString("color_order") != "RGB" ||
                input.optString("layout") != "NHWC" || input.optString("dtype") != "float32"
            ) return null
            val range = input.optJSONArray("value_range") ?: return null
            if (range.length() != 2 || (range.opt(0) as? Number)?.toDouble() != 0.0 ||
                (range.opt(1) as? Number)?.toDouble() != 255.0
            ) {
                return null
            }
            if (input.optString("resize") != RESIZE || input.opt("crop") != false) return null

            val output = json.optJSONObject("output") ?: return null
            if (output.optString("kind") != "sigmoid_pothole_probability") return null

            val decision = json.optJSONObject("decision") ?: return null
            val threshold = (decision.opt("threshold") as? Number)?.toDouble() ?: return null
            if (!threshold.isFinite() || threshold <= 0.0 || threshold >= 1.0) return null
            val minPositive = decision.opt("min_positive_frames") as? Int ?: return null
            if (minPositive !in 1..MAX_MIN_POSITIVE_FRAMES) return null

            val validation = json.optJSONObject("validation") ?: return null
            val fieldValidated = validation.opt("validated_on_real_roads") as? Boolean
                ?: return null
            // A pipeline smoke-test model trained on synthetic or tiny data is never runnable.
            if (validation.opt("smoke_test_only") != false) return null

            return OnDeviceModelSpec(modelFile, width, height, threshold, minPositive, fieldValidated)
        }
    }
}

internal enum class OnDeviceBurstDecision { ACCEPT, REJECT, INSUFFICIENT_FRAMES, INVALID_SCORE }

internal data class OnDeviceBurstVerdict(
    val decision: OnDeviceBurstDecision,
    val positiveFrames: Int,
    val maxScore: Double?
)

internal object OnDeviceDetectorContract {
    /**
     * Fills [out] (NHWC, RGB, 0..255 floats) from ARGB pixels of a bitmap that already holds
     * the complete frame resized to the model input. The pixel count must match the input
     * exactly: a partial frame or a region of interest can never be fed to the model.
     */
    fun fillInputTensor(
        argbPixels: IntArray,
        width: Int,
        height: Int,
        spec: OnDeviceModelSpec,
        out: FloatArray
    ) {
        require(width == spec.inputWidth && height == spec.inputHeight) {
            "Input must be the whole frame resized to ${spec.inputWidth}x${spec.inputHeight}"
        }
        require(argbPixels.size == width * height) { "Pixel count does not cover the whole frame" }
        require(out.size == width * height * 3) { "Tensor size does not match the model input" }
        var at = 0
        for (pixel in argbPixels) {
            out[at++] = ((pixel shr 16) and 0xFF).toFloat()
            out[at++] = ((pixel shr 8) and 0xFF).toFloat()
            out[at++] = (pixel and 0xFF).toFloat()
        }
    }

    /**
     * One score per complete chronological frame. Fails closed: any non-probability score
     * produces no report, and a burst shorter than the required consistency never accepts.
     */
    fun decideBurst(scores: List<Double>, spec: OnDeviceModelSpec): OnDeviceBurstVerdict {
        if (scores.any { !it.isFinite() || it < 0.0 || it > 1.0 }) {
            return OnDeviceBurstVerdict(OnDeviceBurstDecision.INVALID_SCORE, 0, null)
        }
        val maxScore = scores.maxOrNull()
        val positives = scores.count { it >= spec.threshold }
        val decision = when {
            scores.size < spec.minPositiveFrames -> OnDeviceBurstDecision.INSUFFICIENT_FRAMES
            positives >= spec.minPositiveFrames -> OnDeviceBurstDecision.ACCEPT
            else -> OnDeviceBurstDecision.REJECT
        }
        return OnDeviceBurstVerdict(decision, positives, maxScore)
    }
}
