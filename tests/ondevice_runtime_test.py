# -*- coding: utf-8 -*-
"""ONDEVICE-002 wiring contract: the LiteRT runtime is present but dormant. It loads only a
bundled model whose card passes the shared contract and whose tensors match it, feeds it
complete frames, and only annotates sensor shock reports. No model ships in the repository."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "android-app/android/app"
DRIVE = APP / "src/main/java/dev/aiengg/potholereporter/drive"


def require(label, condition):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        raise AssertionError(label)


runtime = (DRIVE / "OnDevicePotholeModel.kt").read_text()
sensor = (DRIVE / "SensorDriveDetector.kt").read_text()
service = (DRIVE / "DriveForegroundService.kt").read_text()
gradle = (APP / "build.gradle").read_text()
variables = (ROOT / "android-app/android/variables.gradle").read_text()

require("one pinned LiteRT dependency, stored uncompressed for memory mapping",
        'implementation "com.google.ai.edge.litert:litert:$litertVersion"' in gradle
        and re.search(r"litertVersion = '\d+\.\d+\.\d+'", variables)
        and "noCompress 'tflite'" in gradle
        and "tensorflow-lite" not in gradle)
require("the model is loaded only through the shared card contract and from app assets",
        "OnDeviceModelSpec::parse" in runtime and 'CARD_ASSET = "models/pothole_detector.json"' in runtime
        and "MODEL_DIR + spec.modelFile" in runtime and "assets.openFd(asset)" in runtime)
require("nothing is downloaded or sent",
        all(term not in runtime for term in ("okhttp", "java.net", "URL(", "HttpURLConnection")))
require("card and model sizes are bounded and loading never throws",
        "MAX_CARD_BYTES" in runtime and "MAX_MODEL_BYTES" in runtime
        and "catch (error: Throwable)" in runtime)
require("tensors must be exactly one whole frame [1, h, w, 3] float32 and one probability",
        "intArrayOf(1, spec.inputHeight, spec.inputWidth, 3)" in runtime
        and "DataType.FLOAT32" in runtime and "numElements() == 1" in runtime
        and "inputTensorCount != 1" in runtime)
require("every burst frame is scored and the shared burst rule decides",
        "m.decide(burstFrames.map { it.bitmap })" in sensor
        and "OnDeviceDetectorContract.decideBurst(scores, spec)" in runtime
        and "score(it) ?: Double.NaN" in runtime)
require("a felt shock is always reported first; the camera model only annotates it",
        "OnDeviceDetectorContract.reviewNote(frame.modelVerdict, model?.spec)" in sensor
        and sensor.index("val matched = nextMatchedBump()") < sensor.index("ONDEVICE-003")
        and "createReport(matched.first, matched.second, driveId, onEvidenceSaved)" in sensor)
require("ONDEVICE-003: a camera-only report needs an ACCEPT verdict, movement and spacing",
        "verdict?.decision == OnDeviceBurstDecision.ACCEPT" in sensor
        and "modelReportAllowed(current)" in sensor
        and "MODEL_MIN_SPEED_MPS = 4f" in sensor and "MODEL_REPORT_MIN_GAP_MS = 3_000L" in sensor
        and "MODEL_REPORT_MIN_SPACING_M = 25.0" in sensor
        and "createReport(null, current, driveId, onEvidenceSaved)" in sensor)
require("camera-only reports are marked as unverified on-device candidates",
        'ONDEVICE_CAPTURE_SOURCE = "drive_ondevice"' in sensor and 'ONDEVICE_DECISION = "ondevice_candidate"' in sensor
        and 'ONDEVICE_DAMAGE_TYPE = "pothole_candidate"' in sensor
        and "isReportable = 0" in sensor and "isPothole = 0" in sensor)
require("the service loads the model only for the AI-free sensor mode, and the detector closes it",
        "model = OnDevicePotholeModel.load(applicationContext)" in service
        and "model?.close()" in sensor)
models = APP / "src/main/assets/models"
require("no model is bundled in the repository",
        not models.exists() or not any(models.iterdir()))

print("on-device runtime checks passed")
