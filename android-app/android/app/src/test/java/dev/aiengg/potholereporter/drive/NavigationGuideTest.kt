package dev.aiengg.potholereporter.drive

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.cos

class NavigationGuideTest {
    private val lat0 = 41.3111
    private val lng0 = 69.2797
    private val perLng = 111_320.0 * cos(Math.toRadians(lat0))

    private fun at(eastM: Double, northM: Double) = NavPoint(lat0 + northM / 111_320.0, lng0 + eastM / perLng)

    /** 1.5 km east, then a left turn and 1 km north. */
    private fun lRoute(): NavigationGuide {
        val line = (0..150).map { at(it * 10.0, 0.0) } + (1..100).map { at(1500.0, it * 10.0) }
        val corner = at(1500.0, 0.0)
        val end = at(1500.0, 1000.0)
        return NavigationGuide(line, listOf(
            NavManeuver(lng0.let { lat0 }, lng0, "depart"),
            NavManeuver(corner.lat, corner.lng, "new name", "straight", name = "Same street"),
            NavManeuver(corner.lat, corner.lng, "turn", "left", name = "Amir Temur"),
            NavManeuver(end.lat, end.lng, "arrive")
        ))
    }

    /** Drives the route at [speed] m/s, one fix per second, returning (metres along, event). */
    private fun NavigationGuide.drive(speed: Double, offsetNorthM: (Double) -> Double = { 0.0 }): List<Pair<Double, NavEvent>> {
        val events = mutableListOf<Pair<Double, NavEvent>>()
        var s = 0.0
        while (s <= 2_600.0) {
            val p = if (s <= 1500) at(s, offsetNorthM(s)) else at(1500.0 + offsetNorthM(s), s - 1500)
            onFix(p.lat, p.lng, 5f, speed.toFloat())?.let { events += s to it }
            s += speed
        }
        return events
    }

    @Test fun announcesStartFarNearNowAndArrival() {
        val events = lRoute().drive(14.0)
        val kinds = events.map { (_, e) -> e.kind to e.stage }
        assertEquals(listOf(
            NavEvent.Kind.START to null,
            NavEvent.Kind.INSTRUCTION to NavEvent.Stage.FAR,
            NavEvent.Kind.INSTRUCTION to NavEvent.Stage.NEAR,
            NavEvent.Kind.INSTRUCTION to NavEvent.Stage.NOW,
            NavEvent.Kind.INSTRUCTION to NavEvent.Stage.FAR,
            NavEvent.Kind.INSTRUCTION to NavEvent.Stage.NEAR,
            NavEvent.Kind.ARRIVED to null
        ), kinds)
        // The left turn is announced about 420 m, 140 m and 40 m before the corner.
        val turn = events.filter { it.second.maneuver?.type == "turn" && it.second.kind == NavEvent.Kind.INSTRUCTION }
        assertTrue(1500 - turn[0].first in 406.0..420.0)
        assertTrue(1500 - turn[1].first in 126.0..140.0)
        assertTrue(1500 - turn[2].first in 26.0..40.0)
        assertEquals("Amir Temur", turn[0].second.maneuver!!.name)
        assertTrue(events.last().first >= 2470.0)
    }

    @Test fun speakableUzbekRussianAndEnglishWording() {
        val events = lRoute().drive(14.0).map { it.second }
        assertEquals("Marshrut boshlandi. 1,5 kilometr to'g'riga yuring.", NavigationPhrases.text(events[0], "uz"))
        assertEquals("400 metrdan keyin chapga buriling.", NavigationPhrases.text(events[1], "uz"))
        assertEquals("Chapga buriling.", NavigationPhrases.text(events[3], "uz"))
        assertEquals("400 metrdan keyin manzilga yetasiz.", NavigationPhrases.text(events[4], "uz"))
        assertEquals("Manzilga yetib keldingiz.", NavigationPhrases.text(events.last(), "uz"))
        assertEquals("Через 400 метров поверните налево.", NavigationPhrases.text(events[1], "ru"))
        assertEquals("In 400 metres, turn left.", NavigationPhrases.text(events[1], "en"))
    }

    @Test fun progressCountsDownTheRemainingDistance() {
        val guide = lRoute()
        val p = at(500.0, 0.0)
        guide.onFix(p.lat, p.lng, 5f, 14f)
        val progress = guide.progress()
        assertEquals("turn", progress.nextManeuver!!.type)
        assertTrue(progress.distanceToNextM!! in 995..1005)
        assertTrue(progress.remainingM in 1995..2005)
        assertFalse(progress.offRoute)
    }

    @Test fun leavingTheRouteIsReportedOnceAfterThreeFixes() {
        val guide = lRoute()
        // East along the route for 600 m, then straight south away from it for 1 km.
        val track = (0..60).map { at(it * 10.0, 0.0) } + (1..100).map { at(600.0, -it * 10.0) }
        val events = track.mapNotNull { p -> guide.onFix(p.lat, p.lng, 5f, 10f)?.let { 0.0 to it } }
        val off = events.filter { it.second.kind == NavEvent.Kind.OFF_ROUTE }
        assertEquals(1, off.size)
        assertTrue(guide.progress().offRoute)
        assertTrue(events.none { it.second.kind == NavEvent.Kind.ARRIVED })
    }

    @Test fun inaccurateFixesAreIgnored() {
        val guide = lRoute()
        val p = at(100.0, 0.0)
        assertNull(guide.onFix(p.lat, p.lng, 80f, 14f))
        assertNull(guide.onFix(p.lat, p.lng, null, 14f))
        assertNull(guide.onFix(Double.NaN, p.lng, 5f, 14f))
    }

    @Test fun roundaboutsForksAndNoiseSteps() {
        assertEquals("aylanma yo'lda 2-chiqishga chiqing",
            NavigationPhrases.action(NavManeuver(0.0, 0.0, "roundabout", "right", exit = 2), "uz"))
        assertEquals("ayriliqda o'ngga yuring", NavigationPhrases.action(NavManeuver(0.0, 0.0, "fork", "slight right"), "uz"))
        assertEquals("biroz chapga buriling", NavigationPhrases.action(NavManeuver(0.0, 0.0, "turn", "slight left"), "uz"))
        assertEquals("orqaga qayriling", NavigationPhrases.action(NavManeuver(0.0, 0.0, "turn", "uturn"), "uz"))
        assertFalse(NavigationGuide.isSpoken(NavManeuver(0.0, 0.0, "depart")))
        assertFalse(NavigationGuide.isSpoken(NavManeuver(0.0, 0.0, "new name", "straight")))
        assertTrue(NavigationGuide.isSpoken(NavManeuver(0.0, 0.0, "continue", "left")))
        assertEquals("800 metr", NavigationPhrases.distanceWords(790, "uz"))
        assertEquals("2 kilometr", NavigationPhrases.distanceWords(2_040, "uz"))
        assertEquals("2.5 kilometres", NavigationPhrases.distanceWords(2_480, "en"))
    }

    @Test fun aRouteWithoutAnArrivalStepStillEnds() {
        val line = (0..60).map { at(it * 10.0, 0.0) }
        val guide = NavigationGuide(line, emptyList())
        var arrived = false
        var s = 0.0
        while (s <= 620.0) {
            val p = at(s, 0.0)
            if (guide.onFix(p.lat, p.lng, 5f, 10f)?.kind == NavEvent.Kind.ARRIVED) arrived = true
            s += 10.0
        }
        assertTrue(arrived)
        assertTrue(guide.progress().arrived)
    }
}
