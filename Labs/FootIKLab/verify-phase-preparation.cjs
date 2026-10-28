/* Real new-phase preparation; saved user state is read-only in this test. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const url='http://127.0.0.1:8890';
(async()=>{
 const saved=await(await fetch(url+'/state')).json();saved.playback.playing=false;
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-background-networking','--disable-extensions','--disable-component-update','--disable-sync']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:850}}),errors=[],cases=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/state',r=>r.fulfill({json:r.request().method()==='GET'?saved:{saved:true}}));
  await page.addInitScript(()=>{window.phaseRequests=[];const real=fetch;window.fetch=async(url,options)=>{const start=performance.now(),response=await real(url,options);if(String(url)==='/resume'){const json=response.json.bind(response);response.json=async()=>{const data=await json();phaseRequests.push({request:JSON.parse(options.body),ms:performance.now()-start,cache:data.cache,inferenceSeconds:data.seconds});return data;};}return response;};});
  await page.goto(url);await page.waitForFunction(()=>window.FootIKLab&&!busy,null,{timeout:60000,polling:100});
  cases.push(await page.evaluate(()=>({kind:'load',ms:loadTiming.ready,requests:phaseRequests.map(({request,...x})=>({...x,phase:request.phase,kind:request.kind||'continuation'})),stages:loadTiming.stages})));
  for(const phase of [.47,.73]){
   const info=await page.evaluate(phase=>{
    window.phaseStarted=performance.now();window.phaseRequests=[];window.phaseBefore={time,renderer};
    const input=document.getElementById('phaseInput');input.value=phase;input.dispatchEvent(new Event('change',{bubbles:true}));
    return revision;
   },phase);
   await page.waitForFunction(id=>revision===id&&!busy,info,{timeout:60000,polling:50});
   const result=await page.evaluate(()=>({kind:'phase',phase:settings.phase,ms:performance.now()-phaseStarted,requests:phaseRequests.map(({request,...x})=>({...x,phase:request.phase,kind:request.kind||'continuation'})),stages:loadTiming.stages,framePreserved:time===phaseBefore.time,rendererPreserved:renderer===phaseBefore.renderer,error:document.querySelector('#error').textContent}));
   assert(result.framePreserved&&result.rendererPreserved&&!result.error);cases.push(result);
  }
  assert.equal(errors.length,0);const result={passed:true,cases,errors};fs.writeFileSync(path.join(__dirname,'snapshots/phase-preparation-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
