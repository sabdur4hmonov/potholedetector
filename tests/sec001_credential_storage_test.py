#!/usr/bin/env python3
"""Static security contract for SEC-001 credential storage and native use."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
ENGINE = (STATIC / "standalone.js").read_text(encoding="utf-8")
STORE = (ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NativeSecretStore.kt").read_text(encoding="utf-8")
BRIDGE = (ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/security/NativeCredentialPlugin.kt").read_text(encoding="utf-8")
DRIVE = (ROOT / "android-app/android/app/src/main/java/dev/aiengg/potholereporter/plugin/DriveModePlugin.kt").read_text(encoding="utf-8")

failures = []


def check(label, condition):
    if condition:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        failures.append(label)


shipped = INDEX + "\n" + ENGINE
check(
    "WebView code never writes OpenAI or RTSP plaintext to local/session storage",
    not re.search(r"(?:localStorage|sessionStorage)\.setItem\(\s*['\"](?:openai_key|dashcam_rtsp_url)['\"]", shipped),
)
check(
    "legacy plaintext is synchronously removed before native migration",
    'takeLegacy("openai_key")' in ENGINE
    and 'takeLegacy("dashcam_rtsp_url")' in ENGINE
    and "localStorage.removeItem(name);" in ENGINE,
)
check(
    "native settings and Drive payloads expose only configured status",
    '$("setKey").value = "";' in INDEX
    and '$("setDashcamRtspUrl").value = "";' in INDEX
    and "apiKey:" not in INDEX
    and "dashcamRtspUrl: captureConfig" not in INDEX,
)
check(
    "Android retention uses a non-exportable AES-GCM Keystore key and ciphertext preferences",
    'const val ANDROID_KEYSTORE = "AndroidKeyStore"' in STORE
    and 'const val TRANSFORMATION = "AES/GCM/NoPadding"' in STORE
    and ".setRandomizedEncryptionRequired(true)" in STORE
    and ".setKeySize(256)" in STORE
    and "SharedPreferencesSecretCiphertextPersistence" in STORE,
)
check(
    "ciphertexts are bound to secret names and corruption fails closed",
    'cipher.updateAAD(aad(secret))' in STORE
    and STORE.count("throw SecretUnavailableException()") >= 3
    and "persistence.remove(secret.persistenceKey)" in STORE,
)
check(
    "native bridge returns booleans and response data but no credential plaintext",
    'put("openAiConfigured"' in BRIDGE
    and 'put("dashcamRtspConfigured"' in BRIDGE
    and 'put("openAiKey"' not in BRIDGE
    and 'put("dashcamRtspUrl"' not in BRIDGE,
)
check(
    "OpenAI authorization is attached only inside the fixed native gateway",
    'const val OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"' in BRIDGE
    and '.header("Authorization", "Bearer $apiKey")' in BRIDGE
    and "Authorization" not in INDEX
    and "call.getString(\"apiKey\")" not in DRIVE,
)
check(
    "bridge restricts origin, visibility, models, request size, and store=false",
    'parsed.scheme == "https" && parsed.host == "localhost"' in BRIDGE
    and "Lifecycle.State.RESUMED" in BRIDGE
    and "MAX_REQUEST_BYTES" in BRIDGE
    and "allowedModels" in BRIDGE
    and 'json.opt("store") == false' in BRIDGE
    and '.followRedirects(false)' in BRIDGE,
)
check(
    "settings clears entered secrets and native authentication error bodies are suppressed",
    INDEX.count('$("setKey").value = "";') >= 4
    and INDEX.count('$("setDashcamRtspUrl").value = "";') >= 4
    and 'val responseText = if (response.isSuccessful)' in BRIDGE
    and '} else ""' in BRIDGE,
)
check(
    "delete/reset removes ciphertext and the Keystore key",
    "keyProvider.delete()" in STORE
    and "persistence.clear()" in STORE
    and "NativeSecretStore.create(context).clearAll()" in DRIVE,
)
check(
    "browser credential is memory-only and reload is not forced after settings save",
    'let browserOpenAiKey = "";' in ENGINE
    and "sessionStorage" not in ENGINE
    and 'localStorage.setItem("openai_key"' not in ENGINE
    and "location.reload(); return;" not in INDEX,
)
check(
    "security implementation contains no credential logging calls",
    not re.search(r"\b(?:Log\.|println\(|print\(|logger\.)", STORE + "\n" + BRIDGE),
)
check(
    "all shipped web mirrors are exact",
    (STATIC / "index.html").read_bytes() == (ROOT / "docs/index.html").read_bytes()
    == (ROOT / "android-app/www/index.html").read_bytes()
    and (STATIC / "standalone.js").read_bytes() == (ROOT / "docs/standalone.js").read_bytes()
    == (ROOT / "android-app/www/standalone.js").read_bytes(),
)

if failures:
    raise SystemExit(f"SEC-001 credential storage test failed: {', '.join(failures)}")
print("SEC-001 credential storage tests passed")
