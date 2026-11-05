package dev.aiengg.potholereporter.drive

import java.util.PriorityQueue
import kotlin.math.*

internal data class NativeHazard(val id: String, val lat: Double, val lng: Double, val kind: String)

/** Offline geometry and drive-lifetime state. No Android, wall clock, audio or I/O. */
internal class NativeHazardAlertPolicy(
    private val leadSeconds: Int = 20,
    private val includeUnconfirmed: Boolean = true
) {
    data class Fix(val lat: Double, val lng: Double, val accuracy: Double,
                   val speed: Double, val heading: Double, val elapsedMs: Long)
    data class Alert(val ids: List<String>, val distanceM: Double, val possible: Boolean)
    private data class Disarmed(val radius: Double, val generation: Long)
    private data class Check(val afterTravel: Double, val id: String, val generation: Long)
    private var hazards = emptyMap<String, NativeHazard>()
    private var grid = emptyMap<Int, Map<Int, List<NativeHazard>>>()
    private val disarmed = HashMap<String, Disarmed>()
    private val checks = PriorityQueue<Check>(compareBy { it.afterTravel })
    private var generation = 0L
    private var travel = 0.0
    private var previous: Fix? = null
    private var lastSpoken: Long? = null
    var examinedLastFix = 0; private set
    var pendingCount = 0; private set
    val loadedCount get() = hazards.values.count { includeUnconfirmed || it.kind == "confirmed" }

    init { require(leadSeconds in setOf(10, 20, 30)) }

    fun replace(values: List<NativeHazard>) {
        NativeHazardStore.validate(values)
        hazards = values.associateBy { it.id }
        grid = values.groupBy { cell(it.lat) }.mapValues { (_, row) -> row.groupBy { wrapCell(cell(it.lng)) } }
        disarmed.keys.retainAll(hazards.keys)
        // Rebuild rather than accumulating stale heap entries across repeated WebView syncs.
        checks.clear()
        disarmed.forEach { (id, state) -> checks.add(Check(travel, id, state.generation)) }
        pendingCount = 0
    }

    fun evaluate(fix: Fix): Alert? {
        examinedLastFix = 0
        if (!valid(fix) || previous?.let { fix.elapsedMs <= it.elapsedMs } == true) return null
        previous?.let { travel += distance(it.lat, it.lng, fix.lat, fix.lng) }
        previous = fix
        val d = leadDistance(fix.speed, leadSeconds)
        while (checks.peek()?.afterTravel?.let { it <= travel } == true) {
            val item = checks.remove()
            val state = disarmed[item.id] ?: continue
            if (state.generation != item.generation) continue
            val h = hazards[item.id] ?: continue
            val away = distance(fix.lat, fix.lng, h.lat, h.lng)
            if (away > state.radius) disarmed.remove(item.id)
            else checks.add(item.copy(afterTravel = travel + max(1.0, state.radius - away)))
        }
        val latDelta = Math.toDegrees(d / EARTH)
        val lngDelta = min(180.0, latDelta / max(0.000001, cos(Math.toRadians(fix.lat))))
        val near = ArrayList<Pair<NativeHazard, Double>>()
        for (rowIndex in cell(max(-90.0, fix.lat - latDelta))..cell(min(90.0, fix.lat + latDelta))) {
            val row = grid[rowIndex] ?: continue
            // At polar latitudes query populated buckets, not an enormous longitude range.
            val low = cell(fix.lng - lngDelta); val high = cell(fix.lng + lngDelta)
            val buckets = if (high - low > 200) row.keys else (low..high).map { wrapCell(it) }
            for (column in buckets) for (h in row[column].orEmpty()) {
                examinedLastFix++
                if (h.id in disarmed || (!includeUnconfirmed && h.kind != "confirmed")) continue
                val meters = distance(fix.lat, fix.lng, h.lat, h.lng)
                if (meters > d) continue
                val angle = abs((bearing(fix.lat, fix.lng, h.lat, h.lng) - fix.heading + 540.0) % 360.0 - 180.0)
                if (meters <= 40.0 || angle <= 30.0) near.add(h to meters)
            }
        }
        near.sortWith(compareBy<Pair<NativeHazard, Double>> { it.second }.thenBy { it.first.id })
        // Pending candidates are bounded by the 5,000-item index and revalidated each fix;
        // hazards passed/left behind never become stale spoken warnings.
        pendingCount = near.size
        if (near.isEmpty() || lastSpoken?.let { fix.elapsedMs - it < 4_000 } == true) return null
        val seed = near.first()
        val group = near.filter { distance(seed.first.lat, seed.first.lng, it.first.lat, it.first.lng) <= 30.0 }
        for ((h, meters) in group) {
            val state = Disarmed(max(300.0, 1.5 * d), ++generation)
            disarmed[h.id] = state
            checks.add(Check(travel + max(1.0, state.radius - meters), h.id, state.generation))
        }
        pendingCount -= group.size
        lastSpoken = fix.elapsedMs
        return Alert(group.map { it.first.id }, seed.second, group.any { it.first.kind == "unconfirmed" })
    }

    companion object {
        private const val EARTH = 6_371_000.0
        private const val CELL = 0.005 // about 556 m north/south
        private const val COLUMNS = 72_000
        private fun cell(value: Double) = floor(value / CELL).toInt()
        private fun wrapCell(value: Int) = Math.floorMod(value + COLUMNS / 2, COLUMNS) - COLUMNS / 2
        fun leadDistance(speed: Double, seconds: Int = 20) = (speed * seconds).coerceIn(80.0, 700.0)
        private fun valid(f: Fix) = f.lat.isFinite() && f.lat in -90.0..90.0 &&
            f.lng.isFinite() && f.lng in -180.0..180.0 && f.accuracy.isFinite() &&
            f.accuracy in 0.0..30.0 && f.speed.isFinite() && f.speed >= 3.0 &&
            f.heading.isFinite() && f.heading in 0.0..<360.0 && f.elapsedMs >= 0
        fun distance(a: Double, b: Double, c: Double, d: Double): Double {
            val x = sin(Math.toRadians(c - a) / 2).pow(2) + cos(Math.toRadians(a)) *
                cos(Math.toRadians(c)) * sin(Math.toRadians(d - b) / 2).pow(2)
            return 2 * EARTH * asin(sqrt(x.coerceIn(0.0, 1.0)))
        }
        private fun bearing(a: Double, b: Double, c: Double, d: Double): Double {
            val delta = Math.toRadians(d - b)
            return (Math.toDegrees(atan2(sin(delta) * cos(Math.toRadians(c)),
                cos(Math.toRadians(a)) * sin(Math.toRadians(c)) -
                    sin(Math.toRadians(a)) * cos(Math.toRadians(c)) * cos(delta))) + 360) % 360
        }
    }
}
