package dev.aiengg.potholereporter.drive

import org.json.JSONArray
import java.time.Instant

/** Only retained, opted-in track points reach this serializer. No map/network calls. */
internal object NativeDriveGpx {
    data class Point(val offset: Double, val lat: Double, val lng: Double)
    fun points(json: String): List<Point> {
        require(json.length <= 4_000_000)
        val array = JSONArray(json)
        require(array.length() <= 20_000)
        val points = ArrayList<Point>()
        var last = -1.0
        for (i in 0 until array.length()) {
            val row = array.optJSONArray(i) ?: continue
            val offset = row.optDouble(0, Double.NaN)
            val lat = row.optDouble(1, Double.NaN)
            val lng = row.optDouble(2, Double.NaN)
            if (!offset.isFinite() || offset !in 0.0..86_400.0 || offset < last ||
                !lat.isFinite() || lat !in -90.0..90.0 || !lng.isFinite() || lng !in -180.0..180.0) continue
            points.add(Point(offset, lat, lng)); last = offset
        }
        return points
    }
    fun encode(startedAt: Long, points: List<Point>): String = buildString {
        append("<?xml version=\"1.0\" encoding=\"UTF-8\"?><gpx version=\"1.1\" creator=\"Pothole Reporter\" xmlns=\"http://www.topografix.com/GPX/1/1\"><trk><trkseg>")
        for (p in points) append("<trkpt lat=\"${p.lat}\" lon=\"${p.lng}\"><time>${Instant.ofEpochMilli(startedAt*1000+(p.offset*1000).toLong())}</time></trkpt>")
        append("</trkseg></trk></gpx>")
    }
    fun shareText(start: Long, end: Long?, points: List<Point>): String = buildString {
        append("Drive: ${Instant.ofEpochSecond(start)} — ${end?.let(Instant::ofEpochSecond) ?: "unknown"}")
        if (points.isNotEmpty()) {
            append("\nStart: https://www.google.com/maps?q=${points.first().lat},${points.first().lng}")
            append("\nEnd: https://www.google.com/maps?q=${points.last().lat},${points.last().lng}")
        } else append("\nGPS track unavailable (not retained, expired or removed).")
    }
}
