const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachArmFirst20261015'),fixture=JSON.parse(fs.readFileSync(process.argv[2]||path.join(__dirname,'snapshots/snapshot_0002.json'),'utf8'));fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});try{const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8873/reach');await page.waitForFunction(()=>reachLab.ready);await page.evaluate(()=>setPlaying(false));await page.waitForFunction(()=>!pending);
 const result=await page.evaluate(async saved=>{
  const originalPlan=ReachCoupled.plan,originalUpdate=ReachGrab.update;let planCalls=0,planEvaluations=0,maxPlanEvaluations=0,badAcquisitions=0;
  ReachCoupled.plan=input=>{const p=originalPlan(input);planCalls++;planEvaluations+=p.evaluations;maxPlanEvaluations=Math.max(maxPlanEvaluations,p.evaluations);return p;};
  ReachGrab.update=(g,h,w,t)=>{const held=g.gripped;originalUpdate(g,h,w,t);if(!held&&g.gripped&&(g.angle>t.grip||g.distance>=1.25||g.close<1))badAcquisitions++;};
  const times=[],bodyTimes=[];const run=async n=>{for(let i=0;i<n;i+=4){await step(Math.min(4,n-i));times.push(coupledMs);bodyTimes.push(solveMs);}};
  const stats=()=>({dropCm:solverState[0]*100,pitchDegrees:solverState[4]*180/Math.PI,rollDegrees:solverState[5]*180/Math.PI,hands:grabs.map(g=>({held:g?.gripped,angle:g?.angle,distance:g?.distance,palm:g?.coupled?.palmError,reserve:g?.armPlan?.reserve}))});
  const fixed=grabs=>JSON.stringify(grabs.map(g=>[g.normal,g.rotation,g.palm,g.curl]));const results=[];
  for(const mode of ['continue','fromIdle','freshContact']){
   await reachLab.restore(saved);
   if(mode!=='continue'){const captured=copy(grabs);resetPose();if(mode==='fromIdle'){grabs=captured;for(const g of grabs){g.gripped=false;g.close=0;g.attachment=null;delete g.armPlan;}}}
   prepareGrabs();const before=fixed(grabs);await run(480);const report=stats();const state=snapshot();const beforeCalls=planCalls;await run(120);
   results.push({mode,...report,contactUnchanged:fixed(grabs)===before,settledPlanCalls:planCalls-beforeCalls,state});
  }
  const checkpoint=snapshot();await run(16);const next=snapshot();await reachLab.restore(checkpoint);await run(16);const replay=snapshot();const deterministic=['pose','grabs','solverState'].every(k=>JSON.stringify(next[k])===JSON.stringify(replay[k]));
  await reachLab.restore(results[1].state);const reserveBefore=grabs[0].armPlan.reserve,fitBefore=JSON.stringify(grabs.map(g=>[g.normal,g.rotation,g.curl]));settings.hands[0].target[0]+=1;await run(4);const reserveAfter=grabs[0].armPlan.reserve;await run(120);const moved={...stats(),reserveBefore,reserveAfter,fitPreserved:fitBefore===JSON.stringify(grabs.map(g=>[g.normal,g.rotation,g.curl]))};
  settings=defaults();resetPose();for(let k=0;k<2;k++){const a=arms[k],h=settings.hands[k],desired=ReachWrist.constrain(phat.wrists[k],pose[a[2]].slice(3),pose[a[3]].slice(3));h.orientation='target';h.rotation=rotationDegrees(desired);h.target=add(pose[a[1]].slice(0,3),[0,15,-10]);}
  prepareGrabs();for(let k=0;k<2;k++){const g=grabs[k],wrist=add(pose[arms[k][1]].slice(0,3),[0,15,-10]);settings.hands[k].target=sub(add(wrist,R.rotate(g.rotation,g.palm)),mul(g.normal,g.radius+.35));}await run(360);const armOnly=stats();
  const callsBefore=planCalls;settings.phat=false;await run(8);const clampOffSkipped=planCalls===callsBefore;
  await reachLab.restore(results[1].state);drawAll();
  return {original:{dropCm:saved.solverState[0]*100,pitchDegrees:saved.solverState[4]*180/Math.PI},cases:results,armOnly,moved,deterministic,clampOffSkipped,badAcquisitions,planCalls,planEvaluations,maxPlanEvaluations,times,bodyTimes};
 },fixture);
 const stat=a=>{const s=[...a].sort((a,b)=>a-b);return {mean:a.reduce((a,b)=>a+b,0)/a.length,p95:s[Math.floor(s.length*.95)],max:s.at(-1)};};
 const report={...result,cases:result.cases.map(({state,...rest})=>rest),times:stat(result.times),bodyTimes:stat(result.bodyTimes),errors};fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));fs.writeFileSync(path.join(out,'after.json'),JSON.stringify(result.cases[1].state,null,2));console.log(JSON.stringify(report));await page.screenshot({path:path.join(out,'after.png')});
 assert.deepEqual(errors,[]);assert(result.cases.every(c=>c.hands.every(h=>h.held&&h.angle<=fixture.settings.grip&&h.distance<1.25)&&c.contactUnchanged));assert(result.cases.slice(0,2).every(c=>c.dropCm<result.original.dropCm*.6&&c.pitchDegrees<result.original.pitchDegrees*.65));assert(result.cases.every(c=>c.settledPlanCalls===0));assert(result.armOnly.hands.every(h=>h.reserve===0&&h.held));assert(result.moved.reserveAfter>result.moved.reserveBefore*.5&&result.moved.fitPreserved&&result.moved.hands.every(h=>h.held));assert(result.deterministic&&result.clampOffSkipped);assert.equal(result.badAcquisitions,0);assert(result.maxPlanEvaluations<=14);report.passed=true;fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
