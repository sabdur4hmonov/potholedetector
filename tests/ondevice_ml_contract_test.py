"""Contract checks that cross Python, native Drive, and export boundaries."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
native = root / 'android-app/android/app/src/main/java/dev/aiengg/potholereporter'
def read(path):
    return path.read_text(encoding='utf-8')

detector = read(native / 'drive/NativePotholeDetector.kt')
service = read(native / 'drive/DriveForegroundService.kt')
sensor = read(native / 'drive/NativeSensorDrive.kt')
assert all(x not in detector + sensor for x in ('OkHttp', 'HttpURLConnection', 'java.net.', 'NativeAiUsageBudget'))
assert detector.index('verifyModel(parsed, bytes)') < detector.index('env.createSession(bytes, options)')
assert 'env.setTelemetry(false)' in detector and 'busy.compareAndSet(false, true)' in detector
assert 'potholeDetector?.detect(item.burstFrames.map { it.bitmap })' in service
assert 'potholeDetector?.close()' in service and 'inferenceMeanMs' in service and 'inferenceMeanMs' in sensor
assert 'NativePotholeFusion.matches' in sensor and 'NativeDuplicateReportOwnership.merge' in sensor
pins = json.loads(read(root / 'ml/pins.json'))
gradle = read(root / 'android-app/android/app/build.gradle')
assert f'com.microsoft.onnxruntime:onnxruntime-android:{pins["onnxruntime"]}' in gradle
notebook = json.loads(read(root / 'ml/train_pothole_yolox.ipynb'))
for cell in notebook['cells']:
    if cell['cell_type'] == 'code':
        compile(''.join(cell['source']), 'Colab cell', 'exec')
print('ON-DEVICE ML CONTRACT PASS (8 checks including executable notebook cell syntax)')
