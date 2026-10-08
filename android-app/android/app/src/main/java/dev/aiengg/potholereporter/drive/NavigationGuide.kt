package dev.aiengg.potholereporter.drive

import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Offline turn-by-turn guidance for a route the community server computed with OSRM.
 * Every GPS fix is snapped onto the route line; the next real manoeuvre is announced
 * early, close and "now" at distances that grow with speed. Leaving the route for three
 * accurate fixes raises one off-route event so the app can ask for a new route.
 * Pure Kotlin: no Android, no network.
 */
data class NavPoint(val lat: Double, val lng: Double)

data class NavManeuver(
    val lat: Double,
    val lng: Double,
    /** OSRM maneuver type: turn, fork, roundabout, arrive, ... */
    val type: String,
    /** OSRM modifier: left, right, slight left, sharp right, uturn, straight, ... */
    val modifier: String? = null,
    val exit: Int? = null,
    val name: String = ""
)

data class NavEvent(
    val kind: Kind,
    val maneuver: NavManeuver?,
    val distanceM: Int,
    val stage: Stage? = null
) {
    enum class Kind { START, INSTRUCTION, OFF_ROUTE, ARRIVED }
    enum class Stage { FAR, NEAR, NOW }
}

data class NavProgress(
    val nextManeuver: NavManeuver?,
    val distanceToNextM: Int?,
    val remainingM: Int,
    val offRoute: Boolean,
    val arrived: Boolean
)

class NavigationGuide(route: List<NavPoint>, maneuvers: List<NavManeuver>) {
    private val points: List<NavPoint> = route
        .filter { it.lat.isFinite() && it.lng.isFinite() && abs(it.lat) <= 90 && abs(it.lng) <= 180 }
        .take(MAX_POINTS)
    private val along = DoubleArray(points.size)
    private val steps: List<Pair<NavManeuver, Double>>
    private val announced = HashMap<Int, NavEvent.Stage>()
    private var progressM = 0.0
    private var lastSegment = 0
    private var offRouteFixes = 0
    private var offRoute = false
    private var started = false
    private var arrived = false

    val totalM: Double get() = if (along.isEmpty()) 0.0 else along.last()

    init {
        for (i in 1 until points.size) {
            along[i] = along[i - 1] + RoadAlertEngine.distanceM(
                points[i - 1].lat, points[i - 1].lng, points[i].lat, points[i].lng
            )
        }
        var searchFrom = 0
        val placed = ArrayList<Pair<NavManeuver, Double>>()
        for (m in maneuvers.take(MAX_MANEUVERS)) {
            if (!m.lat.isFinite() || !m.lng.isFinite() || !isSpoken(m) || points.size < 2) continue
            val snap = project(m.lat, m.lng, searchFrom, points.size - 2) ?: continue
            searchFrom = snap.segment
            placed += m to snap.alongM
        }
        // Always finish with an arrival at the very end of the line.
        if (placed.none { it.first.type == "arrive" } && points.size >= 2) {
            placed += NavManeuver(points.last().lat, points.last().lng, "arrive") to totalM
        }
        steps = placed
    }

    fun progress(): NavProgress {
        val next = nextIndex()
        return NavProgress(
            nextManeuver = next?.let { steps[it].first },
            distanceToNextM = next?.let { max(0.0, steps[it].second - progressM).roundToInt() },
            remainingM = max(0.0, totalM - progressM).roundToInt(),
            offRoute = offRoute,
            arrived = arrived
        )
    }

    /** At most one event per fix. */
    fun onFix(lat: Double, lng: Double, accuracyM: Float?, speedMps: Float?): NavEvent? {
        if (arrived || points.size < 2 || !lat.isFinite() || !lng.isFinite()) return null
        val accuracy = accuracyM?.takeIf { it.isFinite() } ?: return null
        if (accuracy > MAX_ACCURACY_M) return null
        val speed = speedMps?.takeIf { it.isFinite() && it >= 0f } ?: 0f

        val window = project(lat, lng, max(0, lastSegment - 3), min(points.size - 2, lastSegment + 80))
        val snap = window?.takeIf { it.crossTrackM <= OFF_ROUTE_M }
            ?: project(lat, lng, 0, points.size - 2)
            ?: return null
        if (snap.crossTrackM > OFF_ROUTE_M) {
            offRouteFixes++
            if (offRouteFixes >= OFF_ROUTE_FIXES && !offRoute) {
                offRoute = true
                return NavEvent(NavEvent.Kind.OFF_ROUTE, null, snap.crossTrackM.roundToInt())
            }
            return null
        }
        offRouteFixes = 0
        offRoute = false
        lastSegment = snap.segment
        // GPS jitter may move the snapped point back a little; never rewind far.
        progressM = max(progressM - BACKTRACK_TOLERANCE_M, snap.alongM).coerceAtMost(totalM)

        val nextIdx = nextIndex() ?: return null
        val (maneuver, maneuverAlong) = steps[nextIdx]
        val distance = max(0.0, maneuverAlong - progressM)

        if (maneuver.type == "arrive" && distance <= ARRIVE_M) {
            arrived = true
            return NavEvent(NavEvent.Kind.ARRIVED, maneuver, 0)
        }
        val stage = when {
            distance <= nowDistanceM(speed) -> NavEvent.Stage.NOW
            distance <= nearDistanceM(speed) -> NavEvent.Stage.NEAR
            distance <= farDistanceM(speed) -> NavEvent.Stage.FAR
            else -> null
        }
        if (!started) {
            started = true
            if (stage != null) announced[nextIdx] = stage
            return NavEvent(NavEvent.Kind.START, maneuver, distance.roundToInt(), stage)
        }
        if (stage == null || maneuver.type == "arrive" && stage == NavEvent.Stage.NOW) return null
        val previous = announced[nextIdx]
        if (previous != null && previous.ordinal >= stage.ordinal) return null
        announced[nextIdx] = stage
        return NavEvent(NavEvent.Kind.INSTRUCTION, maneuver, distance.roundToInt(), stage)
    }

    private fun nextIndex(): Int? = steps.indices.firstOrNull { steps[it].second > progressM + PASSED_M }
        ?: steps.indices.lastOrNull()?.takeIf { steps[it].first.type == "arrive" && !arrived }

    private class Snap(val segment: Int, val alongM: Double, val crossTrackM: Double)

    /** Nearest point on segments [from, to] using a local flat projection. */
    private fun project(lat: Double, lng: Double, from: Int, to: Int): Snap? {
        if (to < from) return null
        var best: Snap? = null
        val kx = 111_320.0 * cos(Math.toRadians(lat))
        val ky = 110_540.0
        for (i in from..to) {
            val a = points[i]
            val b = points[i + 1]
            val ax = (a.lng - lng) * kx
            val ay = (a.lat - lat) * ky
            val bx = (b.lng - lng) * kx
            val by = (b.lat - lat) * ky
            val dx = bx - ax
            val dy = by - ay
            val len2 = dx * dx + dy * dy
            val t = if (len2 == 0.0) 0.0 else (-(ax * dx + ay * dy) / len2).coerceIn(0.0, 1.0)
            val px = ax + t * dx
            val py = ay + t * dy
            val cross = kotlin.math.sqrt(px * px + py * py)
            if (best == null || cross < best.crossTrackM) {
                best = Snap(i, along[i] + t * (along[i + 1] - along[i]), cross)
            }
        }
        return best
    }

    companion object {
        const val MAX_POINTS = 20_000
        const val MAX_MANEUVERS = 2_000
        const val MAX_ACCURACY_M = 40f
        const val OFF_ROUTE_M = 50.0
        const val OFF_ROUTE_FIXES = 3
        const val ARRIVE_M = 30.0
        const val PASSED_M = 5.0
        const val BACKTRACK_TOLERANCE_M = 30.0

        fun farDistanceM(speedMps: Float) = (speedMps * 30.0).coerceIn(400.0, 1_200.0)
        fun nearDistanceM(speedMps: Float) = (speedMps * 10.0).coerceIn(80.0, 300.0)
        fun nowDistanceM(speedMps: Float) = (speedMps * 3.0).coerceIn(15.0, 40.0)

        /** "Continue on the same road" style steps would only be noise in the ear. */
        fun isSpoken(m: NavManeuver): Boolean = when (m.type) {
            "depart", "notification" -> false
            "new name", "continue" -> m.modifier != null && m.modifier != "straight"
            else -> true
        }
    }
}

/** Spoken and displayed navigation wording (Uzbek, Russian voice fallback, English). */
object NavigationPhrases {
    fun text(event: NavEvent, language: String): String {
        val m = event.maneuver
        return when (event.kind) {
            NavEvent.Kind.ARRIVED -> when (language) {
                "uz" -> "Manzilga yetib keldingiz."
                "ru" -> "Вы прибыли."
                else -> "You have arrived."
            }
            NavEvent.Kind.OFF_ROUTE -> when (language) {
                "uz" -> "Marshrutdan chiqdingiz. Yangi yo'l hisoblanmoqda."
                "ru" -> "Вы сошли с маршрута. Строю новый."
                else -> "You left the route. Finding a new one."
            }
            NavEvent.Kind.START -> {
                val start = when (language) { "uz" -> "Marshrut boshlandi."; "ru" -> "Маршрут построен."; else -> "Route started." }
                if (m == null || event.stage == null) start + " " + straightOn(event.distanceM, language)
                else start + " " + instruction(m, event.distanceM, event.stage, language)
            }
            NavEvent.Kind.INSTRUCTION -> instruction(m!!, event.distanceM, event.stage!!, language)
        }
    }

    private fun straightOn(distanceM: Int, language: String): String {
        val d = distanceWords(distanceM, language)
        return when (language) {
            "uz" -> "$d to'g'riga yuring."
            "ru" -> "Двигайтесь прямо $d."
            else -> "Continue straight for $d."
        }
    }

    private fun instruction(m: NavManeuver, distanceM: Int, stage: NavEvent.Stage, language: String): String {
        val action = action(m, language)
        if (stage == NavEvent.Stage.NOW) return action.replaceFirstChar { it.uppercase() } + "."
        val d = distanceWords(distanceM, language)
        return when (language) {
            "uz" -> "${d}dan keyin $action."
            "ru" -> "Через $d $action."
            else -> "In $d, $action."
        }
    }

    fun distanceWords(distanceM: Int, language: String): String {
        if (distanceM >= 1_000) {
            val km = (distanceM / 100.0).roundToInt() / 10.0
            val text = if (km % 1.0 == 0.0) km.toInt().toString() else km.toString().replace('.', if (language == "en") '.' else ',')
            return when (language) { "uz" -> "$text kilometr"; "ru" -> "$text км"; else -> "$text kilometres" }
        }
        val rounded = RoadAlertEngine.roundForSpeech(distanceM.toDouble())
        return when (language) { "uz" -> "$rounded metr"; "ru" -> "$rounded метров"; else -> "$rounded metres" }
    }

    fun action(m: NavManeuver, language: String): String {
        val mod = m.modifier ?: "straight"
        val side = if (mod.contains("left")) "left" else if (mod.contains("right")) "right" else "straight"
        return when (m.type) {
            "arrive" -> when (language) { "uz" -> "manzilga yetasiz"; "ru" -> "вы прибудете"; else -> "you will arrive" }
            "roundabout", "rotary", "roundabout turn" -> {
                val exit = m.exit
                when (language) {
                    "uz" -> if (exit != null) "aylanma yo'lda $exit-chiqishga chiqing" else "aylanma yo'lga kiring"
                    "ru" -> if (exit != null) "на круге съезжайте на $exit-й съезд" else "въезжайте на круг"
                    else -> if (exit != null) "at the roundabout take exit $exit" else "enter the roundabout"
                }
            }
            "exit roundabout", "exit rotary" -> when (language) {
                "uz" -> "aylanma yo'ldan chiqing"; "ru" -> "съезжайте с круга"; else -> "leave the roundabout"
            }
            "fork" -> when (language) {
                "uz" -> if (side == "left") "ayriliqda chapga yuring" else "ayriliqda o'ngga yuring"
                "ru" -> if (side == "left") "на развилке держитесь левее" else "на развилке держитесь правее"
                else -> if (side == "left") "keep left at the fork" else "keep right at the fork"
            }
            "on ramp", "off ramp" -> when (language) {
                "uz" -> if (side == "left") "chapdagi chiqishga o'ting" else "o'ngdagi chiqishga o'ting"
                "ru" -> if (side == "left") "съезжайте левее" else "съезжайте правее"
                else -> if (side == "left") "take the ramp on the left" else "take the ramp on the right"
            }
            "merge" -> when (language) {
                "uz" -> "yo'lga qo'shiling"; "ru" -> "перестройтесь в поток"; else -> "merge"
            }
            else -> turn(mod, language)
        }
    }

    private fun turn(modifier: String, language: String): String = when (language) {
        "uz" -> when (modifier) {
            "left" -> "chapga buriling"
            "right" -> "o'ngga buriling"
            "slight left" -> "biroz chapga buriling"
            "slight right" -> "biroz o'ngga buriling"
            "sharp left" -> "keskin chapga buriling"
            "sharp right" -> "keskin o'ngga buriling"
            "uturn" -> "orqaga qayriling"
            else -> "to'g'riga yuring"
        }
        "ru" -> when (modifier) {
            "left" -> "поверните налево"
            "right" -> "поверните направо"
            "slight left" -> "плавно поверните налево"
            "slight right" -> "плавно поверните направо"
            "sharp left" -> "резко поверните налево"
            "sharp right" -> "резко поверните направо"
            "uturn" -> "развернитесь"
            else -> "двигайтесь прямо"
        }
        else -> when (modifier) {
            "left" -> "turn left"
            "right" -> "turn right"
            "slight left" -> "bear left"
            "slight right" -> "bear right"
            "sharp left" -> "turn sharp left"
            "sharp right" -> "turn sharp right"
            "uturn" -> "make a U-turn"
            else -> "continue straight"
        }
    }
}
