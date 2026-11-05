package dev.aiengg.potholereporter.drive

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.system.Os
import java.io.File
import java.util.Locale
import kotlin.math.roundToInt

/** Drive-owned offline output, independent of WebView visibility or detection mode. */
internal class NativeHazardAlerter(
    context: Context,
    private val language: String,
    private val enabled: Boolean,
    leadSeconds: Int,
    includeUnconfirmed: Boolean,
    private val onAlert: (String) -> Unit
) {
    private val handler = Handler(Looper.getMainLooper())
    private val policy = NativeHazardAlertPolicy(leadSeconds, includeUnconfirmed)
    private var snapshot = emptyList<NativeHazard>()
    private val live = LinkedHashMap<String, NativeHazard>()
    private val audio = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
    private val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
    private val attributes = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
    private val focusListener = AudioManager.OnAudioFocusChangeListener { change ->
        if (change == AudioManager.AUDIOFOCUS_LOSS || change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) {
            handler.post { tts?.stop(); tone?.stopTone(); abandonFocus() }
        }
    }
    private var focus: AudioFocusRequest? = null
    private var tone: ToneGenerator? = null
    private var tts: TextToSpeech? = null
    private var voiceLanguage = "en"
    private var ready = false
    private var closed = false
    private var testPending = false
    private var utterance = 0L
    @Volatile var lastAlert: String? = null; private set
    @Volatile var loadedCount = 0; private set
    private val finishAudio = Runnable { tts?.stop(); abandonFocus() }
    private val pendingTest = Runnable { if (testPending) { testPending = false; play(testAlert()) } }

    init {
        tts = runCatching { TextToSpeech(context.applicationContext) { status ->
            handler.post {
                if (closed) return@post
                if (status == TextToSpeech.SUCCESS) runCatching {
                    val engine = tts
                    val choices = if (language == "uz") listOf("uz-UZ", "ru-RU", "en") else listOf("en")
                    for (tag in choices) {
                        val locale = Locale.forLanguageTag(tag)
                        // Never select an online/network voice or request a voice download.
                        val voice = runCatching { engine?.voices?.firstOrNull {
                            !it.isNetworkConnectionRequired && it.locale.language == locale.language
                        } }.getOrNull() ?: continue
                        if (engine?.setVoice(voice) == TextToSpeech.SUCCESS) {
                            voiceLanguage = locale.language; ready = true; break
                        }
                    }
                    engine?.setAudioAttributes(attributes)
                    engine?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                        override fun onStart(id: String?) = Unit
                        override fun onDone(id: String?) { finish(id) }
                        @Deprecated("Android callback") override fun onError(id: String?) { finish(id) }
                        private fun finish(id: String?) { handler.post {
                            if (id == utterance.toString()) abandonFocus()
                        } }
                    })
                }.onFailure { ready = false }
                if (testPending) { handler.removeCallbacks(pendingTest); pendingTest.run() }
            }
        } }.getOrNull()
    }

    @Synchronized fun replaceSnapshot(values: List<NativeHazard>, acknowledgedNativeIds: Set<String> = emptySet()) {
        if (closed) return
        live.keys.removeAll(acknowledgedNativeIds + values.map { it.id }.toSet())
        snapshot = values
        rebuild()
    }

    @Synchronized fun addLive(hazard: NativeHazard) {
        if (closed) return
        NativeHazardStore.validate(listOf(hazard))
        if (hazard.id !in live && snapshot.none { it.id == hazard.id } &&
            snapshot.size + live.size >= NativeHazardStore.MAX_ITEMS) return
        live[hazard.id] = hazard
        rebuild()
    }

    @Synchronized fun removeLive(id: String) { live.remove(id); snapshot = snapshot.filterNot { it.id == id }; rebuild() }
    @Synchronized fun liveIds(): List<Long> = live.keys.mapNotNull { it.removePrefix("native:").toLongOrNull() }
    private fun rebuild() {
        val merged = snapshot.associateBy { it.id }.toMutableMap().apply { putAll(live) }
        policy.replace(merged.values.take(NativeHazardStore.MAX_ITEMS))
        loadedCount = if (enabled) policy.loadedCount else 0
    }

    @Synchronized fun onFix(fix: GpsFix) {
        if (closed || !enabled || SystemClock.elapsedRealtime() - fix.elapsedRealtimeMs !in 0..5_000) return
        val result = policy.evaluate(NativeHazardAlertPolicy.Fix(fix.lat, fix.lng,
            fix.accuracy?.toDouble() ?: return, fix.speedMps?.toDouble() ?: return,
            fix.heading?.toDouble() ?: return, fix.elapsedRealtimeMs)) ?: return
        handler.post { if (!closed) play(result) }
    }

    fun testOnce() {
        testPending = true
        if (ready) pendingTest.run() else handler.postDelayed(pendingTest, 1_500)
    }
    private fun testAlert() = NativeHazardAlertPolicy.Alert(listOf("test"), 300.0, false)

    private fun phrase(alert: NativeHazardAlertPolicy.Alert, lang: String): String {
        val meters = ((alert.distanceM / 10).roundToInt() * 10).coerceAtLeast(10)
        val count = alert.ids.size
        return when (lang) {
            "uz" -> "Diqqat, $meters metrdan keyin ${if (alert.possible) "ehtimoliy " else ""}" +
                if (count > 1) "$count ta chuqur" else "chuqur"
            "ru" -> "Внимание, через $meters метров " +
                (if (alert.possible) "возможная неровность" else if (count > 1) "ямы: $count" else "яма")
            else -> "${if (alert.possible) "Possible " else ""}${if (count > 1) "$count potholes" else "Pothole"} in $meters meters"
        }
    }

    private fun play(alert: NativeHazardAlertPolicy.Alert) {
        if (closed) return
        lastAlert = phrase(alert, if (language == "uz") "uz" else "en")
        onAlert(lastAlert!!)
        runCatching {
            if (Build.VERSION.SDK_INT >= 26) vibrator?.vibrate(
                VibrationEffect.createWaveform(longArrayOf(0, 130, 70, 180), -1), attributes)
            else @Suppress("DEPRECATION") vibrator?.vibrate(longArrayOf(0, 130, 70, 180), -1)
        }
        val granted = runCatching {
            if (Build.VERSION.SDK_INT >= 26) {
                val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                    .setAudioAttributes(attributes).setOnAudioFocusChangeListener(focusListener).build()
                focus = request
                audio?.requestAudioFocus(request) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            } else @Suppress("DEPRECATION") (audio?.requestAudioFocus(focusListener,
                AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED)
        }.getOrDefault(false)
        if (!granted) return // Notification and vibration still happened.
        runCatching {
            tone?.release()
            tone = ToneGenerator(AudioManager.STREAM_MUSIC, 80).also { it.startTone(ToneGenerator.TONE_PROP_BEEP2, 250) }
        }
        val id = (++utterance).toString()
        handler.postDelayed({
            if (!closed && id == utterance.toString() && ready) {
                if (runCatching { tts?.speak(phrase(alert, voiceLanguage), TextToSpeech.QUEUE_FLUSH, null, id) }
                    .getOrNull() != TextToSpeech.SUCCESS) abandonFocus()
            } else abandonFocus()
        }, 300)
        handler.removeCallbacks(finishAudio)
        handler.postDelayed(finishAudio, 3_800) // Bound ducking even if an engine never calls back.
    }

    private fun abandonFocus() {
        handler.removeCallbacks(finishAudio)
        if (Build.VERSION.SDK_INT >= 26) focus?.let { runCatching { audio?.abandonAudioFocusRequest(it) } }
        else @Suppress("DEPRECATION") runCatching { audio?.abandonAudioFocus(focusListener) }
        focus = null
    }
    fun silence() { handler.removeCallbacksAndMessages(null); tts?.stop(); tone?.stopTone(); vibrator?.cancel(); abandonFocus() }
    @Synchronized fun close() {
        if (closed) return
        closed = true; testPending = false
        silence(); tts?.shutdown(); tts = null; tone?.release(); tone = null
    }

    companion object {
        fun store(context: Context) = NativeHazardStore(File(context.filesDir, "hazards/hazards-v1.json")) { from, to ->
            Os.rename(from.absolutePath, to.absolutePath)
        }
    }
}
