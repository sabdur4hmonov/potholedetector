/* Deterministic SEC-010 policy and resource-lifetime tests of production functions.
 * Bitmap/canvas APIs are instrumented, so hostile bounds never allocate pixels.
 * Actual format decoding is covered separately by the real-browser test.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/standalone.js'), 'utf8');
const fixtures = require('./fixtures/sec010-images.json');
const helper = source.slice(source.indexOf('  // SEC-010:'), source.indexOf('  // Photos are stored as blobs'));
function productionFunction(name) {
  const start = source.search(new RegExp(`  (?:async )?function ${name}\\(`));
  assert.ok(start >= 0, name);
  return source.slice(start, source.indexOf('\n  }', start) + 4);
}
let decodeCalls = [], closes = 0, canvases = [], failDecode = false, lie = false, failDraw = false, failEncode = false;
let alerts = [], revoked = [], originalCalls = [], originalFailure = false;
let activeBitmaps = 0, peakBitmaps = 0;
const preview = { src: '', removeAttribute() { this.src = ''; } };
const sandbox = {
  Blob, File, Uint8Array, DataView, Promise, Math, Number, Error, console,
  REPAIR_EVIDENCE_MIN_BYTES: 256, REPAIR_EVIDENCE_MAX_BYTES: 8 * 1024 * 1024,
  REPAIR_EVIDENCE_MIN_DIMENSION: 32, REPAIR_EVIDENCE_MAX_DIMENSION: 8192,
  REPAIR_EVIDENCE_MAX_PIXELS: 40 * 1024 * 1024,
  REPAIR_EVIDENCE_TYPES: new Set(['image/jpeg','image/png','image/webp']),
  alert: message => alerts.push(message),
  URL: { revokeObjectURL: value => revoked.push(value) },
  window: { handleFile: async (file, meta) => {
    originalCalls.push({ file, meta }); preview.src = 'blob:guarded-photo';
    if (originalFailure) throw Error('report failure'); return { ok: true };
  } },
  document: { addEventListener() {}, getElementById: () => preview,
    createElement: () => {
      const canvas = { width: 0, height: 0, getContext: () => ({
        drawImage() { if (failDraw) throw Error('draw failure'); },
      }), toDataURL: () => 'data:image/jpeg;base64,bounded',
      toBlob: callback => callback(failEncode ? null : new Blob([Buffer.from(fixtures.jpeg, 'base64')], { type: 'image/jpeg' })) };
      canvases.push(canvas); return canvas;
    } },
  createImageBitmap: async (blob, options) => {
    decodeCalls.push({ blob, options });
    if (failDecode) throw Error('decoder rejected bytes');
    activeBitmaps++; peakBitmaps=Math.max(peakBitmaps,activeBitmaps);
    return { width: lie ? 20000 : options.resizeWidth, height: options.resizeHeight, close() { closes++; activeBitmaps--; } };
  },
};
vm.createContext(sandbox);
vm.runInContext(helper + '\n' + productionFunction('toDataUrl') + '\n' + productionFunction('decodeRepairEvidence'), sandbox);
const policy = vm.runInContext('IMAGE_DECODE_POLICY', sandbox);
const image = (name = 'png') => new Blob([Buffer.from(fixtures[name], 'base64')]);
function jpegBounds(width, height) {
  const bytes = Uint8Array.from([255,216,255,192,0,11,8,0,0,0,0,1,1,17,0,255,218,0,8,1,1,0,0,63,0,255,217]);
  new DataView(bytes.buffer).setUint16(7, height); new DataView(bytes.buffer).setUint16(9, width);
  return new Blob([bytes]);
}
const rejects = promise => assert.rejects(promise, /malformed|limits/);
let passed = 0;
async function test(name, fn) { await fn(); passed++; console.log('PASS ' + name); }

(async () => {
  await test('normal raster formats and EXIF bounds', async () => {
    for (const name of Object.keys(fixtures)) {
      const b = await sandbox.readImageBounds(image(name));
      assert.equal(b.width, name.endsWith('-oriented') ? 48 : ['gif','bmp'].includes(name) ? 8 : 64, name);
      assert.equal(b.height, name.endsWith('-oriented') ? 64 : ['gif','bmp'].includes(name) ? 6 : 48, name);
    }
  });
  await test('normal valid preparation succeeds and releases resources', async () => {
    const before = closes;
    assert.match(await sandbox.toDataUrl(image(), 2000), /^data:image\/jpeg/);
    assert.equal(closes, before + 1); assert.equal(canvases.at(-1).width, 0); assert.equal(canvases.at(-1).height, 0);
  });
  await test('inclusive dimension and pixel limits are accepted', async () => {
    sandbox.checkedImageDimensions(policy.maxDimension, 1);
    sandbox.checkedImageDimensions(8000, 8000);
    const b = await sandbox.decodeBoundedImage(jpegBounds(8000,8000), 4000);
    assert.equal(b.width, 4000); assert.equal(b.height, 4000); b.close();
  });
  await test('oversized axis and excessive pixel count reject before decoder', async () => {
    const count = decodeCalls.length;
    await rejects(sandbox.decodeBoundedImage(jpegBounds(12001,1),4000));
    await rejects(sandbox.decodeBoundedImage(jpegBounds(8001,8000),4000));
    assert.equal(decodeCalls.length,count);
  });
  await test('output downscales whole frame with unchanged aspect ratio', async () => {
    const b = await sandbox.decodeBoundedImage(jpegBounds(8000,6000),2000);
    assert.equal(b.width,2000); assert.equal(b.height,1500); b.close();
    const options = decodeCalls.at(-1).options;
    assert.equal(options.imageOrientation,'from-image'); assert.equal(options.resizeQuality,'high');
  });
  await test('zero negative noninteger and overflow cannot bypass division check', async () => {
    for (const [w,h] of [[0,1],[-1,1],[1.5,1],[Infinity,1],[Number.MAX_SAFE_INTEGER,Number.MAX_SAFE_INTEGER],[12000,12000]]) {
      assert.throws(()=>sandbox.checkedImageDimensions(w,h),/malformed|limits/);
    }
    assert.throws(()=>sandbox.checkedImageDimensions(Number.MAX_SAFE_INTEGER,2,Number.MAX_SAFE_INTEGER,policy.maxPixels),/malformed|limits/);
  });
  await test('encoded-size rejection performs no read and no decode', async () => {
    let reads=0;
    class Huge extends Blob { get size(){return policy.maxEncodedBytes+1;} slice(){reads++;throw Error('unexpected allocation');} }
    const count=decodeCalls.length;
    await rejects(sandbox.decodeBoundedImage(new Huge(),4000));
    assert.equal(reads,0);assert.equal(decodeCalls.length,count);
  });
  await test('inclusive encoded-byte limit uses bounded slices only', async () => {
    let largestSlice=0;
    const head=await jpegBounds(64,48).arrayBuffer();
    class VirtualBoundary extends Blob {
      get size(){return policy.maxEncodedBytes;}
      slice(start,end){ largestSlice=Math.max(largestSlice,start<0?-start:end-start);return new Blob([head]); }
      arrayBuffer(){throw Error('unbounded original read');}
    }
    const b=await sandbox.decodeBoundedImage(new VirtualBoundary(),4000);b.close();
    assert.ok(largestSlice<=policy.maxHeaderBytes);
  });
  await test('malformed truncated and unsupported vector image reject before decode', async () => {
    const count=decodeCalls.length;
    for (const blob of [new Blob(['invalid bytes for image']),image().slice(0,33),jpegBounds(64,48).slice(0,-2),new Blob(['<svg width="100000" height="100000"></svg>'])]) {
      await rejects(sandbox.decodeBoundedImage(blob,4000));
    }
    assert.equal(decodeCalls.length,count);
  });
  await test('decoder failure releases queue for the next valid photo', async () => {
    failDecode=true;await rejects(sandbox.toDataUrl(image(),2000));failDecode=false;
    assert.match(await sandbox.toDataUrl(image(),2000),/^data:/);
  });
  await test('untrusted decoder output is rechecked and closed before canvas allocation', async () => {
    lie=true; const before=closes,count=canvases.length;
    await rejects(sandbox.toDataUrl(image(),2000));lie=false;
    assert.equal(closes,before+1);assert.equal(canvases.length,count);
  });
  await test('render and encoder failures close bitmap and reset canvas', async () => {
    let before=closes;failDraw=true;await assert.rejects(sandbox.toDataUrl(image(),2000),/draw failure/);failDraw=false;
    assert.equal(closes,before+1);assert.equal(canvases.at(-1).width,0);
    before=closes;failEncode=true;await rejects(sandbox.toDataUrl(image(),2000,0.9,false,true));failEncode=false;
    assert.equal(closes,before+1);assert.equal(canvases.at(-1).height,0);
  });
  await test('manual import guard runs before preview and preserves provenance', async () => {
    sandbox.installManualPhotoBudget();
    const meta={captureSource:'manual_import',capturedAtMs:1234};
    await sandbox.window.handleFile(new File([image()], 'normal.png',{lastModified:1234}),meta);
    assert.equal(originalCalls.length,1);assert.equal(originalCalls[0].meta,meta);
    assert.equal(originalCalls[0].file.type,'image/jpeg');assert.equal(originalCalls[0].file.lastModified,1234);
    assert.equal(preview.src,'');assert.deepEqual(revoked,['blob:guarded-photo']);
    await sandbox.window.handleFile(jpegBounds(12001,1),meta);
    assert.equal(originalCalls.length,1);assert.ok(alerts.at(-1).includes('limits'));
  });
  await test('manual downstream failure revokes preview and permits retry', async () => {
    originalFailure=true;await sandbox.window.handleFile(image(),{});originalFailure=false;
    assert.equal(preview.src,'');assert.equal(revoked.length,2);
    await sandbox.window.handleFile(image(),{});assert.equal(originalCalls.length,3);
  });
  await test('concurrent preparations retain at most one bitmap', async () => {
    assert.equal(activeBitmaps,0);peakBitmaps=0;
    await Promise.all([sandbox.toDataUrl(image(),2000),sandbox.toDataUrl(image(),2000)]);
    assert.equal(peakBitmaps,1);assert.equal(activeBitmaps,0);
  });
  await test('simultaneous manual imports cannot accumulate preparations', async () => {
    const before=originalCalls.length;
    await Promise.all([sandbox.window.handleFile(image(),{}),sandbox.window.handleFile(image(),{})]);
    assert.equal(originalCalls.length,before+1);assert.ok(alerts.some(m=>m.includes('already being prepared')));
  });
  await test('repair bounds enforced before decode and original limits preserved', async () => {
    const jpeg=new Blob([Buffer.from(fixtures.jpeg,'base64')],{type:'image/jpeg'});
    assert.equal(await sandbox.decodeRepairEvidence(jpeg),jpeg);
    const count=decodeCalls.length;
    for(const [w,h] of [[9000,100],[8000,6000]]) {
      const header=await jpegBounds(w,h).slice(0,-2).arrayBuffer();
      assert.equal(await sandbox.decodeRepairEvidence(new Blob([header,new Uint8Array(512),Uint8Array.from([255,217])],{type:'image/jpeg'})),null);
    }
    assert.equal(decodeCalls.length,count);assert.equal(activeBitmaps,0);
  });
  console.log(`${passed} SEC-010 deterministic tests passed`);
})().catch(e=>{console.error(e);process.exitCode=1;});
