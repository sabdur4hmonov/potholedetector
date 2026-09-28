"""Production wiring guards; behavioral budgets are exercised by JVM/JS tests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVE = ROOT / 'android-app/android/app/src/main/java/dev/aiengg/potholereporter/drive'
transport = (DRIVE / 'NativeInferenceTransport.kt').read_text(encoding='utf-8')
reader = (DRIVE / 'NativeBoundedSseReader.kt').read_text(encoding='utf-8')
syntax = (DRIVE / 'NativeInferenceJsonSyntax.kt').read_text(encoding='utf-8')
js = (ROOT / 'static/standalone.js').read_text(encoding='utf-8')
gateway = (DRIVE.parent / 'security/NativeCredentialPlugin.kt').read_text(encoding='utf-8')
checks = 0


def check(name, condition):
    global checks
    assert condition, name
    checks += 1
    print('PASS ' + name)


check('native attacker-controlled inference uses byte framing, never readLine/charStream',
      'NativeBoundedSseReader(sseLimits).read(responseBody.byteStream(), call::isCanceled)' in transport
      and all(term not in transport + reader for term in ('readLine(', 'charStream(', 'readText(')))
check('native buffers are fixed and capacity is checked before writing',
      'ByteArray(4 * 1024)' in reader and 'ByteArray(limits.lineBytes)' in reader
      and 'ByteArray(limits.eventBytes)' in reader
      and reader.index('if (lineSize >= limits.lineBytes)') < reader.index('line[lineSize++] = byte')
      and reader.index('size.size > limits.eventBytes - eventSize - separator') < reader.index('size.copyInto'))
check('native transport-byte accounting precedes parsing with at most one overflow byte',
      'minOf(chunk.size, limits.responseBytes - total + 1)' in reader
      and reader.index('count > limits.responseBytes - total') < reader.index('total += count'))
check('native strict UTF-8, event count, monotonic processing deadline and input closure',
      'CodingErrorAction.REPORT' in reader and 'eventCount >= limits.events' in reader
      and 'nanoTime() - started >= deadlineNs' in reader and 'input.use' in reader)
check('native whole-call deadline and unconditional transport cleanup',
      'call.timeout().timeout(sseLimits.deadlineMs, TimeUnit.MILLISECONDS)' in transport
      and '.callTimeout(35, TimeUnit.SECONDS)' in transport
      and 'call.cancel()\n            responseBody.close()' in transport)
check('strict depth-bounded native JSON grammar runs before Android JSON allocation',
      'MAX_DEPTH = 32' in syntax and 'depth >= MAX_DEPTH' in syntax
      and transport.index('NativeInferenceJsonSyntax.requireObject(payload)') < transport.index('JSONTokener(payload)'))
check('retained native output cap and detection/repair token caps are unchanged',
      'MAX_UTF8_BYTES = 64 * 1024' in transport
      and 'MAX_OUTPUT_TOKENS = 1_536' in (DRIVE / 'NativeDetectionContract.kt').read_text()
      and 'MAX_OUTPUT_TOKENS = 768' in (DRIVE / 'NativeRepairContract.kt').read_text())
block = js[js.index('  // SEC-005:'):js.index('  // Reconstructed from the closed fields')]
check('equivalent browser byte/line/event/count/deadline limits',
      all(term in block for term in ('responseBytes: 64 * 1024', 'lineBytes: 32 * 1024',
                                    'eventBytes: 48 * 1024', 'events: 512', 'deadlineMs: 35000')))
check('browser byte and line checks precede accumulation',
      block.index('chunk.byteLength > state.limits.responseBytes - state.bytes') < block.index('state.bytes += chunk.byteLength')
      and block.index('state.lineSize >= state.limits.lineBytes') < block.index('state.line[state.lineSize++] = byte'))
check('browser decoder and JSON allocation are strict and bounded',
      'TextDecoder("utf-8", { fatal: true })' in block
      and block.index('if (++depth > 32)') < block.index('JSON.parse(text)')
      and 'state.events >= state.limits.events' in block)
check('browser absolute deadline cannot be extended by incoming chunks',
      'performance.now() - started >= limits.deadlineMs' in block
      and 'setTimeout(() => { timedOut = true; controller.abort(); }, limits.deadlineMs)' in block
      and '__rearm' not in block)
check('browser reader cancellation, release and late-header cleanup are wired',
      'context.reader.cancel()' in block and 'context.reader.releaseLock()' in block
      and 'Promise.race([context.reader.read(), context.cancelled])' in block
      and 'pending.then(res =>' in block and 'res.__cancel()' in block)
check('browser full-text fallback is restricted to prebounded native envelope',
      block.index('if (!NATIVE) throw inferenceSafetyError()') < block.index('res.text()')
      and block.index('inferenceUtf8Size(text, context.limits.responseBytes, true)') < block.index('encode(text)')
      and 'MAX_RESPONSE_BYTES = 1024 * 1024' in gateway and '.callTimeout(35, TimeUnit.SECONDS)' in gateway)
json_path = js[js.index('  async function oai(body)'):js.index('  async function oai(body)') + 1800]
check('nonstream inference JSON uses the same bounded byte reader',
      'readInferenceChunks(res, context' in json_path and 'new Uint8Array(context.limits.responseBytes)' in json_path
      and 'res.json()' not in json_path and 'parseInferenceJson' in json_path)
check('all shipped standalone sources match canonical source', all(
    (ROOT / path).read_bytes() == (ROOT / 'static/standalone.js').read_bytes()
    for path in ('docs/standalone.js', 'android-app/www/standalone.js',
                 'android-app/android/app/src/main/assets/public/standalone.js')))
print(f'SEC005 INFERENCE CONTRACT PASS ({checks} checks)')
