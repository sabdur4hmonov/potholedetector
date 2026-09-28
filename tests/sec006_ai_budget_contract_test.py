"""Guard all application paid AI call sites and the authoritative reservation boundary."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'android-app/android/app/src/main/java/dev/aiengg/potholereporter'
def read(path): return path.read_text(encoding='utf-8')
budget=read(BASE/'security/AiUsageBudget.kt')
adapter=read(BASE/'security/NativeAiUsageBudget.kt')
auth=read(BASE/'security/AndroidAiBudgetAuthenticator.kt')
body_guard=read(BASE/'security/NonReplayableAiBody.kt')
bridge=read(BASE/'security/NativeCredentialPlugin.kt')
transport=read(BASE/'drive/NativeInferenceTransport.kt')
engine=read(BASE/'drive/NativeInferenceEngine.kt')
request=read(BASE/'drive/NativeInferenceRequest.kt')
js=read(ROOT/'static/standalone.js')
checks=0
def check(name, condition):
    global checks
    assert condition, name
    checks+=1; print('PASS '+name)

check('one finite native ledger for both paid application paths',
      'MAX_REQUESTS = 32L' in budget and 'MAX_OUTPUT_TOKENS = 32_768L' in budget
      and 'NativeAiUsageBudget.reserve(context, it)' in engine
      and 'NativeAiUsageBudget.reserve(context, request.identity)' in bridge)
check('native bridge reserves before HTTP and handles denial without payloads',
      bridge.index('NativeAiUsageBudget.reserve(context, request.identity)') < bridge.index('http.newCall(httpRequest).execute()')
      and '"AI_USAGE_LIMIT"' in bridge)
gate=transport[transport.index('private inline fun <T> withTrackedCall'):transport.index('private fun httpFailure')]
check('native tracked calls reserve before HTTP creation, missing gate fails closed',
      gate.index('budgetGate(identity)') < gate.index('okHttpClient.newCall(request)')
      and '= { throw AiUsageLimitException() }' in transport
      and transport.count('return withTrackedCall(authorizedRequest(body), AiRequestIdentity(')==2)
check('production transport constructors all install the native gate',
      sum(read(p).count('NativeInferenceTransport(') for p in BASE.rglob('*.kt'))==2
      and 'budgetGate = { NativeAiUsageBudget.reserve(context, it) }' in engine)
check('provider endpoint models and purpose-specific ceilings are authoritative',
      all(x in budget for x in ('identity.provider != "openai"','identity.endpoint != ENDPOINT','identity.model !in models',
                              'identity.outputTokens !in 1..ceiling(identity.purpose)','-> 1536L','-> 768L','-> 512L')))
check('actual paid HTTP endpoints match the identity enforced by the policy',
      'OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"' in bridge
      and 'OAI_URL = "https://api.openai.com/v1/responses"' in transport
      and 'ENDPOINT = "https://api.openai.com/v1/responses"' in budget)
check('native rejects invalid token types and always serializes a native ceiling',
      'rawLimit is Int || rawLimit is Long' in bridge
      and 'AiOutputPolicy.outputLimit(purpose' in bridge and 'json.put("max_output_tokens", limit)' in bridge
      and 'requested !in 1..Int.MAX_VALUE.toLong()' in budget and 'minOf(requested, maximum)' in budget)
check('request count and output checks precede counter increments',
      budget.index('identity.outputTokens > MAX_OUTPUT_TOKENS - state.output') < budget.index('State(state.requests + 1, state.output + identity.outputTokens)')
      and 'state.requests !in 0..MAX_REQUESTS' in budget and 'state.output !in 0..MAX_OUTPUT_TOKENS' in budget)
check('thread and process synchronization encloses durable reservation',
      'synchronized(locks.computeIfAbsent' in budget and 'file.channel.lock().use' in budget
      and 'sync(file)' in budget and 'it.channel.force(true)' in budget)
check('budget remains native private and non-backed-up with directory fsync',
      'noBackupFilesDir.canonicalFile' in adapter and 'Os.fsync(descriptor)' in adapter
      and 'ai_usage_budget' in adapter and 'localStorage' not in adapter+budget)
check('missing/corrupted storage cannot silently refill',
      '!firstRun && (!ledger.isFile' in budget and 'file.length() != RECORD_BYTES' in budget
      and 'authenticator.open(record)' in budget and 'input.readInt() != MAGIC' in budget
      and not re.search(r'\b(?:refund|reset|clear|delete)\s*\(',budget+adapter))
check('usage is permanently charged; provider/client reports cannot refund',
      not re.search(r'\b(?:reportedUsage|refund|reconcile)\s*\(',budget)
      and 'allowedFields' in bridge and 'json.keys().asSequence().all { it in allowedFields }' in bridge
      and '"usage"' not in bridge[bridge.index('private val allowedFields'):bridge.index('fun validate(body')])
check('WebView filesystem tampering/rollback cannot recreate native allowance',
      'firstRun && authenticator.initialized()' in budget
      and '!firstRun && !authenticator.initialized()' in budget
      and budget.index('authenticator.sealNext(payload)') < budget.index('file.write(record)')
      and 'AndroidAiBudgetAuthenticator()' in adapter
      and 'KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")' in auth
      and 'init(Cipher.ENCRYPT_MODE, generate(currentAlias))' in auth and 'AES/GCM/NoPadding' in auth
      and 'GCMParameterSpec(128' in auth and 'updateAAD(aad())' in auth
      and 'pothole_reporter_ai_budget_marker_v1' in auth and 'deleteEntry' not in auth)
check('automatic retransmissions and redirects disabled on both production clients',
      all('.retryOnConnectionFailure(false)' in code and '.followRedirects(false)' in code
          and '.followSslRedirects(false)' in code for code in (bridge,transport)))
check('non-replayable AI bodies also prevent implicit HTTP status follow-ups',
      '.post(NonReplayableAiBody(body))' in transport
      and '.post(NonReplayableAiBody(request.body.toRequestBody(JSON_MEDIA_TYPE)))' in bridge
      and 'override fun isOneShot() = true' in body_guard
      and body_guard.index('written.compareAndSet(false, true)') < body_guard.index('delegate.writeTo(sink)'))
check('native detection/repair output ceilings retained',
      'maxOutputTokens = NativeDetectionContract.MAX_OUTPUT_TOKENS' in request
      and 'maxOutputTokens = NativeRepairContract.MAX_OUTPUT_TOKENS' in request
      and 'put("max_output_tokens", maxOutputTokens)' in request)
check('JS request entrance applies explicit caps and browser paid path fails closed',
      'const bounded = boundedAiRequest(body, stream)' in js
      and 'body: JSON.stringify(bounded)' in js and 'error.code === "AI_USAGE_LIMIT"' in js
      and 'AI inference is available only in the Android app.' in js
      and 'fetchWithTimeout("https://api.openai.com/v1/responses"' not in js)
check('all JS builders/fallbacks and contract match have explicit ceilings',
      '...boundedAiRequest(body, body && body.stream)' in js
      and 'max_output_tokens: schema === REPAIR_SCHEMA ? 768 : 1536' in js
      and js.count('max_output_tokens: 512')==2
      and 'if (e && e.aiUsageLimit) throw e' in js)
check('safe errors and no credential/prompt logging in policy implementations',
      not re.search(r'\b(?:Log\.|println\(|print\(|logger\.)',budget+adapter+bridge+auth)
      and 'catch (_: Exception)' in budget+adapter)
check('known application AI network entrances exhaustively inventoried',
      sum(read(p).count('okHttpClient.newCall(request)') for p in BASE.rglob('*.kt'))==1
      and sum(read(p).count('http.newCall(httpRequest)') for p in BASE.rglob('*.kt'))==1
      and js.count('api.openai.com/v1/models?limit=1')==1)
check('all shipped standalone sources match',all((ROOT/p).read_bytes()==(ROOT/'static/standalone.js').read_bytes()
      for p in ['docs/standalone.js','android-app/www/standalone.js','android-app/android/app/src/main/assets/public/standalone.js']))
print(f'SEC006 AI BUDGET CONTRACT PASS ({checks} checks)')
