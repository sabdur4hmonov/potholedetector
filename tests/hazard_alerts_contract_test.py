"""HAZARD-ALERT-001 offline output, source-of-truth and lifecycle boundaries."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'android-app/android/app/src/main/java/dev/aiengg/potholereporter'
def read(path): return path.read_text(encoding='utf-8')
service = read(BASE / 'drive/DriveForegroundService.kt')
alerter = read(BASE / 'drive/NativeHazardAlerter.kt')
policy = read(BASE / 'drive/NativeHazardAlertPolicy.kt')
store = read(BASE / 'drive/NativeHazardStore.kt')
plugin = read(BASE / 'plugin/DriveModePlugin.kt')
web = read(ROOT / 'static/index.html')
client = read(ROOT / 'static/standalone.js')
checks = 0
def check(value, label):
    global checks
    assert value, label
    checks += 1
check('import android.' not in policy and 'import android.' not in store, 'geometry/storage policy is JVM-testable')
check(all(x not in alerter + policy + store for x in ['OkHttp', 'HttpURLConnection', 'java.net.', 'NativeAiUsageBudget', 'NativeInferenceEngine']), 'warnings have no detector/budget/network client')
check('!it.isNetworkConnectionRequired' in alerter and 'setVoice(voice)' in alerter, 'only installed offline TTS voices')
check('listOf("uz-UZ", "ru-RU", "en")' in alerter, 'Uzbek/Russian/English fallback')
check(all(x in alerter for x in ['USAGE_ASSISTANCE_NAVIGATION_GUIDANCE', 'AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK', 'abandonAudioFocusRequest', 'onDone', 'finishAudio']), 'audio focus is transient and released')
check(all(x in alerter for x in ['ToneGenerator', 'vibrator?.vibrate', 'tts?.speak', 'tts?.shutdown()', 'tone?.release()', 'vibrator?.cancel()']), 'real native output with teardown')
check('hazardAlerter?.onFix(fix)' in service and 'if (sessionRunning && !isPaused && !isStopping)' in service, 'service GPS drives alerts independently of the page/camera model')
check(service.count('hazardAlerter?.close()') >= 3 and 'hazardAlerter?.silence()' in service, 'new drive/pause/stop/destroy release output')
check('hazardAlerter?.lastAlert' in service and 'warningStatus' in service and plugin.count('put("lastHazardAlert"') == 2, 'notification and all HUD status responses include last alert')
check('addCommittedHazard(id, "unconfirmed")' in service and 'addCommittedHazard(it, "confirmed")' in service and 'row.debugCapture' in service, 'same-drive native reports update immediately and exclude debug')
addition = service[service.index('private fun addCommittedHazard'):service.index('private fun publish')]
check('NativeMediaFilesystemMutation.mutex.withLock' in addition and 'row.syncedToWeb' in addition and '!row.lat.isFinite()' in addition, 'delayed native additions cannot resurrect acknowledged/deleted reports or invalid coordinates')
check('acknowledgedIds' in service and 'it.syncedToWeb' in plugin and 'live.keys.removeAll' in alerter, 'web snapshot overrides acknowledged native overlays')
check('NativeHazardStore.parse(call.data.toString())' in plugin and 'NativeHazardAlerter.store(context).save(values)' in plugin, 'strict native validation before atomic persistence')
check('it.write(bytes); it.fd.sync()' in store and 'atomicReplace(temporary, file)' in store and 'Os.rename(' in alerter, 'fsynced temp and same-directory atomic rename')
check('MAX_ITEMS = 5_000' in store and 'MAX_BYTES = 1_048_576' in store and '"hazards/hazards-v1.json"' in alerter, 'private bounded snapshot')
check('"hazards"' in read(BASE / 'media/AndroidAppMediaCleanup.kt') and 'check(!nativeClearInProgress && epoch == hazardSnapshotEpoch)' in plugin and 'hazardSnapshotEpoch++' in plugin, 'Delete All registry, writer mutex and stale-request epoch barrier')
check('groupBy' in policy and 'for (rowIndex' in policy and 'PriorityQueue<Check>' in policy, 'spatial candidate filter and bounded deferred rearm checks')
check('hazardSyncTimer = setTimeout' in web and '2_000' in web and 'await syncHazardsNow();\n      const status = await nativePlugin.startDrive' in web, 'debounced updates and snapshot before Drive admission')
check('window.dispatchEvent(new Event' in client and 'const result = await handle(path, opts)' in client and 'reports-cleared' in web, 'only committed mutations publish; wipe cancels queued refresh')
check('condition_status !== "fixed"' in client and '!r.debug_capture' in client and 'Number.isFinite(r.lat)' in client and 'native_report_id' in client, 'web report source includes manual/native identities and exclusions')
check('MAX_LIMIT_MINUTES = 180' in read(BASE / 'drive/DriveSessionLimitPolicy.kt') and 'DEFAULT_LIMIT_MINUTES = 30' in read(BASE / 'drive/DriveSessionLimitPolicy.kt'), 'battery limit extended without removing default/expiry')
print(f'HAZARD ALERTS CONTRACT PASS ({checks} checks)')
