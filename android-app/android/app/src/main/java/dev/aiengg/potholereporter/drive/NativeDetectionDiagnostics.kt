package dev.aiengg.potholereporter.drive

import java.util.concurrent.CancellationException

/** Local, payload-free lifecycle for one Drive detection burst. */
enum class DetectionDiagnosticStep {
    PROCESSING_STARTED,
    INPUT_ACCEPTED,
    INPUT_REJECTED,
    DETECTION_ENTERED,
    DETECTION_COMPLETED,
    RESULT_PRODUCED,
    PROCESSING_FAILED,
    PROCESSING_COMPLETED
}

enum class DetectionDiagnosticResult { ACCEPTED, REJECTED, NOT_ANALYZED }

enum class DetectionDiagnosticFailure { INFERENCE, IMAGE_MEMORY, CANCELLED, OTHER }

data class DetectionDiagnosticEvent(
    val step: DetectionDiagnosticStep,
    val frameCount: Int? = null,
    val result: DetectionDiagnosticResult? = null,
    val failure: DetectionDiagnosticFailure? = null
)

internal class DetectionDiagnosticProgress(private val emit: (DetectionDiagnosticEvent) -> Unit) {
    fun detectionEntered() = emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.DETECTION_ENTERED))
    fun detectionCompleted() = emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.DETECTION_COMPLETED))
}

/** Keeps diagnostics outside the result path; the observer cannot replace an outcome or error. */
internal suspend fun runObservedDetection(
    frameCount: Int,
    onDiagnostic: ((DetectionDiagnosticEvent) -> Unit)?,
    process: suspend (DetectionDiagnosticProgress) -> InferenceOutcome
): InferenceOutcome {
    fun emit(event: DetectionDiagnosticEvent) {
        try {
            onDiagnostic?.invoke(event)
        } catch (_: Exception) {
            // Optional local diagnostics must not change detection decisions.
        }
    }

    emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.PROCESSING_STARTED, frameCount = frameCount))
    if (frameCount !in NativeFrameBurstContract.MIN_INFERENCE_FRAMES..NativeRollingBurstWindow.OUTPUT_COUNT) {
        emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.INPUT_REJECTED))
        val outcome = InferenceOutcome(analyzed = false, accepted = false, decision = "reject", assessment = null)
        emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.RESULT_PRODUCED,
            result = DetectionDiagnosticResult.NOT_ANALYZED))
        emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.PROCESSING_COMPLETED))
        return outcome
    }

    emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.INPUT_ACCEPTED))
    try {
        val outcome = process(DetectionDiagnosticProgress(::emit))
        val result = when {
            !outcome.analyzed -> DetectionDiagnosticResult.NOT_ANALYZED
            outcome.accepted -> DetectionDiagnosticResult.ACCEPTED
            else -> DetectionDiagnosticResult.REJECTED
        }
        emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.RESULT_PRODUCED, result = result))
        return outcome
    } catch (error: Throwable) {
        val failure = when (error) {
            is NativeInferenceException -> DetectionDiagnosticFailure.INFERENCE
            is OutOfMemoryError -> DetectionDiagnosticFailure.IMAGE_MEMORY
            is CancellationException -> DetectionDiagnosticFailure.CANCELLED
            else -> DetectionDiagnosticFailure.OTHER
        }
        emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.PROCESSING_FAILED, failure = failure))
        throw error
    } finally {
        emit(DetectionDiagnosticEvent(DetectionDiagnosticStep.PROCESSING_COMPLETED))
    }
}
