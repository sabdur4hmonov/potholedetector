const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/standalone.js'), 'utf8');
const helpers = source.slice(source.indexOf('  function aiUsageLimitError()'), source.indexOf('  // Detection is a classification job'));
const defaults = source.slice(source.indexOf('  const withSpeedDefaults ='), source.indexOf('  // Fatal means'));
const sandbox = { ALLOWED_MODELS: new Set(['gpt-5-mini', 'gpt-5.6']) };
vm.createContext(sandbox); vm.runInContext(helpers + defaults + '\nglobalThis.defaults = withSpeedDefaults;', sandbox);
let checks = 0;
const body = purpose => ({ model: 'gpt-5-mini', input: 'synthetic', text: { format: { name: purpose } } });
for (const [purpose, ceiling] of [['pothole_binary_assessment',1536],['road_repair_assessment',768],
  ['road_repair_verification',768],['tender_match',512],['general',512]]) {
  const original = body(purpose);
  assert.equal(sandbox.boundedAiRequest(original, true).max_output_tokens, ceiling); checks++;
  assert.equal(sandbox.boundedAiRequest({...original,max_output_tokens:999999},false).max_output_tokens,ceiling); checks++;
  assert.equal(sandbox.boundedAiRequest({...original,max_output_tokens:1},false).max_output_tokens,1); checks++;
  const prepared=sandbox.defaults(original);
  assert.equal(prepared.store,false); assert.equal(prepared.max_output_tokens,ceiling); checks++;
  assert.equal(original.max_output_tokens,undefined); checks++;
}
for (const value of [-1,0,1.5,'512',true,null,Number.MAX_SAFE_INTEGER,Infinity,NaN]) {
  assert.throws(() => sandbox.boundedAiRequest({...body('general'),max_output_tokens:value},false),
    error => error.fatal === true && error.aiUsageLimit === true); checks++;
}
assert.throws(() => sandbox.boundedAiRequest({...body('general'),model:'unapproved'},false)); checks++;
assert.throws(() => sandbox.boundedAiRequest(body('unknown'),false)); checks++;
assert.equal(sandbox.boundedAiRequest({model:'gpt-5.6',input:'synthetic'},false).max_output_tokens,512); checks++;
const sensitive='dummy-sensitive-value-never-transmitted';
try { sandbox.boundedAiRequest({model:sensitive,input:sensitive},false); assert.fail(); }
catch (error) { assert.equal(error.message,'AI usage limit reached.'); assert.ok(!String(error).includes(sensitive)); checks++; }
console.log(`SEC006 AI REQUEST PASS (${checks} JS checks)`);
