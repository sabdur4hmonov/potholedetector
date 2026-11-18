"""SENSOR-DRIVE-001: offline branch, lifecycle, full-frame evidence and bounded logs."""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'android-app/android/app/src/main/java/dev/aiengg/potholereporter'
service = (BASE / 'drive/DriveForegroundService.kt').read_text(encoding='utf-8')
sensor = (BASE / 'drive/NativeSensorDrive.kt').read_text(encoding='utf-8')
plugin = (BASE / 'plugin/DriveModePlugin.kt').read_text(encoding='utf-8')
checks = 0
def check(value, message):
    global checks
    assert value, message
    checks += 1
check('if (detectionMode == "cloud") {\n            inferenceEngine = NativeInferenceEngine' in service,
      'cloud engine construction must remain behind explicit cloud branch')
check(service.count('NativeInferenceEngine(') == 1, 'no second engine construction path')
check('sensorDrive?.closeInput()\n        sensorDrive = null' in service,
      'a reused service cannot carry an old sensor adapter into the next cloud/session mode')
check('if (apiKey.isBlank() || requestedDetectionMode == "sensor") "sensor" else "cloud"' in service,
      'native service independently forces sensor without a key')
check('if (apiKey.isBlank() || call.getString("detectionMode") == "sensor" || call.getBoolean("useOnDevice") == true)' in plugin,
      'plugin independently forces sensor')
check('if (detectionMode == "sensor") {\n            workerJob = lifecycleScope.launch(Dispatchers.IO) { sensorDrive?.consume() }\n        } else startInferenceWorker()' in service,
      'sensor worker cannot enter inference worker')
check(all(x not in sensor for x in ['NativeInferenceEngine', 'NativeAiUsageBudget', 'OkHttp', 'HttpURLConnection', 'reverseGeocode']),
      'sensor adapter/report/log path has no network or AI client/budget')
check('liveAnalyzed = detectionMode == "sensor"' in service, 'crashed sensor bursts cannot become pending AI replay')
check('sensorDrive?.updateRegistration(enabled)' in service and service.count('sensorDrive?.closeInput()') >= 2
      and 'sensorDrive?.unregister()' in service, 'capture/pause/stop/destroy own registration')
check('TYPE_LINEAR_ACCELERATION' in sensor and 'TYPE_GRAVITY' in sensor and 'TYPE_ACCELEROMETER' in sensor
      and 'SENSOR_DELAY_GAME' in sensor, 'paired sensors with accelerometer fallback')
check('rows < 20_000' in sensor and 'Channel<NativeBumpDetector.Peak>(64)' in sensor
      and 'frames.size > 16' in sensor, 'log, queue and frame references bounded')
check('store.saveDetection(image' in sensor and 'NativeReportEvidenceStorage.reserveInferenceCapacity(context)' in sensor
      and 'NativeMediaFilesystemMutation.mutex.withLock' in sensor, 'existing quota and media ownership paths')
check(all(x not in sensor for x in ['createBitmap(', 'cropRect', 'ViewPort', 'setCropAspectRatio']), 'sensor photo uses full persisted primary')
check('NativeSensorDrive.cleanupFrames(context, db, s.id)' in plugin and 'sensorDrive?.cleanup()' in service,
      'normal stop and interrupted-history recovery clean sampling bursts')
check('nearestFix(peak.elapsedMs)' in sensor and 'frame.gpsAccuracy' in sensor, 'event location with burst fallback')
check('decision = "needs_review"' in sensor and 'assessment = "unverified"' in sensor
      and 'isReportable = if (camera != null) 1 else 0, isPothole = if (camera != null) 1 else 0' in sensor
      and 'size = null' in sensor, 'bump-only reports do not invent a pothole verdict')
check('NativeDuplicateReportOwnership.merge' in sensor and 'db.withTransaction' in sensor,
      'same-drive sensor merge preserves evidence and durable outbox')
print(f'SENSOR DRIVE CONTRACT PASS ({checks} checks)')
