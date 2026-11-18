#!/usr/bin/env bash
# Build the APK and refuse to hand back one that does not contain the current source.
#
# Gradle packages android/app/src/main/assets/public, which is a COPY made by
# "cap copy". Editing static/ or www/ and running gradle alone produces a stale APK
# that looks fine and is missing the change you just made. That has shipped once.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
APK_DIR=android-app/android/app/build/outputs/apk/debug
ABIS=(arm64-v8a armeabi-v7a x86_64)
WEB_FILES=(standalone.js index.html hazard-model.js trip-stats.js)

echo "1/4 mirroring static/ into www/"
for f in "${WEB_FILES[@]}"; do cp "static/$f" "android-app/www/$f"; done

echo "2/4 syncing www into the android assets gradle actually packages"
(cd android-app && npx cap copy android >/dev/null)

echo "3/4 building"
(cd android-app/android && ./gradlew --offline assembleDebug -q)

echo "4/4 verifying the APK contains this source"
fail=0
same() {  # a file inside the APK must be byte-identical to the source
  if diff -q <(unzip -p "$APK" "assets/public/$1") "android-app/www/$1" >/dev/null; then
    echo "  ok   $1 matches source"
  else
    echo "  FAIL $1 in the APK differs from android-app/www/$1"; fail=1
  fi
}
for abi in "${ABIS[@]}"; do
  APK="$APK_DIR/app-$abi-debug.apk"
  [ -s "$APK" ] || { echo "FAIL: gradle produced no $abi APK"; exit 1; }
  for f in "${WEB_FILES[@]}"; do same "$f"; done
  n=$(unzip -p "$APK" assets/public/standalone.js | grep -c 'sk-proj\|sk-[A-Za-z0-9]\{20\}' || true)
  [ "$n" = "0" ] && echo "  ok   no API key baked in" || { echo "  FAIL an API key is in $APK"; fail=1; }
  printf 'APK %s bytes  %s\n' "$(wc -c < "$APK")" "$ROOT/$APK"
done

[ "$fail" = "0" ] || { echo "APK REJECTED"; exit 1; }
