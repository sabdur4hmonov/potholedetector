/* Real SEC-010 raster preparation and guarded manual-import tests.
 * Uses the existing serve_app.py server, installed Playwright/Chrome, no paid calls.
 */
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const fixtures = require('./fixtures/sec010-images.json');
const APP = process.env.POTHOLE_TEST_APP || 'http://127.0.0.1:8765/';
(async () => {
  const browser = await chromium.launch(process.env.POTHOLE_TEST_CHROME
    ? { executablePath: process.env.POTHOLE_TEST_CHROME, headless: true }
    : { channel: process.env.POTHOLE_TEST_BROWSER_CHANNEL || 'chrome', headless: true });
  try {
    for (const suffix of ['/', '/web-app/']) {
      const context = await browser.newContext({ bypassCSP: false });
      try {
        await context.addInitScript(() => {
          window.__sec010DecodeCalls = [];
          const original = window.createImageBitmap;
          window.createImageBitmap = (...args) => {
            window.__sec010DecodeCalls.push({ size: args[0].size, options: args[1] });
            return original(...args);
          };
          window.__sec010Alerts = [];
          window.alert = msg => window.__sec010Alerts.push(String(msg));
          localStorage.setItem('initial_setup_complete', '1');
        });
        await context.route('**/*', route => new URL(route.request().url()).origin === new URL(APP).origin
          ? route.continue() : route.abort());
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.goto(new URL(suffix, APP).href);
        await page.waitForFunction(() => window.StandaloneAPI?.__pure?.decodeBoundedImage);
        assert.equal(await page.evaluate(() => window.handleFile.name), 'boundedManualPhoto');
        const results = await page.evaluate(async fixtures => {
          const P = StandaloneAPI.__pure;
          const bytes = base64 => Uint8Array.from(atob(base64), c => c.charCodeAt(0));
          const results = [];
          for (const [name, base64] of Object.entries(fixtures)) {
            const output = await P.toDataUrl(new Blob([bytes(base64)]), 32);
            const blob = await (await fetch(output)).blob();
            const b = await P.readImageBounds(blob);
            results.push({ name, width: b.width, height: b.height });
          }
          return results;
        }, fixtures);
        for (const result of results) {
          const small = ['gif','bmp'].includes(result.name);
          const oriented = result.name.endsWith('-oriented');
          assert.equal(result.width, small ? 8 : oriented ? 24 : 32, result.name);
          assert.equal(result.height, small ? 6 : oriented ? 32 : 24, result.name);
        }
        const rejection = await page.evaluate(async () => {
          const P = StandaloneAPI.__pure;
          const jpeg = Uint8Array.from([255,216,255,192,0,11,8,0,1,46,225,1,1,17,0,255,218,0,8,1,1,0,0,63,0,255,217]);
          const before = window.__sec010DecodeCalls.length;
          let rejected = false;
          try { await P.toDataUrl(new Blob([jpeg]),2000); } catch { rejected=true; }
          return { rejected, decodes: window.__sec010DecodeCalls.length-before };
        });
        assert.deepEqual(rejection, { rejected: true, decodes: 0 });
        const malformed = await page.evaluate(async base64 => {
          const P = StandaloneAPI.__pure;
          const png = Uint8Array.from(atob(base64), c=>c.charCodeAt(0));
          // Preserve dimensions/chunk layout but corrupt the compressed payload.
          for (let i=33;i<png.length-12;i++) if (png[i]===73 && png[i+1]===68 && png[i+2]===65 && png[i+3]===84) {
            for(let p=i+4;p<Math.min(i+12,png.length-12);p++) png[p]=255;
            break;
          }
          let rejected=false;try {await P.toDataUrl(new Blob([png]),2000);}catch {rejected=true;}
          const recovered=await P.toDataUrl(new Blob([Uint8Array.from(atob(base64),c=>c.charCodeAt(0))]),2000);
          return {rejected,recovered:recovered.startsWith('data:image/jpeg;')};
        },fixtures.png);
        assert.deepEqual(malformed,{rejected:true,recovered:true});
        const manual = await page.evaluate(async base64 => {
          const P=StandaloneAPI.__pure;
          const saved={api:window.api,loadReports:window.loadReports,openDetail:window.openDetail};
          let submitted=null;
          localStorage.setItem('data_notice_version',DATA_NOTICE_VERSION);window.confirm=()=>true;
          window.api=async (path,options)=>{submitted=options.body;return {id:99};};
          window.loadReports=async()=>{};window.openDetail=()=>{};
          try {
            const file=new File([Uint8Array.from(atob(base64),c=>c.charCodeAt(0))],'normal.png',{type:'image/png',lastModified:1234});
            await window.handleFile(file,{captureSource:'manual_import',locationConfirmed:false,capturedAtMs:1234});
            const photo=submitted.get('photo');const bounds=await P.readImageBounds(photo);
            return {type:photo.type,width:bounds.width,height:bounds.height,source:submitted.get('capture_source'),time:submitted.get('captured_at_ms'),preview:document.getElementById('progressPhoto').getAttribute('src')};
          }finally{Object.assign(window,saved);}
        },fixtures.png);
        assert.deepEqual(manual,{type:'image/jpeg',width:64,height:48,source:'manual_import',time:'1234',preview:null});
        const frame = await page.evaluate(async () => {
          const c=document.createElement('canvas');c.width=640;c.height=480;const ctx=c.getContext('2d');
          for(const [color,x,y] of [['#ff0000',0,0],['#00ff00',320,0],['#0000ff',0,240],['#ffff00',320,240]]) {
            ctx.fillStyle=color;ctx.fillRect(x,y,320,240);
          }
          const source=await new Promise(resolve=>c.toBlob(resolve,'image/png'));
          const encoded=await StandaloneAPI.__pure.toDataUrl(source,200);
          const bitmap=await createImageBitmap(await (await fetch(encoded)).blob());
          c.width=bitmap.width;c.height=bitmap.height;ctx.drawImage(bitmap,0,0);bitmap.close();
          return {width:c.width,height:c.height,corners:[[2,2],[c.width-3,2],[2,c.height-3],[c.width-3,c.height-3]].map(([x,y])=>Array.from(ctx.getImageData(x,y,1,1).data).slice(0,3))};
        });
        assert.equal(frame.width,200);assert.equal(frame.height,150);
        for(const [i,expected] of [[0,[255,0,0]],[1,[0,255,0]],[2,[0,0,255]],[3,[255,255,0]]]) {
          frame.corners[i].forEach((channel,j)=>assert.ok(Math.abs(channel-expected[j])<10,'complete-frame corner lost'));
        }
        // Reuse the existing authoritative enhancement fixture through its production kernel.
        const parity = require('../android-app/android/app/src/test/resources/detection-image-enhancement-v1.json');
        const parityResults=await page.evaluate(cases=>cases.map(c=>{
          const P=StandaloneAPI.__pure,values=c.input_rgb.split(',').map(Number),rgba=new Uint8ClampedArray(c.width*c.height*4);
          for(let i=0;i<c.width*c.height;i++){rgba.set(values.slice(i*3,i*3+3),i*4);rgba[i*4+3]=255;}
          P.applyDetectionEnhancement(rgba,P.detectionEnhancementPlan(rgba,c.width,c.height));
          return Array.from(rgba).filter((_,i)=>i%4!==3);
        }),parity.cases);
        parity.cases.forEach((c,i)=>assert.deepEqual(parityResults[i],c.expected_rgb.split(',').map(Number),c.name));
        assert.deepEqual(errors,[]);
        console.log(`PASS ${suffix}: eight real raster/EXIF cases, pre-decode oversized rejection, malformed decoder failure/recovery, guarded report submission and preview cleanup, full-frame corners, existing enhancement fixtures`);
      }finally{await context.close();}
    }
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
