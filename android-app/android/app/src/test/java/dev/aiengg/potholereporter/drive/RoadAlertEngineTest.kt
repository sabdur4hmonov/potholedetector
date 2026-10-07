package dev.aiengg.potholereporter.drive

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.cos

class RoadAlertEngineTest {
    private val lat0 = 41.3111
    private val lng0 = 69.2797
    private val metresPerDegLng = 111_320.0 * cos(Math.toRadians(lat0))

    private fun east(metres: Double) = lng0 + metres / metresPerDegLng
    private fun north(metres: Double) = lat0 + metres / 111_320.0

    /** Drives east from x=0 at [speed] m/s with 1 Hz fixes until [toMetres]; returns alerts. */
    private fun RoadAlertEngine.driveEast(
        speed: Float,
        fromMetres: Double = 0.0,
        toMetres: Double = 1_500.0,
        heading: Float? = 90f,
        accuracy: Float? = 5f,
        startMs: Long = 0L
    ): List<Pair<Double, RoadAlert>> {
        val alerts = mutableListOf<Pair<Double, RoadAlert>>()
        var x = fromMetres
        var t = startMs
        while (x <= toMetres) {
            onFix(lat0, east(x), accuracy, speed, heading, t)?.let { alerts += x to it }
            x += speed
            t += 1_000
        }
        return alerts
    }

    private fun pothole(x: Double, id: String = "p$x") =
        RoadHazard(id, RoadHazardKind.POTHOLE, lat0, east(x))

    @Test fun potholeAheadIsAnnouncedEarlyThenRightAhead() {
        val engine = RoadAlertEngine(listOf(pothole(1_000.0)))
        val alerts = engine.driveEast(speed = 14f) // ~50 km/h
        assertEquals(2, alerts.size)
        val (earlyAt, early) = alerts[0]
        assertEquals(RoadAlert.Stage.EARLY, early.stage)
        // 14 m/s * 14 s = 196 m of warning, so announced about 200 m before.
        assertTrue(1_000.0 - earlyAt in 182.0..196.0)
        assertEquals(200, early.distanceM)
        assertEquals(RoadAlert.Stage.NEAR, alerts[1].second.stage)
        assertTrue(1_000.0 - alerts[1].first <= 70.0)
    }

    @Test fun fasterDrivingWarnsEarlierWithinBounds() {
        assertEquals(150.0, RoadAlertEngine.warnDistanceM(RoadHazardKind.POTHOLE, 5f), 0.0)
        assertEquals(420.0, RoadAlertEngine.warnDistanceM(RoadHazardKind.POTHOLE, 30f), 0.0)
        assertEquals(600.0, RoadAlertEngine.warnDistanceM(RoadHazardKind.POTHOLE, 60f), 0.0)
        assertEquals(300.0, RoadAlertEngine.warnDistanceM(RoadHazardKind.SPEED_CAMERA, 8f), 0.0)
        assertEquals(616.0, RoadAlertEngine.warnDistanceM(RoadHazardKind.SPEED_CAMERA, 28f), 0.001)
        assertEquals(1_000.0, RoadAlertEngine.warnDistanceM(RoadHazardKind.SPEED_CAMERA, 60f), 0.0)
    }

    @Test fun hazardBehindOrBesideTheRoadIsSilent() {
        val behind = RoadAlertEngine(listOf(pothole(-300.0)))
        assertTrue(behind.driveEast(speed = 14f, toMetres = 600.0).isEmpty())
        // 400 m north of the road: never inside the 30 degree cone ahead.
        val beside = RoadAlertEngine(listOf(RoadHazard("side", RoadHazardKind.POTHOLE, north(400.0), east(800.0))))
        assertTrue(beside.driveEast(speed = 14f, toMetres = 1_000.0).isEmpty())
    }

    @Test fun cameraForTheOtherDirectionIsSilent() {
        val westbound = RoadHazard("cam-w", RoadHazardKind.SPEED_CAMERA, lat0, east(1_000.0), heading = 270f, speedLimitKmh = 60)
        val eastbound = RoadHazard("cam-e", RoadHazardKind.SPEED_CAMERA, lat0, east(1_000.0), heading = 90f, speedLimitKmh = 60)
        assertTrue(RoadAlertEngine(listOf(westbound)).driveEast(speed = 16f).isEmpty())
        val alerts = RoadAlertEngine(listOf(eastbound)).driveEast(speed = 16f)
        assertEquals(1, alerts.size) // a camera is announced once, with no "near" repeat
        assertEquals(RoadAlert.Stage.EARLY, alerts.single().second.stage)
        assertEquals(60, alerts.single().second.hazard.speedLimitKmh)
        assertEquals(58, alerts.single().second.speedKmh) // 16 m/s
        assertTrue(!alerts.single().second.overLimit)
    }

    @Test fun parkedOrInaccurateFixesNeverAlert() {
        val engine = RoadAlertEngine(listOf(pothole(100.0)))
        assertTrue(engine.driveEast(speed = 1f, toMetres = 99.0).isEmpty())
        val inaccurate = RoadAlertEngine(listOf(pothole(400.0)))
        assertTrue(inaccurate.driveEast(speed = 14f, accuracy = 60f, toMetres = 500.0).isEmpty())
        val unknownAccuracy = RoadAlertEngine(listOf(pothole(400.0)))
        assertTrue(unknownAccuracy.driveEast(speed = 14f, accuracy = null, toMetres = 500.0).isEmpty())
    }

    @Test fun courseFromMovementWhenGpsHasNoBearing() {
        val engine = RoadAlertEngine(listOf(pothole(800.0)))
        val alerts = engine.driveEast(speed = 14f, heading = null, toMetres = 900.0)
        assertTrue(alerts.isNotEmpty())
        assertEquals(RoadAlert.Stage.EARLY, alerts.first().second.stage)
    }

    @Test fun nearestHazardWinsAndEachIsAnnouncedOncePerApproach() {
        val engine = RoadAlertEngine(listOf(pothole(600.0, "a"), pothole(650.0, "b")))
        val alerts = engine.driveEast(speed = 14f, toMetres = 700.0)
        val ids = alerts.map { it.second.hazard.id to it.second.stage }
        assertEquals(listOf("a" to RoadAlert.Stage.EARLY, "b" to RoadAlert.Stage.EARLY,
            "a" to RoadAlert.Stage.NEAR, "b" to RoadAlert.Stage.NEAR), ids)
    }

    @Test fun passedHazardIsAnnouncedAgainOnTheNextLap() {
        val engine = RoadAlertEngine(listOf(pothole(500.0)))
        val first = engine.driveEast(speed = 14f, toMetres = 700.0)
        // Drive away far enough, then approach the same spot again from the start.
        engine.onFix(lat0, east(2_500.0), 5f, 14f, 90f, 60_000)
        val second = engine.driveEast(speed = 14f, toMetres = 700.0, startMs = 120_000)
        assertEquals(first.map { it.second.stage }, second.map { it.second.stage })
    }

    @Test fun invalidHazardsAreDropped() {
        val engine = RoadAlertEngine(listOf(
            RoadHazard("nan", RoadHazardKind.POTHOLE, Double.NaN, lng0),
            RoadHazard("far", RoadHazardKind.POTHOLE, 95.0, lng0),
            pothole(10.0, "ok"), pothole(20.0, "ok")
        ))
        assertEquals(1, engine.hazardCount)
        assertNull(engine.onFix(Double.NaN, lng0, 5f, 10f, 90f, 0))
    }

    @Test fun speechRoundsDistances() {
        assertEquals(50, RoadAlertEngine.roundForSpeech(30.0))
        assertEquals(200, RoadAlertEngine.roundForSpeech(190.0))
        assertEquals(300, RoadAlertEngine.roundForSpeech(320.0))
        assertEquals(500, RoadAlertEngine.roundForSpeech(497.0))
    }

    @Test fun phrasesInEveryLanguage() {
        val pothole = RoadAlert(pothole(500.0), 500, RoadAlert.Stage.EARLY, 0)
        assertEquals("500 metrdan keyin chuqur. Sekinlang.", RoadAlertPhrases.text(pothole, "uz"))
        assertEquals("Pothole in 500 metres. Slow down.", RoadAlertPhrases.text(pothole, "en"))
        assertEquals("Через 500 метров яма. Снизьте скорость.", RoadAlertPhrases.text(pothole, "ru"))
        val camera = RoadAlert(
            RoadHazard("c", RoadHazardKind.SPEED_CAMERA, lat0, lng0, 90f, 70), 600,
            RoadAlert.Stage.EARLY, 0
        )
        assertEquals("600 metrdan keyin tezlik kamerasi. Chegara 70.", RoadAlertPhrases.text(camera, "uz"))
        val belt = camera.copy(hazard = camera.hazard.copy(kind = RoadHazardKind.SEATBELT_CAMERA))
        assertEquals("600 metrdan keyin xavfsizlik kamari kamerasi. Kamarni taqing.",
            RoadAlertPhrases.text(belt, "uz"))
        RoadHazardKind.entries.forEach { kind ->
            val alert = camera.copy(hazard = camera.hazard.copy(kind = kind))
            listOf("uz", "en", "ru").forEach { assertTrue(RoadAlertPhrases.text(alert, it).isNotBlank()) }
        }
        val fast = camera.copy(speedKmh = 85)
        assertEquals("600 metrdan keyin tezlik kamerasi. Chegara 70. Tezlikni kamaytiring.",
            RoadAlertPhrases.text(fast, "uz"))
        assertEquals("Speed camera in 600 metres. Limit 70. Slow down.", RoadAlertPhrases.text(fast, "en"))
        // Within the tolerance, and for potholes, there is no extra reminder.
        assertEquals("600 metrdan keyin tezlik kamerasi. Chegara 70.",
            RoadAlertPhrases.text(camera.copy(speedKmh = 72), "uz"))
        assertEquals("500 metrdan keyin chuqur. Sekinlang.",
            RoadAlertPhrases.text(pothole.copy(speedKmh = 120), "uz"))
        assertEquals(RoadHazardKind.SEATBELT_CAMERA, RoadHazardKind.fromWire("seatbelt_camera"))
        assertNull(RoadHazardKind.fromWire("unknown"))
    }
}
