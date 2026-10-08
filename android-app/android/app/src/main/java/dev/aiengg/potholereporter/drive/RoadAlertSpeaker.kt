package dev.aiengg.potholereporter.drive

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.ToneGenerator
import android.speech.tts.TextToSpeech

/**
 * Plays a short tone and, when the phone has an offline voice for it, speaks the warning.
 * Uses Android's own text-to-speech; nothing is sent anywhere. If the phone has no Uzbek
 * voice, Russian and then English are tried, because many phones ship only those.
 */
internal class RoadAlertSpeaker(
    context: Context,
    private val language: String,
    voiceEnabled: Boolean
) : TextToSpeech.OnInitListener {
    private val tts: TextToSpeech? = if (voiceEnabled) {
        runCatching { TextToSpeech(context.applicationContext, this) }.getOrNull()
    } else null
    private val tone: ToneGenerator? = runCatching {
        ToneGenerator(AudioManager.STREAM_NOTIFICATION, TONE_VOLUME)
    }.getOrNull()
    @Volatile private var speechLanguage: String? = null

    override fun onInit(status: Int) {
        val engine = tts ?: return
        if (status != TextToSpeech.SUCCESS) return
        runCatching {
            engine.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
        }
        for (candidate in listOf(language, "ru", "en").distinct()) {
            val result = runCatching { engine.setLanguage(RoadAlertPhrases.locale(candidate)) }
                .getOrDefault(TextToSpeech.LANG_NOT_SUPPORTED)
            if (result >= TextToSpeech.LANG_AVAILABLE) {
                speechLanguage = candidate
                return
            }
        }
    }

    /** Returns the on-screen text in the app language. */
    fun announce(alert: RoadAlert, interrupt: Boolean = true): String {
        runCatching { tone?.startTone(ToneGenerator.TONE_PROP_BEEP2, TONE_MS) }
        return say(alert.hazard.id, interrupt) { RoadAlertPhrases.text(alert, it) }
    }

    /**
     * Speaks [textFor] in the best available voice language and returns it in the app
     * language. [interrupt] replaces whatever is being said; otherwise it waits its turn.
     */
    fun say(utteranceId: String, interrupt: Boolean, textFor: (String) -> String): String {
        speechLanguage?.let { spoken ->
            runCatching {
                tts?.speak(textFor(spoken),
                    if (interrupt) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD, null, utteranceId)
            }
        }
        return textFor(language)
    }

    fun shutdown() {
        runCatching { tts?.stop() }
        runCatching { tts?.shutdown() }
        runCatching { tone?.release() }
    }

    companion object {
        const val TONE_VOLUME = 90
        const val TONE_MS = 350
    }
}
