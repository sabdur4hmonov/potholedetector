package dev.aiengg.potholereporter.drive

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.nio.FloatBuffer

class NativePotholeRuntimeTest {
    @Test fun installedModelRunsThreeFixtureFramesOnRealCpuRuntime() {
        val model=File("src/main/assets/ml/pothole_yolox_nano.onnx")
        val manifest=File("src/main/assets/ml/pothole_model.json")
        assumeTrue("Model not trained/installed: real ONNX fixture/latency test SKIPPED",model.isFile && manifest.isFile)
        val config=NativePotholeMath.config(manifest.readText())
        NativePotholeMath.verifyModel(config,model.readBytes())
        val env=OrtEnvironment.getEnvironment(); env.setTelemetry(false)
        OrtSession.SessionOptions().use { options ->
            options.setIntraOpNumThreads(1)
            env.createSession(model.absolutePath,options).use { session ->
                for ((width, height) in listOf(64 to 32, 32 to 64, 48 to 48)) {
                    val fixture = IntArray(width * height) { i -> ((i % width * 4) shl 16) or ((i / width * 4) shl 8) or 96 }
                    val b=NativePotholeMath.letterbox(width,height)
                    val input=FloatArray(416*416*3) {114f}
                    for (y in 0 until b.height) for (x in 0 until b.width) {
                        val p=fixture[(y*height/b.height)*width+x*width/b.width]
                        val at=y*416+x
                        input[at]=(p and 255).toFloat(); input[at+416*416]=((p shr 8) and 255).toFloat()
                        input[at+416*416*2]=((p shr 16) and 255).toFloat()
                    }
                    val start=System.nanoTime()
                    OnnxTensor.createTensor(env,FloatBuffer.wrap(input),longArrayOf(1,3,416,416)).use { tensor ->
                        session.run(mapOf("images" to tensor)).use { result ->
                            assertArrayEquals(longArrayOf(1,3549,6),(result[0].info as ai.onnxruntime.TensorInfo).shape)
                        }
                    }
                    val ms=(System.nanoTime()-start)/1_000_000.0
                    println("Real ONNX ${width}x$height fixture latency: $ms ms (host CPU, not phone)")
                    assertTrue(ms.isFinite() && ms > 0)
                }
            }
        }
    }
}
