// Read-only hardware-WebGL playback benchmark; does not touch desktop state.
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');
(async()=>{
 const label=process.argv[2]||'playback',out=process.env.HARNESS_OUTPUT_DIR||path.resolve(__dirname,'../../Saved/Diagnostics/SwordPlayback');
 fs.mkdirSync(out,{recursive:true});const baseline=process.env.HARNESS_BASELINE_DIR;
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl']});
 try {
 const page=await browser.newPage({viewport:{width:1500,height:1050},deviceScaleFactor:1.25});page.on('pageerror',e=>console.error(e));page.on('console',m=>{if(m.type()==='error')console.error(m.text());});
 if(baseline)for(const file of ['app.js','equipment.js','renderer.js','holster.js','curve-editor.js','recovery.js'])await page.route('**/'+file+'?*',r=>r.fulfill({path:path.join(baseline,file),contentType:'text/javascript'}));
 await page.goto('http://127.0.0.1:8818/');await page.waitForFunction(()=>window.holsterLab?.ready);
 if(process.env.HARNESS_STATE_FILE)await page.evaluate(s=>holsterLab.restore(s),JSON.parse(fs.readFileSync(process.env.HARNESS_STATE_FILE,'utf8')));
 await page.evaluate(()=>canvasPNG()); // Warm capture shaders before playback, as the desktop's initial paused publication does.
 const info=await page.evaluate(()=>{const g=renderer.gl,e=g.getExtension('WEBGL_debug_renderer_info');return {gpu:e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER),canvas:[g.canvas.width,g.canvas.height],triangles:Object.fromEntries(['sword','holster'].map(k=>[k,equipmentSetup[k+'Mesh'].sections.reduce((n,s)=>n+s.triangles.length/3,0)]))};});
 await page.evaluate(()=>{
  window.samples={};window.intervals=[];window.captures=[];window.longTasks=[];
  new PerformanceObserver(l=>longTasks.push(...l.getEntries().map(x=>({start:x.startTime,duration:x.duration})))).observe({entryTypes:['longtask']});
  const wrap=(o,k,label)=>{const f=o[k];o[k]=function(...a){const t=performance.now();try{return f.apply(this,a);}finally{(samples[label]||=[]).push(performance.now()-t);}};};
  wrap(renderer.gl,'readPixels','readPixels');wrap(renderer.gl,'getBufferSubData','readback');wrap(Holster,'sample','pose');wrap(renderer,'draw','render');wrap(renderer,'addSword','equipment');wrap(renderer,'addBody','bodyIncludingEquipment');wrap(renderer,'bindAndDraw','upload');
  const old=drawAll;drawAll=function(){const t=performance.now();old();(samples.draw||=[]).push(performance.now()-t);};
  let last=0;function frame(t){if(last)intervals.push({time:performance.now(),dt:t-last});last=t;requestAnimationFrame(frame);}requestAnimationFrame(frame);
  holsterLab.seek(0);holsterLab.setPlaying(true);
 });
 await page.waitForTimeout(2500);
 const results={info};
 for(const capture of [false,true]){
  await page.evaluate(c=>{samples={};intervals=[];captures=[];longTasks=[];if(c)window.captureTimer=setInterval(async()=>{const start=performance.now(),p=canvasPNG({preview:true}),sync=performance.now()-start;await p;captures.push({start,sync,total:performance.now()-start});},1200);},capture);
  await page.waitForTimeout(12000);
  results[capture?'capture':'plain']=await page.evaluate(()=>{clearInterval(window.captureTimer);const stat=a=>{a=[...a].sort((a,b)=>a-b);return {count:a.length,mean:a.reduce((a,b)=>a+b,0)/a.length,p50:a[Math.floor(a.length*.5)],p95:a[Math.floor(a.length*.95)],p99:a[Math.floor(a.length*.99)],max:a.at(-1)};};return {samples:Object.fromEntries(Object.entries(samples).map(([k,v])=>[k,stat(v)])),frames:stat(intervals.map(x=>x.dt)),missed:intervals.filter(x=>x.dt>25),captures,longTasks};});
 }
 await page.screenshot({path:path.join(out,label+'.png')});
 fs.writeFileSync(path.join(out,label+'.json'),JSON.stringify(results,null,2));console.log(JSON.stringify({info:results.info,...Object.fromEntries(['plain','capture'].map(k=>[k,{draw:results[k].samples.draw,frames:results[k].frames,longTasks:results[k].longTasks.length}]))},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
