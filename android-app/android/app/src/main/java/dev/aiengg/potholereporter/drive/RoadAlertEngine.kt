package dev.aiengg.potholereporter.drive

import java.util.Locale
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Offline, AI-free road warnings. Each GPS fix is compared with a local list of known
 * hazards (the driver's own potholes and road shocks today; speed cameras from an official
 * list later). A hazard is announced once per approach when it lies ahead on the current
 * course, at a distance that grows with speed so the driver always has time to react.
 *
 * Nothing here talks to a network. The list comes from the phone's own reports.
 */
enum class RoadHazardKind(val wireValue: String) {
    POTHOLE("pothole"),
    ROAD_SHOCK("road_shock"),
    SPEED_CAMERA("speed_camera"),
    SEATBELT_CAMERA("seatbelt_camera"),
    RED_LIGHT_CAMERA("red_light_camera"),
    LANE_CAMERA("lane_camera"),
    MOBILE_PHONE_CAMERA("phone_camera"),
    SPEED_BUMP("speed_bump");

    val isCamera: Boolean get() = this in CAMERAS

    companion object {
        private val CAMERAS = setOf(
            SPEED_CAMERA, SEATBELT_CAMERA, RED_LIGHT_CAMERA, LANE_CAMERA, MOBILE_PHONE_CAMERA
        )

        fun fromWire(value: String?): RoadHazardKind? = entries.firstOrNull { it.wireValue == value }
    }
}

data class RoadHazard(
    val id: String,
    val kind: RoadHazardKind,
    val lat: Double,
    val lng: Double,
    /** Direction of travel the hazard applies to, degrees from north; null = both ways. */
    val heading: Float? = null,
    /** Posted speed limit in km/h for a camera, when known. */
    val speedLimitKmh: Int? = null
)

data class RoadAlert(
    val hazard: RoadHazard,
    /** Rounded for speech: 50 m steps below 300 m, 100 m steps above. */
    val distanceM: Int,
    val stage: Stage,
    val atElapsedMs: Long
) {
    enum class Stage { EARLY, NEAR }
}

class RoadAlertEngine(hazards: List<RoadHazard>) {
    private val hazards: List<RoadHazard> = hazards
        .filter { it.lat.isFinite() && it.lng.isFinite() && abs(it.lat) <= 90.0 && abs(it.lng) <= 180.0 }
        .distinctBy { it.id }
        .take(MAX_HAZARDS)
    private val byId = this.hazards.associateBy { it.id }
    private val announced = HashMap<String, Announcement>()
    private var lastLat: Double? = null
    private var lastLng: Double? = null
    private var courseHeading: Float? = null

    private class Announcement(val stage: RoadAlert.Stage, val atElapsedMs: Long)

    val hazardCount: Int get() = hazards.size

    /** Returns at most one alert per fix: the nearest hazard needing a new announcement. */
    fun onFix(
        lat: Double,
        lng: Double,
        accuracyM: Float?,
        speedMps: Float?,
        gpsHeading: Float?,
        elapsedMs: Long
    ): RoadAlert? {
        if (!lat.isFinite() || !lng.isFinite()) return null
        val heading = updateCourse(lat, lng, speedMps, gpsHeading)
        rearm(lat, lng, heading, elapsedMs)
        val accuracy = accuracyM?.takeIf { it.isFinite() } ?: return null
        val speed = speedMps?.takeIf { it.isFinite() && it >= 0f } ?: return null
        if (accuracy > MAX_ACCURACY_M || speed < MIN_SPEED_MPS || heading == null) return null

        var best: RoadAlert? = null
        var bestDistance = Double.MAX_VALUE
        for (hazard in hazards) {
            if (abs(hazard.lat - lat) > SEARCH_DEGREES || abs(hazard.lng - lng) > SEARCH_DEGREES) continue
            val distance = distanceM(lat, lng, hazard.lat, hazard.lng)
            if (distance > warnDistanceM(hazard.kind, speed) || distance < MIN_ANNOUNCE_M) continue
            if (!isAhead(lat, lng, heading, hazard)) continue
            val stage = if (distance <= nearDistanceM(hazard.kind, speed)) RoadAlert.Stage.NEAR
                else RoadAlert.Stage.EARLY
            val previous = announced[hazard.id]?.stage
            if (previous == RoadAlert.Stage.NEAR || previous == stage) continue
            // Only potholes and shocks get a second "right ahead" reminder.
            if (previous == RoadAlert.Stage.EARLY && hazard.kind.isCamera) continue
            if (distance < bestDistance) {
                bestDistance = distance
                best = RoadAlert(hazard, roundForSpeech(distance), stage, elapsedMs)
            }
        }
        best?.let { announced[it.hazard.id] = Announcement(it.stage, elapsedMs) }
        return best
    }

    private fun updateCourse(lat: Double, lng: Double, speed: Float?, gpsHeading: Float?): Float? {
        if (gpsHeading != null && gpsHeading.isFinite() && (speed ?: 0f) >= MIN_SPEED_MPS) {
            courseHeading = normalise(gpsHeading)
            lastLat = lat
            lastLng = lng
            return courseHeading
        }
        val previousLat = lastLat
        val previousLng = lastLng
        if (previousLat == null || previousLng == null) {
            lastLat = lat
            lastLng = lng
        } else if (distanceM(previousLat, previousLng, lat, lng) >= COURSE_FROM_MOVEMENT_M) {
            courseHeading = bearing(previousLat, previousLng, lat, lng)
            lastLat = lat
            lastLng = lng
        }
        return courseHeading
    }

    /** A passed, distant or long-ago hazard can be announced again on a later approach. */
    private fun rearm(lat: Double, lng: Double, heading: Float?, elapsedMs: Long) {
        val iterator = announced.entries.iterator()
        while (iterator.hasNext()) {
            val (id, announcement) = iterator.next()
            val hazard = byId[id]
            if (hazard == null || elapsedMs - announcement.atElapsedMs > REARM_AFTER_MS) {
                iterator.remove()
                continue
            }
            val distance = distanceM(lat, lng, hazard.lat, hazard.lng)
            val behind = heading != null &&
                angleBetween(heading, bearing(lat, lng, hazard.lat, hazard.lng)) > BEHIND_DEG
            if (distance > REARM_DISTANCE_M || (behind && distance > PASSED_DISTANCE_M)) iterator.remove()
        }
    }

    private fun isAhead(lat: Double, lng: Double, heading: Float, hazard: RoadHazard): Boolean {
        val toHazard = bearing(lat, lng, hazard.lat, hazard.lng)
        if (angleBetween(heading, toHazard) > AHEAD_CONE_DEG) return false
        val applies = hazard.heading?.takeIf { it.isFinite() } ?: return true
        return angleBetween(heading, normalise(applies)) <= DIRECTION_MATCH_DEG
    }

    companion object {
        const val MAX_HAZARDS = 20_000
        const val MIN_SPEED_MPS = 2.5f
        const val MAX_ACCURACY_M = 35f
        const val AHEAD_CONE_DEG = 30f
        const val DIRECTION_MATCH_DEG = 45f
        const val COURSE_FROM_MOVEMENT_M = 8.0
        const val MIN_ANNOUNCE_M = 25.0
        const val PASSED_DISTANCE_M = 40.0
        const val REARM_DISTANCE_M = 1_500.0
        const val REARM_AFTER_MS = 10 * 60_000L
        const val BEHIND_DEG = 100f
        /** About 0.02 degrees is more than 1.5 km everywhere in Uzbekistan. */
        const val SEARCH_DEGREES = 0.02

        /** Seconds of warning before reaching the hazard, bounded to sensible distances. */
        fun warnDistanceM(kind: RoadHazardKind, speedMps: Float): Double = if (kind.isCamera) {
            (speedMps * 22.0).coerceIn(300.0, 1_000.0)
        } else {
            (speedMps * 14.0).coerceIn(150.0, 600.0)
        }

        fun nearDistanceM(kind: RoadHazardKind, speedMps: Float): Double = if (kind.isCamera) {
            0.0
        } else {
            (speedMps * 5.0).coerceIn(60.0, 150.0)
        }

        fun roundForSpeech(distanceM: Double): Int = if (distanceM < 300.0) {
            ((distanceM / 50.0).roundToInt() * 50).coerceAtLeast(50)
        } else {
            (distanceM / 100.0).roundToInt() * 100
        }

        fun distanceM(lat1: Double, lng1: Double, lat2: Double, lng2: Double): Double {
            val r = 6_371_000.0
            val dLat = Math.toRadians(lat2 - lat1)
            val dLng = Math.toRadians(lng2 - lng1)
            val a = sin(dLat / 2) * sin(dLat / 2) +
                cos(Math.toRadians(lat1)) * cos(Math.toRadians(lat2)) * sin(dLng / 2) * sin(dLng / 2)
            return 2 * r * atan2(sqrt(a), sqrt(1 - a))
        }

        fun bearing(lat1: Double, lng1: Double, lat2: Double, lng2: Double): Float {
            val p1 = Math.toRadians(lat1)
            val p2 = Math.toRadians(lat2)
            val dl = Math.toRadians(lng2 - lng1)
            val y = sin(dl) * cos(p2)
            val x = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dl)
            return normalise(Math.toDegrees(atan2(y, x)).toFloat())
        }

        fun angleBetween(a: Float, b: Float): Float {
            val diff = abs(normalise(a) - normalise(b))
            return if (diff > 180f) 360f - diff else diff
        }

        private fun normalise(value: Float): Float = ((value % 360f) + 360f) % 360f
    }
}

/** Spoken and displayed wording. Uzbek and English match the app; Russian is a voice fallback. */
object RoadAlertPhrases {
    fun text(alert: RoadAlert, language: String): String {
        val d = alert.distanceM
        val near = alert.stage == RoadAlert.Stage.NEAR
        val limit = alert.hazard.speedLimitKmh
        return when (language) {
            "uz" -> when (alert.hazard.kind) {
                RoadHazardKind.POTHOLE -> if (near) "Diqqat, oldinda chuqur." else "$d metrdan keyin chuqur. Sekinlang."
                RoadHazardKind.ROAD_SHOCK -> if (near) "Diqqat, oldinda notekislik." else "$d metrdan keyin yo'l notekisligi. Sekinlang."
                RoadHazardKind.SPEED_BUMP -> if (near) "Diqqat, sun'iy notekislik." else "$d metrdan keyin sun'iy notekislik."
                RoadHazardKind.SPEED_CAMERA -> "$d metrdan keyin tezlik kamerasi" + (limit?.let { ". Chegara $it." } ?: ".")
                RoadHazardKind.SEATBELT_CAMERA -> "$d metrdan keyin xavfsizlik kamari kamerasi. Kamarni taqing."
                RoadHazardKind.RED_LIGHT_CAMERA -> "$d metrdan keyin svetofor kamerasi."
                RoadHazardKind.LANE_CAMERA -> "$d metrdan keyin tasma kamerasi."
                RoadHazardKind.MOBILE_PHONE_CAMERA -> "$d metrdan keyin telefon kamerasi. Telefonni qo'ying."
            }
            "ru" -> when (alert.hazard.kind) {
                RoadHazardKind.POTHOLE -> if (near) "Внимание, впереди яма." else "Через $d метров яма. Снизьте скорость."
                RoadHazardKind.ROAD_SHOCK -> if (near) "Внимание, впереди неровность." else "Через $d метров неровность. Снизьте скорость."
                RoadHazardKind.SPEED_BUMP -> if (near) "Внимание, лежачий полицейский." else "Через $d метров лежачий полицейский."
                RoadHazardKind.SPEED_CAMERA -> "Через $d метров камера скорости" + (limit?.let { ". Ограничение $it." } ?: ".")
                RoadHazardKind.SEATBELT_CAMERA -> "Через $d метров камера ремня. Пристегнитесь."
                RoadHazardKind.RED_LIGHT_CAMERA -> "Через $d метров камера на светофоре."
                RoadHazardKind.LANE_CAMERA -> "Через $d метров камера полосы."
                RoadHazardKind.MOBILE_PHONE_CAMERA -> "Через $d метров камера телефона. Уберите телефон."
            }
            else -> when (alert.hazard.kind) {
                RoadHazardKind.POTHOLE -> if (near) "Pothole right ahead." else "Pothole in $d metres. Slow down."
                RoadHazardKind.ROAD_SHOCK -> if (near) "Rough road right ahead." else "Rough road in $d metres. Slow down."
                RoadHazardKind.SPEED_BUMP -> if (near) "Speed bump right ahead." else "Speed bump in $d metres."
                RoadHazardKind.SPEED_CAMERA -> "Speed camera in $d metres" + (limit?.let { ". Limit $it." } ?: ".")
                RoadHazardKind.SEATBELT_CAMERA -> "Seat belt camera in $d metres. Fasten your belt."
                RoadHazardKind.RED_LIGHT_CAMERA -> "Red light camera in $d metres."
                RoadHazardKind.LANE_CAMERA -> "Lane camera in $d metres."
                RoadHazardKind.MOBILE_PHONE_CAMERA -> "Phone-use camera in $d metres. Put the phone down."
            }
        }
    }

    fun locale(language: String): Locale = when (language) {
        "uz" -> Locale("uz", "UZ")
        "ru" -> Locale("ru", "RU")
        else -> Locale.ENGLISH
    }
}
