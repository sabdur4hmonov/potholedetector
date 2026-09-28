#!/usr/bin/env python3
"""Source contracts supplement executable JVM transport authorization tests."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / 'android-app/android/app/src/main/java/dev/aiengg/potholereporter'
DRIVE = JAVA / 'drive'
policy = (DRIVE / 'NativeRtspTransportPolicy.kt').read_text(encoding='utf-8')
source = (DRIVE / 'NativeFrameSource.kt').read_text(encoding='utf-8')
rtsp = (DRIVE / 'NativeRtspFrameSource.kt').read_text(encoding='utf-8')
plugin = (JAVA / 'plugin/DriveModePlugin.kt').read_text(encoding='utf-8')
service = (DRIVE / 'DriveForegroundService.kt').read_text(encoding='utf-8')
web = (ROOT / 'static/index.html').read_text(encoding='utf-8')
checks = 0

def check(label, condition):
    global checks
    assert condition, label
    checks += 1
    print('PASS ' + label)

check('native capability cannot be enabled through bridge arguments',
      'private const val VERIFIED_SECURE_TRANSPORT_SUPPORTED = false' in policy)
check('plaintext rejection precedes capability check/client callback',
      policy.index('validateSecureEndpoint(value)') < policy.index('if (!VERIFIED_SECURE_TRANSPORT_SUPPORTED)') < policy.index('return connect(endpoint)')
      and 'uri.scheme.equals("rtsp", ignoreCase = true)' in policy)
check('production config uses sole native endpoint boundary',
      'NativeRtspTransportPolicy.requireProductionEndpoint(rtspValue)' in source
      and 'private fun validatedRtspUrl' not in source)
check('direct source construction rejects before Android resources',
      rtsp.index('NativeRtspTransportPolicy.requireProductionEndpoint(rtspUrl)') < rtsp.index('private val mainHandler')
      < rtsp.index('private val decodeThread') < rtsp.index('private val mediaLedger'))
gate = rtsp.index('val mediaSource = NativeRtspTransportPolicy.withProductionEndpoint(rtspUrl)')
end = rtsp.index('\n        }', gate)
factory = rtsp[gate:end]
check('only Media3 factory and route factory are inside native gate',
      rtsp.count('RtspMediaSource.Factory()') == 1
      and 'RtspMediaSource.Factory()' in factory
      and 'preferredWifiSocketFactory()?.let' in factory
      and 'MediaItem.fromUri(verifiedEndpoint)' in factory)
check('RTSP wire debug logging remains disabled', '.setDebugLoggingEnabled(false)' in factory)
check('bridge and foreground intent independently use native source config',
      'NativeFrameSourceConfig.create(' in plugin and 'NativeFrameSourceConfig.create(' in service
      and 'secretStore.readForNativeUse(NativeSecret.DASHCAM_RTSP)' in plugin
      and 'call.getString("dashcamRtspUrl")' not in plugin)
check('parser errors discard credential-bearing causes',
      'catch (_: Exception)' in policy and 'throw IllegalArgumentException(INVALID_ENDPOINT)' in policy
      and not re.search(r'(?:Log\.|println\(|print\(|Socket\(|InetAddress|SocketFactory)', re.sub(r'//[^\n]*', '', policy)))
check('unsafe endpoint syntax explicitly covered',
      all(x in policy for x in ['uri.rawAuthority', 'uri.rawUserInfo', 'uri.fragment', 'uri.port in 1..65535', 'authority.count', 'uri.isOpaque']))
production = '\n'.join(p.read_text(encoding='utf-8') for p in JAVA.rglob('*') if p.suffix in ('.kt', '.java'))
check('no permissive TLS or plaintext downgrade implementation',
      not re.search(r'trustAll|TrustAll|ALLOW_ALL_HOSTNAME_VERIFIER|setHostnameVerifier|checkServerTrusted|cleartextTrafficPermitted|replace\([^\n]*rtsps[^\n]*rtsp', production))
check('no alternate RTSP client introduced', production.count('RtspMediaSource.Factory()') == 1)
check('transport policy cannot persist or return credentials to WebView',
      not any(x in policy for x in ['SharedPreferences', 'File(', 'localStorage', 'PluginCall', 'JSObject', 'Log.']))
save = web[web.index('$("setSave").onclick'):web.index('$("setSave").onclick') + 5500]
check('settings reject dashcam before storing credentials',
      save.index('selectedCaptureSource === DASHCAM_CAPTURE_SOURCE') < save.index('CredentialBroker.storeCredentials')
      and 'dashcamRtspUrl:' not in save)
check('unsupported source and endpoint entry are disabled',
      '$("dashcamOption").disabled = true' in web and '$("setDashcamRtspUrl").disabled = true' in web)
check('browser does not accept unsupported endpoint',
      re.search(r'function validateDashcamRtspUrl\(rawValue\)\s*\{[^}]*return null;', web) is not None)
start = web[web.index('  const captureConfig = savedDriveCaptureConfig();'):]
check('saved dashcam source rejected before requesting permission or native start',
      start.index('captureConfig.captureSource === DASHCAM_CAPTURE_SOURCE') < start.index('requestNativeDrivePermissions')
      and 'never reconnect or silently switch source' in start)
for folder in ['docs', 'android-app/www', 'android-app/android/app/src/main/assets/public']:
    check('WebView mirror matches ' + folder, (ROOT / folder / 'index.html').read_bytes() == (ROOT / 'static/index.html').read_bytes())
print(f'SEC003 TRANSPORT CONTRACT PASS ({checks} checks)')

