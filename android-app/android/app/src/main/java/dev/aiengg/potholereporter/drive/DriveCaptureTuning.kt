package dev.aiengg.potholereporter.drive

/**
 * Pure capture rules for the Drive camera, kept free of Android types so they run in JVM
 * tests. [NativeDriveCameraManager] applies them through CameraX and Camera2 interop.
 *
 * Field of view: phone sensors are 4:3. A 16:9 stream is produced by cutting the top and
 * bottom off the sensor, so every Drive use case asks for 4:3 and keeps the whole sensor
 * image. Electronic stabilisation also crops, so it is turned off; optical stabilisation
 * does not crop and is left to the phone.
 */
internal object DriveCaptureTuning {
    /** 4:3 analysis target in sensor (landscape) orientation; the closest size is used. */
    const val ANALYSIS_WIDTH = 1440
    const val ANALYSIS_HEIGHT = 1080

    /** Below this frame rate auto exposure may use exposures long enough to smear the road. */
    const val MIN_AE_FPS = 20
    /** Higher maximum rates can restrict stream sizes on some phones; 30 is enough. */
    const val MAX_AE_FPS = 30

    /**
     * Picks the auto-exposure frame-rate range that keeps exposures shortest: the highest
     * lower bound, preferring an upper bound of exactly [MAX_AE_FPS]. Null leaves the
     * phone's default, for example when it only offers ranges that may drop below
     * [MIN_AE_FPS] or that need more than [MAX_AE_FPS].
     */
    fun pickAeFpsRange(ranges: List<Pair<Int, Int>>): Pair<Int, Int>? = ranges
        .filter { (low, high) -> low in MIN_AE_FPS..high && high <= MAX_AE_FPS }
        .maxWithOrNull(compareBy<Pair<Int, Int>>({ it.first }, { if (it.second == MAX_AE_FPS) 1 else 0 }))

    /**
     * Continuous-video autofocus moves smoothly and hunts less on a moving road than the
     * photo mode; null leaves the phone's default when it does not offer it.
     */
    fun pickAfMode(available: IntArray?, continuousVideo: Int): Int? =
        if (available != null && continuousVideo in available) continuousVideo else null
}
