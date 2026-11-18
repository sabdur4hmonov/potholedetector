"""Contract checks that cross Python, native Drive, and export boundaries."""
import json
import re
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
weights = pins['nano_pretrained']
assert re.fullmatch(r'[0-9a-f]{64}', weights['sha256'])
assert weights['url'].endswith('/0.1.1rc0/yolox_nano.pth') and weights['license'] is None
training = '\n'.join(''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type'] == 'code')
assert 'prepare_initial_weights(pins, weights)' in training and 'load_training_receipt(receipt_path, pins) == receipt' in training
exp = read(root / 'ml/yolox_pothole_exp.py')
assert exp.index('verify_weights(checkpoint') < exp.index('torch.load(checkpoint')
assert 'weights_only=True' in exp and "'backbone.'" in exp and 'strict=False' in exp and 'requires_grad' not in exp
export = read(root / 'ml/evaluate_export.py')
assert 'load_training_receipt(args.checkpoint.with_name' in export and '**init)' in export
ci = read(root / '.github/workflows/ci.yml')
build = read(root / 'tools/build-apk.sh')
abis = ('arm64-v8a', 'armeabi-v7a', 'x86_64')
assert "include 'arm64-v8a', 'armeabi-v7a', 'x86_64'" in gradle and 'universalApk false' in gradle
assert all(f'app-{abi}-debug.apk' in ci and abi in build for abi in abis)
assert 'tools/emulator-smoke.sh apk/app-x86_64-debug.apk' in ci and 'app-debug.apk' not in ci + build
print('ON-DEVICE ML CONTRACT PASS (17 checks including notebook syntax, initialization and ABI routing)')
