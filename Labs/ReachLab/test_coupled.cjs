const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process'),vm=require('node:vm');
(async()=>{
const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachCoupled20261015');fs.mkdirSync(out,{recursive:true});const store=fs.mkdtempSync(path.join(out,'test-'));const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe'});let browser;try{
for(let i=0;;i++){try{if((await fetch('http://127.0.0.1:'+port+'/health')).ok)break;}catch(e){if(i>80)throw e;}await new Promise(r=>setTimeout(r,100));}
browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:'+port+'/reach');await page.waitForFunction(()=>window.reachLab?.ready);await page.evaluate(()=>setPlaying(false));await page.waitForFunction(()=>!pending);
const result=await page.evaluate(async()=>{
 const metrics={frames:0,maxLengthError:0,maxLimitError:0,maxQuaternionError:0,maxFootOverride:0,maxEvaluations:0,maxHandStep:0,coreMs:[],correctionMs:[]},samples=[];
 const original=ReachCoupled.solve;let calls=0;
 ReachCoupled.solve=input=>{const solved=original(input);calls++;if(samples.length<40&&calls%7===0)samples.push(copy(input));metrics.maxEvaluations=Math.max(metrics.maxEvaluations,solved.evaluations);return solved;};
 const apply=applyFrame;
 applyFrame=raw=>{const old=copy(pose),wasReturning=!!wholeReturn;apply(raw);metrics.frames++;
  for(let k=0;k<2;k++)if(settings.phat&&settings.hands[k].enabled&&grabs[k]?.active&&!grabs[k].error){
   const ids=arms[k].slice(1);for(let i=0;i<2;i++)metrics.maxLengthError=Math.max(metrics.maxLengthError,Math.abs(norm(sub(pose[ids[i+1]].slice(0,3),pose[ids[i]].slice(0,3)))-armLengths[k][i]));
   const q=pose[hands[k]].slice(3),limited=ReachWrist.constrain(phat.wrists[k],pose[arms[k][2]].slice(3),q);metrics.maxLimitError=Math.max(metrics.maxLimitError,1-Math.abs(dot(q,limited)));metrics.maxHandStep=Math.max(metrics.maxHandStep,norm(sub(pose[hands[k]].slice(0,3),old[hands[k]].slice(0,3))));
  }
  for(const t of pose){if(!t.every(Number.isFinite))throw Error('Non-finite pose');metrics.maxQuaternionError=Math.max(metrics.maxQuaternionError,Math.abs(norm(t.slice(3))-1));}
  if(!wasReturning)for(const name of ['foot_l','foot_r']){const j=nameToIndex.get(name);metrics.maxFootOverride=Math.max(metrics.maxFootOverride,norm(sub(pose[j].slice(0,3),raw[j].slice(0,3))));}
 };
 async function run(n){for(let i=0;i<n;i+=4){await step(Math.min(4,n-i));metrics.coreMs.push(solveMs);metrics.correctionMs.push(coupledMs);}}
 const cases=[];
 for(const orientation of ['surface','target']){
  settings=defaults();settings.hands.forEach(h=>h.orientation=orientation);resetPose();prepareGrabs();const fixed=copy(grabs.map(g=>({normal:g.normal,rotation:g.rotation,palm:g.palm,curl:g.curl})));await run(240);
  cases.push({orientation,hands:copy(grabs),fixedContact:JSON.stringify(fixed)===JSON.stringify(grabs.map(g=>({normal:g.normal,rotation:g.rotation,palm:g.palm,curl:g.curl}))),state:snapshot()});
 }
 const saved=snapshot();await run(16);const next=snapshot();await reachLab.restore(saved);await run(16);const replay=snapshot();const deterministic=['pose','solverState','grabs'].every(k=>JSON.stringify(next[k])===JSON.stringify(replay[k]));
 settings.hands[0].target[0]+=8;settings.hands[0].target[2]-=10;await run(120);const moved={held:grabs[0].gripped,palm:grabs[0].coupled.palmError,attachmentError:norm(sub(ReachGrab.compose(pose[13],grabs[0].attachment).slice(0,3),grabs[0].ball.slice(0,3)))};
 settings=defaults();settings.hands[0].target=[300,300,300];settings.hands[1].enabled=false;resetPose();await run(180);const unreachable={held:grabs[0].gripped,distance:grabs[0].distance};
 await reachLab.restore(saved);setGrab(0,false);const wrist=pose[13].slice(0,3);const grabOffSeeded=JSON.stringify(solverState.slice(6,9))===JSON.stringify(wrist.map(v=>v*.01));await step(1);const grabOffStep=norm(sub(pose[13].slice(0,3),wrist));
 const oldCalls=calls;settings.phat=false;await run(8);const clampOffSkipped=calls===oldCalls;
 setEnabled(0,false);setEnabled(1,false);const offCalls=calls;await run(16);const inactiveSkipped=calls===offCalls;const tick=ticks;await step(4);const retired=ticks===tick;
 await reachLab.restore(cases[0].state);syncControls();drawAll();
 return {metrics,samples,cases:cases.map(c=>({orientation:c.orientation,hands:c.hands.map(g=>({held:g.gripped,distance:g.distance,angle:g.angle,palm:g.coupled.palmError,evaluations:g.coupled.evaluations})),fixedContact:c.fixedContact})),deterministic,moved,unreachable,grabOffSeeded,grabOffStep,clampOffSkipped,inactiveSkipped,retired};
});
fs.writeFileSync(path.join(out,'trial.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({...result,samples:result.samples.length,metrics:{...result.metrics,coreMs:undefined,correctionMs:undefined}}));
assert(result.cases.every(c=>c.hands.every(h=>h.held)&&c.fixedContact),'Both modes acquire with original fixed contact');assert(result.metrics.maxLengthError<1e-8);assert(result.metrics.maxLimitError<1e-12);assert(result.metrics.maxQuaternionError<1e-12);assert(result.metrics.maxFootOverride<1e-8);assert(result.metrics.maxEvaluations<=18);assert(result.deterministic);assert(result.grabOffSeeded&&result.grabOffStep<=2.001);assert(result.moved.held&&result.moved.attachmentError<1e-9);assert(!result.unreachable.held&&result.unreachable.distance>3);assert(result.clampOffSkipped&&result.inactiveSkipped&&result.retired);assert.deepEqual(errors,[]);
// Arithmetic-only benchmark, deliberately excludes networking, rendering and the unchanged native kernel.
global.Recovery=require('../SwordHolsterLab/recovery.js');global.ReachWrist=require('./wrist.js');vm.runInThisContext(fs.readFileSync(path.join(__dirname,'coupled.js'),'utf8'));
for(let i=0;i<3000;i++)ReachCoupled.solve(result.samples[i%result.samples.length]);
const batches=[];let totalEvals=0;for(let b=0;b<100;b++){const start=performance.now();for(let i=0;i<100;i++)totalEvals+=ReachCoupled.solve(result.samples[i%result.samples.length]).evaluations;batches.push((performance.now()-start)/100);}
const stat=a=>{const s=[...a].sort((a,b)=>a-b);return {mean:a.reduce((a,b)=>a+b,0)/a.length,p95:s[Math.floor(s.length*.95)],max:s.at(-1)};};
const receipt={passed:true,...result,samples:undefined,metrics:{...result.metrics,coreMs:stat(result.metrics.coreMs),correctionMs:stat(result.metrics.correctionMs)},benchmark:{description:'100 batches x 100 single-hand solves, mixed approach poses; no render/network/native body cost',perHandMs:stat(batches),meanEvaluations:totalEvals/10000},errors};fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));await page.screenshot({path:path.join(out,'coupled.png')});
}finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exit(1)});
