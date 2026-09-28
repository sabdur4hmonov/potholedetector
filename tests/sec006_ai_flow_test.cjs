const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = process.env.POTHOLE_TEST_APP || 'http://127.0.0.1:8765/';
(async () => {
  const browser = await chromium.launch({ headless:true, executablePath:process.env.POTHOLE_TEST_CHROME });
  let tests=0;
  try {
    for (const native of [false,true]) {
      const context=await browser.newContext();
      await context.addInitScript(native => {
        window.__fixture={requests:[],rejectBudget:false,paidFetch:0};
        const original=window.fetch.bind(window);
        window.fetch=(url,init)=>{
          if (String(url).includes('api.openai.com/v1/responses')) { __fixture.paidFetch++; throw Error('Unexpected paid fetch'); }
          return original(url,init);
        };
        if (native) window.Capacitor={isNativePlatform:()=>true,Plugins:{SecureCredentials:{
          getStatus:async()=>({openAiConfigured:true,dashcamRtspConfigured:false}),
          migrateLegacyCredentials:async()=>({openAiConfigured:true,dashcamRtspConfigured:false}),
          openAiRequest:async envelope=>{
            const request=JSON.parse(envelope.body); __fixture.requests.push(request);
            if (__fixture.rejectBudget) { const error=Error('synthetic'); error.code='AI_USAGE_LIMIT'; throw error; }
            const verdict='{"ok":true}';
            const text=request.stream ? 'data: '+JSON.stringify({type:'response.output_text.delta',delta:verdict})+'\n\ndata: [DONE]\n\n'
              : JSON.stringify({output:[{type:'message',content:[{type:'output_text',text:verdict}]}]});
            return {status:200,ok:true,body:text};
          }
        }}};
      },native);
      await context.route('**/standalone.js', route => route.fulfill({contentType:'application/javascript',body:
        fs.readFileSync(path.join(__dirname,'../static/standalone.js'),'utf8').replace('  window.StandaloneAPI =',
          '  window.__sec006 = { oai, oaiStream, analyzeImage, CredentialBroker, ASSESS_SCHEMA };\n  window.StandaloneAPI =')}));
      const page=await context.newPage(); await page.goto(app); await page.waitForFunction(()=>window.__sec006);
      if (!native) {
        await page.evaluate(()=>CredentialBroker.storeCredentials({openAiKey:'dummy-never-transmitted'}));
        const denied=await page.evaluate(async()=>{
          try {await __sec006.oai({model:'gpt-5-mini',input:'synthetic'}); return false;}
          catch(error){return error.fatal===true && error.message==='AI inference is available only in the Android app.';}
        });
        assert.equal(denied,true); assert.equal(await page.evaluate(()=>__fixture.paidFetch),0); tests+=2;
      } else {
        for (const streaming of [false,true]) {
          const result=await page.evaluate(async streaming=>__sec006[streaming?'oaiStream':'oai']({model:'gpt-5-mini',input:'synthetic'},null,false),streaming);
          assert.equal(result.ok,true); tests++;
        }
        await page.evaluate(()=>CredentialBroker.request({model:'gpt-5-mini',input:'synthetic',store:false,max_output_tokens:999999},false));
        assert.equal(await page.evaluate(()=>__fixture.requests.at(-1).max_output_tokens),512); tests++;
        const denied=await page.evaluate(async()=>{
          __fixture.rejectBudget=true; const before=__fixture.requests.length;
          try {await __sec006.analyzeImage('data:image/jpeg;base64,AA==','synthetic','pothole_binary_assessment',__sec006.ASSESS_SCHEMA,'gpt-5-mini',()=>{},false,'high');return null;}
          catch(error){return {message:error.message,fatal:error.fatal,count:__fixture.requests.length-before};}
        });
        assert.equal(denied.message,'AI usage limit reached.'); assert.equal(denied.fatal,true); assert.equal(denied.count,1); tests+=3;
        assert.equal(await page.evaluate(()=>__fixture.paidFetch),0); tests++;
      }
      await context.close();
    }
    console.log(`SEC006 AI FLOW PASS (${tests} browser/native-gateway-mock checks)`);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
