package dev.aiengg.potholereporter.drive

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Test

class NativeDetectionDiagnosticsTest {
    private val accepted = InferenceOutcome(true, true, "accept", null)
    private val rejected = InferenceOutcome(true, false, "reject", null)

    private suspend fun completedFlow(
        outcome: InferenceOutcome,
        events: MutableList<DetectionDiagnosticEvent>
    ): InferenceOutcome = runObservedDetection(2, events::add) { progress ->
        progress.detectionEntered()
        progress.detectionCompleted()
        outcome
    }

    @Test fun acceptedFlowHasOrderedLifecycleAndPreservesResult() = runBlocking {
        val events = mutableListOf<DetectionDiagnosticEvent>()
        assertSame(accepted, completedFlow(accepted, events))
        assertEquals(listOf(
            DetectionDiagnosticEvent(DetectionDiagnosticStep.PROCESSING_STARTED, frameCount = 2),
            DetectionDiagnosticEvent(DetectionDiagnosticStep.INPUT_ACCEPTED),
            DetectionDiagnosticEvent(DetectionDiagnosticStep.DETECTION_ENTERED),
            DetectionDiagnosticEvent(DetectionDiagnosticStep.DETECTION_COMPLETED),
            DetectionDiagnosticEvent(DetectionDiagnosticStep.RESULT_PRODUCED,
                result = DetectionDiagnosticResult.ACCEPTED),
            DetectionDiagnosticEvent(DetectionDiagnosticStep.PROCESSING_COMPLETED)
        ), events)
    }

    @Test fun rejectedResultAndInvalidFrameCountsAreDistinct() = runBlocking {
        val rejectedEvents = mutableListOf<DetectionDiagnosticEvent>()
        assertSame(rejected, completedFlow(rejected, rejectedEvents))
        assertEquals(DetectionDiagnosticResult.REJECTED, rejectedEvents[4].result)

        for (count in listOf(0, 1, 4)) {
            val events = mutableListOf<DetectionDiagnosticEvent>()
            var processed = false
            val outcome = runObservedDetection(count, events::add) {
                processed = true
                accepted
            }
            assertFalse(processed)
            assertFalse(outcome.analyzed)
            assertEquals("reject", outcome.decision)
            assertEquals(listOf(
                DetectionDiagnosticStep.PROCESSING_STARTED,
                DetectionDiagnosticStep.INPUT_REJECTED,
                DetectionDiagnosticStep.RESULT_PRODUCED,
                DetectionDiagnosticStep.PROCESSING_COMPLETED
            ), events.map { it.step })
            assertEquals(DetectionDiagnosticResult.NOT_ANALYZED, events[2].result)
        }
    }

    @Test fun inferenceFailureHasStableCategoryAndNoPayload() = runBlocking {
        val events = mutableListOf<DetectionDiagnosticEvent>()
        val secretLikePayload = "data:image/jpeg;base64,raw-frame-sentinel"
        val failure = NativeInferenceException(secretLikePayload)
        try {
            runObservedDetection(3, events::add) { progress ->
                progress.detectionEntered()
                throw failure
            }
            throw AssertionError("Expected the original failure")
        } catch (actual: NativeInferenceException) {
            assertSame(failure, actual)
        }
        assertEquals(listOf(
            DetectionDiagnosticStep.PROCESSING_STARTED,
            DetectionDiagnosticStep.INPUT_ACCEPTED,
            DetectionDiagnosticStep.DETECTION_ENTERED,
            DetectionDiagnosticStep.PROCESSING_FAILED,
            DetectionDiagnosticStep.PROCESSING_COMPLETED
        ), events.map { it.step })
        assertEquals(DetectionDiagnosticFailure.INFERENCE, events[3].failure)
        assertFalse(events.toString().contains(secretLikePayload))
        assertFalse(events.any { it.step == DetectionDiagnosticStep.RESULT_PRODUCED })
    }

    @Test fun repeatExecutionAndFailingObserverDoNotChangeSemantics() = runBlocking {
        val first = mutableListOf<DetectionDiagnosticEvent>()
        val second = mutableListOf<DetectionDiagnosticEvent>()
        assertSame(accepted, completedFlow(accepted, first))
        assertSame(accepted, completedFlow(accepted, second))
        assertEquals(first, second)

        val outcome = runObservedDetection(2, { throw IllegalStateException("observer failed") }) {
            progress ->
            progress.detectionEntered()
            progress.detectionCompleted()
            accepted
        }
        assertSame(accepted, outcome)
    }
}
