package dev.aiengg.potholereporter.drive

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import dev.aiengg.potholereporter.MainActivity
import kotlin.math.roundToInt

data class RoadAlertStatus(
    val running: Boolean,
    val cameraCount: Int = 0,
    val potholeCount: Int = 0,
    val speedKmh: Int? = null,
    val gpsReady: Boolean = false,
    val alertText: String? = null,
    val alertKind: String? = null,
    val alertAgeMs: Long? = null
)

/**
 * "Antiradar" mode: a location-only foreground service that announces known speed cameras
 * and potholes ahead. No camera, no recording, no network; it only needs precise location
 * and the persistent notification. Drive mode gives the same warnings itself, so the two
 * never run together.
 */
class RoadAlertService : Service() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private var locationProvider: NativeDriveLocationProvider? = null
    private var engine: RoadAlertEngine? = null
    private var speaker: RoadAlertSpeaker? = null
    private var language = "en"
    private var cameraCount = 0
    private var potholeCount = 0
    @Volatile private var lastSpeedKmh: Int? = null
    @Volatile private var lastFixElapsedMs = 0L
    @Volatile private var lastAlertText: String? = null
    @Volatile private var lastAlertKind: String? = null
    @Volatile private var lastAlertElapsedMs = 0L
    private var lastNotifiedText: String? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> start(
                intent.getStringExtra(EXTRA_LANGUAGE) ?: "en",
                intent.getBooleanExtra(EXTRA_VOICE, true)
            )
            else -> stopNow()
        }
        return START_NOT_STICKY
    }

    private fun start(requestedLanguage: String, voice: Boolean) {
        language = requestedLanguage
        val hazards = takeStaged()
        cameraCount = hazards.count { it.kind.isCamera }
        potholeCount = hazards.size - cameraCount
        createChannel(this)
        // Android requires the notification within seconds of startForegroundService.
        val notification = buildNotification(null)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        speaker?.shutdown()
        speaker = RoadAlertSpeaker(this, language, voice)
        engine = RoadAlertEngine(hazards)
        locationProvider?.stopUpdates()
        locationProvider = NativeDriveLocationProvider(this, onLocationUpdate = ::onFix)
            .also { it.startUpdates(System.currentTimeMillis()) }
        active = this
        publish()
    }

    /** Main looper, once per GPS fix. */
    private fun onFix(fix: GpsFix) {
        if (active !== this) return
        lastFixElapsedMs = SystemClock.elapsedRealtime()
        lastSpeedKmh = fix.speedMps?.takeIf { it.isFinite() && it >= 0f }?.let { (it * 3.6f).roundToInt() }
        val alert = runCatching {
            engine?.onFix(fix.lat, fix.lng, fix.accuracy, fix.speedMps, fix.heading, fix.elapsedRealtimeMs)
        }.getOrNull()
        if (alert != null) {
            lastAlertText = speaker?.announce(alert) ?: RoadAlertPhrases.text(alert, language)
            lastAlertKind = alert.hazard.kind.wireValue
            lastAlertElapsedMs = SystemClock.elapsedRealtime()
            updateNotification(lastAlertText)
        }
        publish()
    }

    private fun snapshot(): RoadAlertStatus {
        val now = SystemClock.elapsedRealtime()
        return RoadAlertStatus(
            running = true,
            cameraCount = cameraCount,
            potholeCount = potholeCount,
            speedKmh = lastSpeedKmh,
            gpsReady = lastFixElapsedMs > 0L && now - lastFixElapsedMs < GPS_STALE_MS,
            alertText = lastAlertText,
            alertKind = lastAlertKind,
            alertAgeMs = lastAlertText?.let { now - lastAlertElapsedMs }
        )
    }

    private fun publish() {
        val status = snapshot()
        runCatching { onStatusListener?.invoke(status) }
    }

    private fun updateNotification(text: String?) {
        if (text == lastNotifiedText) return
        lastNotifiedText = text
        runCatching {
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .notify(NOTIFICATION_ID, buildNotification(text))
        }
    }

    private fun buildNotification(alertText: String?): Notification {
        val open = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stop = PendingIntent.getService(
            this, 1,
            Intent(this, RoadAlertService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val uz = language == "uz"
        val title = if (uz) "Antiradar yoqilgan · faqat GPS" else "Road warnings on · GPS only"
        val summary = if (uz) "$cameraCount ta kamera, $potholeCount ta chuqur · kamera ishlatilmaydi"
            else "$cameraCount cameras, $potholeCount potholes · camera not used"
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(alertText ?: summary)
            .setSubText(if (alertText != null) summary else null)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentIntent(open)
            .setDeleteIntent(stop)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_NAVIGATION)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, if (uz) "To'xtatish" else "Stop", stop)
            .build()
    }

    private fun stopNow() {
        cleanUp()
        runCatching { stopForeground(STOP_FOREGROUND_REMOVE) }
        stopSelf()
    }

    private fun cleanUp() {
        runCatching { locationProvider?.stopUpdates() }
        locationProvider = null
        runCatching { speaker?.shutdown() }
        speaker = null
        engine = null
        if (active === this) {
            active = null
            runCatching { onStatusListener?.invoke(RoadAlertStatus(running = false)) }
        }
    }

    override fun onDestroy() {
        cleanUp()
        mainHandler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    companion object {
        const val ACTION_START = "dev.aiengg.potholereporter.ROAD_ALERTS_START"
        const val ACTION_STOP = "dev.aiengg.potholereporter.ROAD_ALERTS_STOP"
        const val EXTRA_LANGUAGE = "extra_language"
        const val EXTRA_VOICE = "extra_voice"
        const val CHANNEL_ID = "road_alert_channel"
        const val NOTIFICATION_ID = 7_301
        const val GPS_STALE_MS = 10_000L

        @Volatile var active: RoadAlertService? = null
            private set
        @Volatile var onStatusListener: ((RoadAlertStatus) -> Unit)? = null
        @Volatile private var staged: List<RoadHazard> = emptyList()

        fun status(): RoadAlertStatus = active?.snapshot() ?: RoadAlertStatus(running = false)

        fun start(context: Context, hazards: List<RoadHazard>, language: String, voice: Boolean) {
            staged = hazards.take(RoadAlertEngine.MAX_HAZARDS)
            ContextCompat.startForegroundService(
                context,
                Intent(context, RoadAlertService::class.java)
                    .setAction(ACTION_START)
                    .putExtra(EXTRA_LANGUAGE, language)
                    .putExtra(EXTRA_VOICE, voice)
            )
        }

        fun stop(context: Context) {
            if (active == null) return
            context.startService(Intent(context, RoadAlertService::class.java).setAction(ACTION_STOP))
        }

        private fun takeStaged(): List<RoadHazard> = staged.also { staged = emptyList() }

        fun createChannel(context: Context) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
            val channel = NotificationChannel(
                CHANNEL_ID, "Road warnings", NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Speed camera and pothole warnings while driving"
                setShowBadge(false)
            }
            (context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(channel)
        }
    }
}
