package dev.aiengg.potholereporter.drive

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import android.os.SystemClock
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.withContext
import java.nio.FloatBuffer
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** One background worker, no bitmap queue; caller retains ownership until return. No network. */
internal class NativePotholeDetector(private val context: Context) {
    private val executor = Executors.newSingleThreadExecutor { r -> Thread(r, "pothole-onnx") }
    private val dispatcher = executor.asCoroutineDispatcher()
    private val closed = AtomicBoolean(false)
    private val busy = AtomicBoolean(false)
    private var session: OrtSession? = null
    private var config: NativePotholeMath.Config? = null
    @Volatile var status = "not_installed"; private set
    @Volatile var averageMs = 0.0; private set
    private var count = 0L
    data class Result(val yes: Boolean, val version: String, val boxes: List<List<NativePotholeMath.Box>>)

    suspend fun initialize() = withContext(dispatcher) {
        if (assetStatus(context) == "not_installed") return@withContext
        try {
            val json = context.assets.open("ml/pothole_model.json").use { stream ->
                val bytes = boundedRead(stream, 32_768)
                require(bytes.size <= 32_768)
                bytes.toString(Charsets.UTF_8)
            }
            val parsed = NativePotholeMath.config(json)
            val bytes = context.assets.open("ml/pothole_yolox_nano.onnx").use { boundedRead(it, 32 * 1024 * 1024) }
            require(bytes.size in 1..32*1024*1024) { "Model size invalid" }
            NativePotholeMath.verifyModel(parsed, bytes)
            val env = OrtEnvironment.getEnvironment()
            env.setTelemetry(false)
            val loaded = OrtSession.SessionOptions().use { options ->
                options.setIntraOpNumThreads(1); options.setInterOpNumThreads(1)
                env.createSession(bytes, options)
            }
            try {
                val input = loaded.inputInfo.values.single().info as ai.onnxruntime.TensorInfo
                val output = loaded.outputInfo.values.single().info as ai.onnxruntime.TensorInfo
                require(input.shape.contentEquals(longArrayOf(1,3,416,416)))
                require(output.shape.contentEquals(longArrayOf(1,3549,6)))
                require(loaded.inputNames == setOf("images"))
                session = loaded; config = parsed; status = "ready"
            } catch (e: Exception) { loaded.close(); throw e }
        } catch (_: Exception) { status = "invalid_model"; session?.close(); session = null; config = null }
        catch (_: LinkageError) { status = "invalid_model" }
    }

    suspend fun detect(views: List<Bitmap>): Result? {
        if (closed.get() || status != "ready" || !busy.compareAndSet(false, true)) return null
        try {
            return withContext(dispatcher) {
                val active = session ?: return@withContext null
                val c = config ?: return@withContext null
                if (views.size != 3) return@withContext null
                val results = views.map { bitmap ->
                    val start = SystemClock.elapsedRealtimeNanos()
                    val raw = infer(active, bitmap)
                    val ms = (SystemClock.elapsedRealtimeNanos() - start) / 1_000_000.0
                    count++; averageMs += (ms - averageMs) / count
                    NativePotholeMath.decode(raw, bitmap.width, bitmap.height, c)
                }
                Result(NativePotholeMath.consistent(results.map { it.isNotEmpty() }), c.version, results)
            }
        } catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
        catch (_: Exception) { status = "inference_failed"; return null }
        finally { busy.set(false) }
    }

    private fun infer(active: OrtSession, image: Bitmap): FloatArray {
        val geometry = NativePotholeMath.letterbox(image.width, image.height)
        val canvasImage = Bitmap.createBitmap(416,416,Bitmap.Config.ARGB_8888)
        try {
            val canvas = Canvas(canvasImage)
            canvas.drawColor(android.graphics.Color.rgb(114,114,114))
            canvas.drawBitmap(image, null, Rect(0,0,geometry.width,geometry.height), Paint(Paint.FILTER_BITMAP_FLAG))
            val pixels = IntArray(416*416)
            canvasImage.getPixels(pixels,0,416,0,0,416,416)
            val values = FloatArray(pixels.size*3)
            for (i in pixels.indices) {
                values[i] = (pixels[i] and 255).toFloat()
                values[i+pixels.size] = ((pixels[i] shr 8) and 255).toFloat()
                values[i+pixels.size*2] = ((pixels[i] shr 16) and 255).toFloat()
            }
            OnnxTensor.createTensor(OrtEnvironment.getEnvironment(), FloatBuffer.wrap(values), longArrayOf(1,3,416,416)).use { input ->
                active.run(mapOf("images" to input)).use { result ->
                    val tensor = result[0] as OnnxTensor
                    val buffer = requireNotNull(tensor.floatBuffer)
                    require(buffer.remaining() == 3549*6)
                    return FloatArray(buffer.remaining()).also { buffer.get(it) }
                }
            }
        } finally { canvasImage.recycle() }
    }

    fun close() {
        if (!closed.compareAndSet(false,true)) return
        executor.execute { runCatching { session?.close() }; session = null; config = null }
        executor.shutdown() // Resource closure follows the one active operation; no image queue.
    }

    private fun boundedRead(stream: java.io.InputStream, limit: Int): ByteArray {
        val output = java.io.ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (true) {
            val count = stream.read(buffer)
            if (count < 0) break
            require(output.size().toLong() + count <= limit) { "Model asset exceeds budget" }
            output.write(buffer,0,count)
        }
        return output.toByteArray()
    }

    companion object {
        fun assetStatus(context: Context): String = runCatching {
            val names = context.assets.list("ml")?.toSet().orEmpty()
            NativePotholeMath.assetStatus(names)
        }.getOrDefault("not_installed")
    }
}
