#!/usr/bin/env python3
"""Focused source contracts for the audited remote pack path and Android GET proxy."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'static/standalone.js').read_text(encoding='utf-8')
checks = 0

def function(name):
    match = re.search(r'  (?:async )?function ' + name + r'\(', source)
    assert match, name
    return source[match.start():source.index('\n  }', match.start()) + 4]

def check(name, result):
    global checks
    assert result, name
    checks += 1
    print('PASS ' + name)

reader = function('readBoundedPackBody')
check('status and Content-Length checked before reader and allocation',
      reader.index('!response.ok') < reader.index('declaredPackLength(') < reader.index('response.body.getReader()') < reader.index('new Uint8Array(limit)'))
check('actual bytes checked before buffer copy',
      reader.index('value.byteLength > limit - total') < reader.index('buffer.set(value, total)') < reader.index('total += value.byteLength'))
check('identity declared size independently enforced and EOF checked',
      'value.byteLength > declared - total' in reader and 'total !== declared' in reader and 'total !== expectedBytes' in reader)
check('reader cancellation lock release and buffer cleanup on failure',
      all(x in reader for x in ['finally', 'buffer = null', 'reader.cancel()', 'reader.releaseLock()', 'response.body.cancel()']))
check('stalled reads race cancellation without an unbounded buffer fallback',
      'Promise.race([reader.read(), cancelled])' in reader and 'arrayBuffer(' not in reader and '.text(' not in reader)
check('header values reject duplicates signs decimals overflow and oversize',
      all(x in function('declaredPackLength') for x in ['^[0-9]+$', 'Number.isSafeInteger(length)', 'length > maxBytes']))
download = function('downloadPackResource')
check('deadline signal size and integrity metadata bounded before fetch',
      download.index('expectedBytes > maxBytes') < download.index('fetchStreamingPackResponse(')
      and '^[0-9a-f]{64}$' in download and 'timer = setTimeout(cancel, timeoutMs)' in download)
check('no downloader temporary writes or retries',
      all(x not in download for x in ['putCached', 'localStorage', 'File(', 'while (', 'retry']) and 'return null' in download)
check('only complete validated bytes returned',
      download.index('readBoundedPackBody(') < download.index('await validate(bytes, controller.signal)') < download.index('return { pack, bytes }'))
for fetcher, validator in [('fetchStatePack', 'validateDecodedStatePack'), ('fetchContractPack', 'validateDecodedContractPack'),
                          ('fetchRoadNoticePack', 'validateDecodedRoadNoticePack'), ('fetchRoadAgreementPack', 'validateDecodedRoadAgreementPack'),
                          ('fetchHighwayTile', 'validateHighwayTile')]:
    body = function(fetcher)
    check(fetcher + ' uses bounded downloader and existing integrity validator',
          'downloadPackResource(' in body and 'expectedBytes: resource.bytes' in body
          and 'expectedSha256: resource.sha256' in body and validator + '(resource, bytes' in body
          and 'fetch(' not in body and 'arrayBuffer(' not in body)
    validated = function(validator)
    check(validator + ' preserves exact length SHA-256 before parsing',
          validated.index('bytes.byteLength !== resource.bytes') < validated.index('sha256Bytes(bytes)')
          < validated.index('digest !== resource.sha256') < validated.index('JSON.parse('))
for name in ['getStatePackManifest', 'getHighwayPackManifest', 'fetchOptionalCatalogManifest']:
    body = function(name)
    check(name + ' bounded before UTF-8 decoding and JSON parsing',
          'downloadPackResource(' in body and 'TextDecoder("utf-8", { fatal: true })' in body
          and '.text()' not in body and 'fetch(' not in body)
check('routing contact installation cannot proceed after cancellation',
      'if (signal && signal.aborted) throw packDownloadError();\n    installRoutingAuthorities(pack);' in function('validateRoutingPack'))
native = function('fetchStreamingPackResponse')
check('Android uses original fetch with fixed GET InputStream proxy and no plugin request',
      'method: "GET"' in native and 'window.CapacitorWebFetch.call(window, endpoint, options)' in native
      and 'origin.pathname = "/_capacitor_http_interceptor_"' in native and 'CapacitorHttp.request(' not in native)
bridge = (ROOT / 'android-app/node_modules/@capacitor/android/capacitor/src/main/assets/native-bridge.js').read_text(encoding='utf-8')
server = (ROOT / 'android-app/node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/WebViewLocalServer.java').read_text(encoding='utf-8')
start = server.index('private WebResourceResponse handleCapacitorHttpRequest')
proxy = server[start:server.index('private WebResourceResponse handleLocalRequest', start)]
check('installed Capacitor proxy matches streaming assumption',
      "win.CapacitorWebFetch = window.fetch" in bridge and "'/_capacitor_http_interceptor_'" in bridge
      and 'connection.getInputStream()' in proxy and 'responseHeaders, inputStream)' in proxy
      and not re.search(r'buildResponse|readData|ByteArrayOutputStream|readAllBytes|readBytes', proxy))
check('only remaining arrayBuffer reads are local cache or bounded image header',
      source.count('.arrayBuffer()') == 2
      and 'if (value instanceof Blob) return value.arrayBuffer();' in source
      and 'blob.slice(0, 12).arrayBuffer()' in source)
for folder in ['docs', 'android-app/www', 'android-app/android/app/src/main/assets/public']:
    check(folder + ' exact downloader mirror', (ROOT / folder / 'standalone.js').read_bytes() == (ROOT / 'static/standalone.js').read_bytes())
print(f'SEC004 DOWNLOAD CONTRACT PASS ({checks} checks)')
