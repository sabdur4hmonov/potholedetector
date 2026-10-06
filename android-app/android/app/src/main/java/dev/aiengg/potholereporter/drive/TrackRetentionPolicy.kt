package dev.aiengg.potholereporter.drive

import android.content.Context

/**
 * Raw GPS drive tracks are movement data about the person, so they are kept for a bounded
 * time only: 30 days after the drive ended, or not at all when the user turned track keeping
 * off. Pothole reports keep their own coordinates; this policy never touches them.
 */
object TrackRetentionPolicy {
    const val RETENTION_DAYS = 30L
    const val RETENTION_SECONDS = RETENTION_DAYS * 24L * 60L * 60L

    private const val PREFERENCES = "track_retention"
    private const val KEY_KEEP_TRACKS = "keep_tracks"

    /** Sessions that ended before this instant (epoch seconds) have expired tracks. */
    fun cutoffSeconds(nowSeconds: Long): Long = nowSeconds - RETENTION_SECONDS

    fun isExpired(endedAtSeconds: Long?, startedAtSeconds: Long, nowSeconds: Long): Boolean {
        val reference = endedAtSeconds ?: startedAtSeconds
        return reference < cutoffSeconds(nowSeconds)
    }

    /** Default is to keep (for 30 days); the user can opt out in Settings. */
    fun keepTracks(context: Context): Boolean =
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .getBoolean(KEY_KEEP_TRACKS, true)

    fun setKeepTracks(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_KEEP_TRACKS, enabled).commit()
    }
}
