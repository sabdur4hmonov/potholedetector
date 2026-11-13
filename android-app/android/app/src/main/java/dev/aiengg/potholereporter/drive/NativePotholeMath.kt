package dev.aiengg.potholereporter.drive

import org.json.JSONObject
import kotlin.math.*

/** Contract shared with ml/evaluate_export.py: raw YOLOX, BGR 0..255, top-left letterbox. */
internal object NativePotholeMath {
    const val SIZE = 416
    const val ROWS = 3549
    data class Letterbox(val width: Int, val height: Int, val scale: Double)
    data class Box(val left: Double, val top: Double, val right: Double, val bottom: Double, val score: Double)
    data class Config(val version: String, val threshold: Double, val nms: Double, val sha256: String)

    fun letterbox(width: Int, height: Int): Letterbox {
        require(width > 0 && height > 0)
        val scale = min(SIZE.toDouble() / width, SIZE.toDouble() / height)
        return Letterbox(max(1, (width * scale).toInt()), max(1, (height * scale).toInt()), scale)
    }

    fun config(json: String): Config {
        require(json.length <= 32_768)
        val o = JSONObject(json)
        require(o.getInt("input_size") == SIZE && o.getInt("opset") == 17)
        require(o.getString("output_format") == "yolox_raw_bgr_0_255")
        val version = o.getString("version")
        val sha = o.getString("sha256").lowercase()
        val threshold = o.getDouble("score_threshold")
        val nms = o.getDouble("nms_iou")
        require(Regex("[A-Za-z0-9._-]{1,80}").matches(version))
        require(Regex("[0-9a-f]{64}").matches(sha))
        require(threshold.isFinite() && threshold > 0 && threshold < 1)
        require(nms.isFinite() && nms > 0 && nms < 1)
        require(Regex("[0-9a-f]{64}").matches(o.getString("dataset_sha256")))
        require(o.getString("yolox_commit") == "6ddff4824372906469a7fae2dc3206c7aa4bbaee")
        return Config(version, threshold, nms, sha)
    }

    fun assetStatus(names: Set<String>) = if (setOf("pothole_yolox_nano.onnx", "pothole_model.json").all { it in names }) "installed_unverified" else "not_installed"
    fun verifyModel(config: Config, bytes: ByteArray) {
        val actual = java.security.MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        require(config.sha256 == actual) { "Model SHA-256 mismatch" }
    }
    fun consistent(views: List<Boolean>) = views.size == 3 && views.count { it } >= 2

    fun decode(raw: FloatArray, width: Int, height: Int, config: Config): List<Box> {
        require(raw.size == ROWS * 6)
        val scale = letterbox(width, height).scale
        val candidates = ArrayList<Box>()
        var row = 0
        for (stride in intArrayOf(8, 16, 32)) {
            for (y in 0 until SIZE / stride) for (x in 0 until SIZE / stride) {
                val at = row++ * 6
                if ((0..5).any { !raw[at + it].isFinite() }) continue
                val score = raw[at+4].toDouble() * raw[at+5]
                if (raw[at+4] !in 0f..1f || raw[at+5] !in 0f..1f || score < config.threshold) continue
                val cx = (raw[at] + x) * stride / scale
                val cy = (raw[at+1] + y) * stride / scale
                val bw = exp(raw[at+2].toDouble().coerceIn(-20.0, 20.0)) * stride / scale
                val bh = exp(raw[at+3].toDouble().coerceIn(-20.0, 20.0)) * stride / scale
                val b = Box((cx-bw/2).coerceIn(0.0,width.toDouble()), (cy-bh/2).coerceIn(0.0,height.toDouble()),
                    (cx+bw/2).coerceIn(0.0,width.toDouble()), (cy+bh/2).coerceIn(0.0,height.toDouble()), score)
                if (b.right > b.left && b.bottom > b.top) candidates.add(b)
            }
        }
        return nms(candidates, config.nms)
    }

    fun iou(a: Box, b: Box): Double {
        val area = max(0.0, min(a.right,b.right)-max(a.left,b.left)) * max(0.0,min(a.bottom,b.bottom)-max(a.top,b.top))
        val union = (a.right-a.left)*(a.bottom-a.top)+(b.right-b.left)*(b.bottom-b.top)-area
        return if (union > 0) area/union else 0.0
    }
    fun nms(boxes: List<Box>, threshold: Double): List<Box> {
        val keep = ArrayList<Box>()
        for (box in boxes.sortedByDescending { it.score }) {
            if (keep.all { iou(it,box) <= threshold }) keep.add(box)
            if (keep.size >= 100) break
        }
        return keep
    }
}

internal object NativePotholeFusion {
    fun matches(cameraAt: Long, bumpAt: Long, distance: Double) =
        bumpAt - cameraAt in 150..6_000 && distance.isFinite() && distance in 0.0..40.0
    fun merge(sameDrive: Boolean, distance: Double) = sameDrive && distance.isFinite() && distance in 0.0..15.0
    fun source(camera: Boolean, bump: Boolean) = when {
        camera && bump -> "drive_camera_bump"
        camera -> "drive_camera"
        else -> "drive_sensor"
    }
    fun kind(source: String) = if (source == "drive_camera_bump") "confirmed" else "unconfirmed"
    fun offlineSource(source: String) = source in setOf("drive_sensor", "drive_camera", "drive_camera_bump")
}
