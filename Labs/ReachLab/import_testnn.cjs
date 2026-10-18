// Import captured native state and compare in an isolated browser/service.
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachScenario20261016');fs.mkdirSync(out,{recursive:true});
 const native=JSON.parse(fs.readFileSync(path.join(out,'native.json'),'utf8'));assert.equal(native.reason,'captured');
 const store=fs.mkdtempSync(path.join(out,'test-')),probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe'});
 let browser;try{
 let log='';child.stderr.on('data',d=>log+=d);const url=`http://127.0.0.1:${port}`;
 for(let i=0;;i++){try{if((await fetch(url+'/health')).ok)break;}catch(e){if(i>100)throw Error(log||e);}await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(url+'/reach');await page.waitForFunction(()=>reachLab.ready);await page.evaluate(async()=>{setPlaying(false);await settled();});
 const result=await page.evaluate(async rows=>{
  function convert(n){
   const s=snapshot();s.playing=false;s.tick=n.tick;s.basePose=copy(n.base);s.pose=copy(n.pose);s.solverState=copy(n.state);s.handQ=hands.map(j=>n.pose[j].slice(3));s.returns=[null,null];s.wholeReturn=null;
   s.settings=defaults();s.settings.closure=n.angles[0];s.settings.grip=n.angles[1];s.settings.syncRotation=n.tuning[0];s.settings.elbowDownBlend=n.tuning[1];s.phat={...phat,wrists:n.hands.map(h=>h.joint)};
   s.grabs=n.hands.map((h,k)=>{
    const radius=norm(sub(h.surface,h.ball.slice(0,3))),rotation=h.target.slice(3),normal=h.normal;
    // Last evaluated native target is authoritative; the physical ball may have
    // moved a fraction since that evaluation. Right ball is stationary.
    const center=sub(add(h.target.slice(0,3),R.rotate(rotation,h.palm)),mul(normal,radius+.35));
    const input={enabled:h.enabled,grab:h.grab,target:center,rotation:rotationDegrees(rotation),orientation:'target',radius,speed:h.speed,rotationSpeed:h.rotationSpeed};s.settings.hands[k]=input;
    const g={...ReachGrab.fresh(center),active:h.grab,gripped:h.gripped,close:h.close,curl:h.curl,contacts:h.contacts,radius,rotation,normal,palm:h.palm,key:ReachGrab.key(input),fitted:true,fitCount:1,clearance:norm(sub(h.palm,fingerModels[k].palm))};
    if(h.gripped)g.attachment=ReachGrab.relative(g.ball,n.pose[hands[k]]);
    if(h.plan.valid)g.armPlan={...h.plan,version:3,key:JSON.stringify([h.target.slice(0,3),rotation,s.phat.wrists[k]]),residual:0};
    return g;
   });
   s.scenario={name:'TestNN right hand',absoluteTick:n.tick,source:'native.json',baseMode:'Captured neural base pose held fixed; both hands and native state preserved.',physicalAdmission:'Lab is kinematic; Unreal additionally checks its physical wrist.'};return s;
  }
  const stats=()=>({tick:ticks,hands:grabs.map((g,k)=>({held:g.gripped,close:g.close,distance:g.distance,angle:g.angle,reserve:g.armPlan?.reserve,palm:g.coupled?.palmError,position:pose[hands[k]].slice(0,3)}))});
  const cases=[],fixtures=[];
  for(const tick of [31,250]){
   const n=rows.find(r=>r.tick===tick);if(!n)throw Error('Missing tick '+tick);
   const s=convert(n);fixtures.push(s);await reachLab.restore(s,{save:false});const initial=snapshot();
   const targetErrors=grabs.map((g,k)=>norm(sub(wristTarget(k).slice(0,3),n.hands[k].target.slice(0,3))));
   let firstHeld=null;const samples=[];for(let i=0;i<480;i++){await step(1);if(grabs[1].gripped&&firstHeld===null)firstHeld=ticks;if(i%60===59)samples.push(stats());}
   cases.push({startTick:tick,firstHeld,targetErrors,initial,final:snapshot(),samples,...stats()});
  }
  // Exact one-step input replay: next native base, previous native state and
  // command pose. Refresh moving targets, leaving the solver/arm history intact.
  const replay=[];
  for(let i=1;i<rows.length;i++){
   if(![60,100,150,200,250,300,350].includes(rows[i].tick))continue;
   const prev=convert(rows[i-1]),next=convert(rows[i]);await reachLab.restore(prev,{save:false});setBasePose(next.basePose);
   settings=copy(next.settings);for(let k=0;k<2;k++){grabs[k].rotation=next.grabs[k].rotation;grabs[k].normal=next.grabs[k].normal;grabs[k].key=ReachGrab.key(settings.hands[k]);}
   await step(1);
   replay.push({tick:rows[i].tick,positionErrors:pose.map((p,j)=>norm(sub(p.slice(0,3),rows[i].pose[j].slice(0,3)))),rotationErrors:pose.map((p,j)=>angle(p.slice(3),rows[i].pose[j].slice(3))),stateError:Math.max(...solverState.map((v,j)=>Math.abs(v-rows[i].state[j]))),right:stats().hands[1]});
  }
  const interventions=[];
  for(const mode of ['nativeBase','nativeGoals','nativeBaseAndGoals','rootTranslation','rightGoalOnly']){
   await reachLab.restore(convert(rows[0]),{save:false});let firstHeld=null;const samples=[];
   for(let i=1;i<rows.length;i++){
    const n=rows[i],next=convert(n);
    if(['nativeBase','nativeBaseAndGoals'].includes(mode))setBasePose(next.basePose);
    if(['nativeGoals','nativeBaseAndGoals'].includes(mode)){
     settings=copy(next.settings);
     for(let k=0;k<2;k++){grabs[k].rotation=next.grabs[k].rotation;grabs[k].normal=next.grabs[k].normal;grabs[k].key=ReachGrab.key(settings.hands[k]);}
    }
    if(mode==='rightGoalOnly')settings.hands[1].target=next.settings.hands[1].target;
    if(mode==='rootTranslation'){
     const shift=sub(next.settings.hands[1].target,fixtures[0].settings.hands[1].target);
     for(let k=0;k<2;k++)settings.hands[k].target=add(fixtures[0].settings.hands[k].target,shift);
    }
    await step(1);if(grabs[1].gripped&&firstHeld===null)firstHeld=ticks;if(ticks%30===0)samples.push(stats());
   }
   interventions.push({mode,firstHeld,...stats(),samples});
  }
  const moving=copy(fixtures[0]);moving.scenario.baseMode='Recorded native neural base and component-space target motion, absolute ticks31–360; freezes at end. User target offsets remain editable.';
  moving.motion={startTick:31,initial:copy(fixtures[0]),frames:rows.map(n=>{const s=convert(n);return {basePose:s.basePose,targets:s.grabs.map((g,k)=>({center:s.settings.hands[k].target,rotation:g.rotation,normal:g.normal}))};})};
  await reachLab.restore(moving,{save:false});let movingFirstHeld=null;const movingErrors=[];
  for(let i=1;i<rows.length;i++){await step(1);if(grabs[1].gripped&&movingFirstHeld===null)movingFirstHeld=ticks;movingErrors.push(Math.max(...pose.map((p,j)=>norm(sub(p.slice(0,3),rows[i].pose[j].slice(0,3))))));}
  const movingResult={firstHeld:movingFirstHeld,maxPositionError:Math.max(...movingErrors),final:stats()};
  await reachLab.restore(moving,{save:false});await step(4);const batch=snapshot();await reachLab.restore(moving,{save:false});for(let i=0;i<4;i++)await step(1);const batchingEqual=JSON.stringify(pose)===JSON.stringify(batch.pose);
  const checkpoint=snapshot();await step(4);const continued=snapshot();await reachLab.restore(checkpoint,{save:false});await step(4);const resumeEqual=JSON.stringify(pose)===JSON.stringify(continued.pose);
  fixtures.unshift(moving);
  return {fixtures,cases,replay,interventions,movingResult,batchingEqual,resumeEqual};
 },native.rows);
 fs.writeFileSync(path.join(out,'lab-comparison.json'),JSON.stringify({...result,errors},null,2));
 assert.deepEqual(errors,[]);assert(result.cases.every(c=>c.targetErrors.every(e=>e<1e-6)));
 assert(result.movingResult.firstHeld===null);assert(result.movingResult.maxPositionError<.001);assert(result.batchingEqual&&result.resumeEqual);
 for(let i=0;i<result.fixtures.length;i++){
  const s=result.fixtures[i],name=['TestNN_Right_Recorded','TestNN_Right_Frozen_Start_31','TestNN_Right_Stalled_250'][i];
  await page.evaluate(async s=>{await reachLab.restore(s,{save:false});drawAll();},s);
  const png=await page.evaluate(()=>capturePNG(copy(renderData())));
  fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(s,null,2));fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(png.split(',')[1],'base64'));
 }
 console.log(JSON.stringify({movingResult:result.movingResult,batchingEqual:result.batchingEqual,resumeEqual:result.resumeEqual,cases:result.cases.map(({initial,final,samples,...c})=>c),interventions:result.interventions.map(({samples,...r})=>r),replay:result.replay.map(r=>({tick:r.tick,maxPosition:Math.max(...r.positionErrors),rightPosition:r.positionErrors[17],rightAngle:r.rotationErrors[17],stateError:r.stateError})),errors},null,2));
 }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
