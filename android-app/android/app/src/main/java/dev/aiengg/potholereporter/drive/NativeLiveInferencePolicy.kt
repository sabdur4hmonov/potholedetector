package dev.aiengg.potholereporter.drive

/**
 * Bounds live remote inference without buffering another raw camera burst.
 *
 * One 1440 x 1080 (4:3, the whole sensor) three-frame ARGB burst is roughly 17.8 MiB before
 * request encoding. Two
 * rendezvous consumers materially reduce temporal starvation while keeping the maximum number
 * of service-owned raw inference bursts explicit and small. Durable keyframes still own every
 * burst that cannot be handed directly to one of these consumers.
 */
internal object NativeLiveInferencePolicy {
    const val MAX_CONCURRENT_BURSTS = 2
}
