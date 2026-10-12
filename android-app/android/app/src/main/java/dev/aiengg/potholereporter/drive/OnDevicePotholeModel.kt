package dev.aiengg.potholereporter.drive

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import org.tensorflow.lite.DataType
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel

/**
 * Runs the optional on-device pothole classifier with LiteRT. Nothing is downloaded: the
 * model exists only if a build bundles `assets/models/pothole_detector.json` (the model card
 * written by `ml/train_on_device_detector.py`) and the `.tflite` file it names. Without
 * both, or with a card or tensor shape this version cannot run safely, [load] returns null
 * and Drive behaves exactly as before.
 *
 * Every input is the complete camera frame stretched edge to edge to the model size with
 * [Bitmap.createScaledBitmap]; no part of the frame is ever left out.
 */
internal class OnDevicePotholeModel private constructor(
    val spec: OnDeviceModelSpec,
    private val interpreter: Interpreter
) {
    private val lock = Any()
    private val pixels = IntArray(spec.inputWidth * spec.inputHeight)
    private val tensor = FloatArray(spec.inputWidth * spec.inputHeight * 3)
    private val input: ByteBuffer = ByteBuffer
        .allocateDirect(tensor.size * Float.SIZE_BYTES)
        .order(ByteOrder.nativeOrder())
    private val output = Array(1) { FloatArray(1) }
    @Volatile private var closed = false

    /** Pothole probability for one complete frame, or null when it cannot be scored. */
    fun score(frame: Bitmap): Double? = synchronized(lock) {
        if (closed || frame.isRecycled || frame.width <= 0 || frame.height <= 0) return null
        val resized = Bitmap.createScaledBitmap(frame, spec.inputWidth, spec.inputHeight, true)
        try {
            resized.getPixels(pixels, 0, spec.inputWidth, 0, 0, spec.inputWidth, spec.inputHeight)
        } finally {
            if (resized !== frame) resized.recycle()
        }
        OnDeviceDetectorContract.fillInputTensor(pixels, spec.inputWidth, spec.inputHeight, spec, tensor)
        input.rewind()
        input.asFloatBuffer().put(tensor)
        input.rewind()
        return runCatching {
            interpreter.run(input, output)
            output[0][0].toDouble()
        }.getOrNull()
    }

    /** Scores every frame in order and applies the card's burst rule. */
    fun decide(frames: List<Bitmap>): OnDeviceBurstVerdict {
        val scores = frames.map { score(it) ?: Double.NaN }
        return OnDeviceDetectorContract.decideBurst(scores, spec)
    }

    fun close() {
        synchronized(lock) {
            if (closed) return
            closed = true
            runCatching { interpreter.close() }
        }
    }

    companion object {
        private const val TAG = "OnDevicePotholeModel"
        const val CARD_ASSET = "models/pothole_detector.json"
        private const val MODEL_DIR = "models/"
        private const val MAX_CARD_BYTES = 64 * 1024
        private const val MAX_MODEL_BYTES = 64L * 1024 * 1024
        private const val THREADS = 2

        /** Null unless a runnable model card and its model are bundled. Never throws. */
        fun load(context: Context): OnDevicePotholeModel? = try {
            val assets = context.applicationContext.assets
            val card = runCatching {
                assets.open(CARD_ASSET).use { stream ->
                    val bytes = stream.readNBytesCompat(MAX_CARD_BYTES + 1)
                    if (bytes.size > MAX_CARD_BYTES) null else String(bytes, Charsets.UTF_8)
                }
            }.getOrNull()
            val spec = card?.let(OnDeviceModelSpec::parse)
            if (spec == null) {
                null
            } else {
                val model = map(context, MODEL_DIR + spec.modelFile)
                if (model == null) {
                    null
                } else {
                    val interpreter = Interpreter(model, Interpreter.Options().setNumThreads(THREADS))
                    if (matches(interpreter, spec)) {
                        OnDevicePotholeModel(spec, interpreter)
                    } else {
                        interpreter.close()
                        Log.w(TAG, "Bundled model tensors do not match its card; on-device model disabled")
                        null
                    }
                }
            }
        } catch (error: Throwable) {
            Log.w(TAG, "On-device model unavailable: ${error.javaClass.simpleName}")
            null
        }

        private fun map(context: Context, asset: String): MappedByteBuffer? = runCatching {
            context.applicationContext.assets.openFd(asset).use { fd ->
                if (fd.declaredLength <= 0 || fd.declaredLength > MAX_MODEL_BYTES) return null
                FileInputStream(fd.fileDescriptor).use { stream ->
                    stream.channel.map(FileChannel.MapMode.READ_ONLY, fd.startOffset, fd.declaredLength)
                }
            }
        }.getOrNull()

        /** The model must take exactly one whole frame [1, h, w, 3] and give one probability. */
        private fun matches(interpreter: Interpreter, spec: OnDeviceModelSpec): Boolean {
            if (interpreter.inputTensorCount != 1 || interpreter.outputTensorCount != 1) return false
            val input = interpreter.getInputTensor(0)
            val output = interpreter.getOutputTensor(0)
            return input.dataType() == DataType.FLOAT32 &&
                input.shape().contentEquals(intArrayOf(1, spec.inputHeight, spec.inputWidth, 3)) &&
                output.dataType() == DataType.FLOAT32 &&
                output.numElements() == 1
        }

        private fun java.io.InputStream.readNBytesCompat(limit: Int): ByteArray {
            val out = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(8 * 1024)
            while (out.size() < limit) {
                val read = read(buffer, 0, minOf(buffer.size, limit - out.size()))
                if (read < 0) break
                out.write(buffer, 0, read)
            }
            return out.toByteArray()
        }
    }
}
