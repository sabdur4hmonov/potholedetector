package dev.aiengg.potholereporter.drive

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream

/** Small private snapshot; validation finishes before either disk or live state changes. */
internal class NativeHazardStore(private val file: File,
    private val atomicReplace: (File, File) -> Unit) {
    fun load(): List<NativeHazard> {
        if (!file.exists()) return emptyList()
        require(file.length() <= MAX_BYTES) { "Hazard snapshot too large" }
        return parse(file.readText(Charsets.UTF_8))
    }

    fun save(values: List<NativeHazard>) {
        validate(values)
        val array = JSONArray()
        values.forEach { h -> array.put(JSONObject().put("id", h.id).put("lat", h.lat)
            .put("lng", h.lng).put("kind", h.kind)) }
        val bytes = JSONObject().put("version", 1).put("hazards", array).toString().toByteArray(Charsets.UTF_8)
        require(bytes.size <= MAX_BYTES) { "Hazard snapshot too large" }
        check(file.parentFile!!.isDirectory || file.parentFile!!.mkdirs()) { "Hazard storage unavailable" }
        val temporary = File(file.parentFile, "hazards-v1.json.tmp")
        try {
            FileOutputStream(temporary).use { it.write(bytes); it.fd.sync() }
            atomicReplace(temporary, file) // Same directory, atomic rename; old file survives failure.
        } finally { if (temporary.exists()) check(temporary.delete()) { "Hazard temporary cleanup failed" } }
    }

    companion object {
        const val MAX_ITEMS = 5_000
        const val MAX_BYTES = 1_048_576
        fun validate(values: List<NativeHazard>) {
            require(values.size <= MAX_ITEMS) { "At most 5000 hazards are supported" }
            require(values.map { it.id }.toSet().size == values.size) { "Duplicate hazard id" }
            values.forEach { h ->
                require(h.id.isNotBlank() && h.id.length <= 64 && h.lat.isFinite() &&
                    h.lat in -90.0..90.0 && h.lng.isFinite() && h.lng in -180.0..180.0 &&
                    h.kind in setOf("confirmed", "unconfirmed")) { "Invalid hazard" }
            }
        }
        fun parse(raw: String): List<NativeHazard> {
            require(raw.toByteArray(Charsets.UTF_8).size <= MAX_BYTES) { "Hazard snapshot too large" }
            val root = JSONObject(raw)
            require(root.get("version") is Number && root.getDouble("version") == 1.0) { "Unsupported hazard version" }
            val items = root.getJSONArray("hazards")
            require(items.length() <= MAX_ITEMS) { "At most 5000 hazards are supported" }
            return (0 until items.length()).map { i ->
                val item = items.getJSONObject(i)
                require(item.get("id") is String && item.get("kind") is String &&
                    item.get("lat") is Number && item.get("lng") is Number) { "Invalid hazard types" }
                NativeHazard(item.getString("id"), item.getDouble("lat"), item.getDouble("lng"), item.getString("kind"))
            }.also(::validate)
        }
    }
}
