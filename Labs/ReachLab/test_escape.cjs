// Targeted regression for TestNN's blocked wrist; never controls the desktop tab.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),vm=require('vm');
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachEscape20261016'),old=fs.readFileSync(path.join(out,'coupled-before.js'),'utf8'),current=fs.readFileSync(path.join(__dirname,'coupled.js'),'utf8');
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8873/reach');await page.waitForFunction(()=>reachLab.ready);await page.evaluate(async()=>{setPlaying(false);await settled();});
  const records=[];
  for(const [version,source] of [['before',old],['after',current]]){
   await page.addScriptTag({content:source});
   records.push(await page.evaluate(async version=>{
    const results=[],inputs=[];let maxEval=0,maxViolation=0;const solve=ReachCoupled.solve;
    ReachCoupled.solve=i=>{if(inputs.length<80&&(inputs.length<20||i.allowGuide||i.guiding))inputs.push(copy(i));const r=solve(i);maxEval=Math.max(maxEval,r.evaluations);return r;};
    for(const name of ['TestNN_Right_Recorded','TestNN_Right_Stalled_250']){
     const s=await getJSON('/snapshots/'+name+'.json');await reachLab.restore(s,{save:false});const first=[null,null],left=[],trace=[];let maxElbowStep=0,maxWristStep=0,maxLeftSettledStep=0,checkpoint=null;
     const contact=JSON.stringify(grabs.map(g=>[g.normal,g.rotation,g.palm,g.curl]));
     for(let i=0;i<360;i++){
      const previous=copy(pose);await step(1);
      for(let k=0;k<2;k++){if(grabs[k].gripped&&first[k]===null)first[k]=ticks;const q=pose[hands[k]].slice(3),p=ReachWrist.constrain(phat.wrists[k],pose[arms[k][2]].slice(3),q);maxViolation=Math.max(maxViolation,1-Math.abs(dot(q,p)));}
      maxElbowStep=Math.max(maxElbowStep,norm(sub(pose[16].slice(0,3),previous[16].slice(0,3))));maxWristStep=Math.max(maxWristStep,norm(sub(pose[17].slice(0,3),previous[17].slice(0,3))));
      if(ticks>=200&&ticks<=300)maxLeftSettledStep=Math.max(maxLeftSettledStep,norm(sub(pose[12].slice(0,3),previous[12].slice(0,3))));
      left.push(copy(pose.slice(10,14)));trace.push({tick:ticks,right:copy(pose[17]),elbow:copy(pose[16]),angle:grabs[1].angle,guiding:grabs[1].coupled?.guiding,stalled:grabs[1].coupled?.stalled});
      if(version==='after'&&name.endsWith('250')&&!checkpoint&&grabs[1].coupled?.guiding)checkpoint=snapshot();
     }
     const final=snapshot();let deterministic=true;
     if(checkpoint){await reachLab.restore(checkpoint,{save:false});for(let i=0;i<12;i++)await step(1);const one=snapshot();await reachLab.restore(checkpoint,{save:false});for(let i=0;i<12;i++)await step(1);deterministic=['pose','solverState','grabs'].every(k=>JSON.stringify(one[k])===JSON.stringify(snapshot()[k]));}
     results.push({name,first,maxElbowStep,maxWristStep,maxLeftSettledStep,final,left,trace,deterministic,fixedContact:contact===JSON.stringify(final.grabs.map(g=>[g.normal,g.rotation,g.palm,g.curl]))});
    }
    return {version,results,maxEval,maxViolation,inputs};
   },version));
  }
  const independence=await page.evaluate(async()=>{
   const s=await getJSON('/snapshots/TestNN_Right_Stalled_250.json'),outputs=[];
   for(const mode of ['normal','rootOnly','translated']){
    const t=copy(s),shift=[53,-37,21],move=p=>[...add(p.slice(0,3),shift),...p.slice(3)];
    if(mode==='rootOnly'){t.basePose[0]=[87,-64,31,...rotationQ([25,17,63])];t.pose[0]=copy(t.basePose[0]);}
    if(mode==='translated'){
     t.basePose=t.basePose.map(move);t.pose=t.pose.map(move);
     for(let k=0;k<2;k++){
      const h=t.settings.hands[k],g=t.grabs[k];h.target=add(h.target,shift);g.ball=move(g.ball);
      for(const start of [6+k*3,12+k*3])for(let j=0;j<3;j++)t.solverState[start+j]+=shift[j]*.01;
      if(g.armPlan){g.armPlan.target=add(g.armPlan.target,shift);g.armPlan.shoulder=add(g.armPlan.shoulder,shift);g.armPlan.key=JSON.stringify([ReachGrab.target(g,h.target).slice(0,3),g.rotation,t.phat.wrists[k]]);}
     }
    }
    await reachLab.restore(t,{save:false});for(let i=0;i<80;i++)await step(1);
    outputs.push({mode,pose:pose.map(p=>mode==='translated'?[...sub(p.slice(0,3),shift),...p.slice(3)]:p),held:grabs.map(g=>g.gripped)});
   }
   return {rootOnlyMaxError:Math.max(...outputs[0].pose.slice(1).map((p,j)=>norm(sub(p.slice(0,3),outputs[1].pose[j+1].slice(0,3))))),translationMaxError:Math.max(...outputs[0].pose.map((p,j)=>norm(sub(p.slice(0,3),outputs[2].pose[j].slice(0,3))))),held:outputs.map(o=>o.held)};
  });
  const leftDifference=Math.max(...records[0].results[0].left.flatMap((row,i)=>row.map((p,j)=>Math.hypot(...p.slice(0,3).map((v,k)=>v-records[1].results[0].left[i][j][k])))));
  fs.writeFileSync(path.join(out,'verification-full.json'),JSON.stringify({records,independence,leftDifference,errors}));
  assert.equal(records[0].results[0].first[1],null);assert.equal(records[0].results[1].first[1],null);
  assert(records[1].results.every(r=>r.first.every(t=>t!==null)&&r.final.grabs.every(g=>g.gripped)&&r.deterministic));assert(records[1].results[1].fixedContact);
  assert(records[1].maxEval<=18);assert(records[1].maxViolation<1e-12);assert(leftDifference<1e-7);assert(records[1].results[1].maxWristStep<=2.001);assert(independence.rootOnlyMaxError<1e-9&&independence.translationMaxError<1e-5);assert(independence.held.every(h=>h.every(Boolean)));assert.deepEqual(errors,[]);
  global.Recovery=require('../SwordHolsterLab/recovery.js');global.ReachWrist=require('./wrist.js');const samples=records[1].inputs,bench=[];
  for(const [version,source] of [['before',old],['after',current]]){
   vm.runInThisContext(source);for(let i=0;i<2000;i++)ReachCoupled.solve(samples[i%samples.length]);const times=[];
   for(let batch=0;batch<60;batch++){const start=performance.now();for(let i=0;i<100;i++)ReachCoupled.solve(samples[i%samples.length]);times.push((performance.now()-start)/100);}
   times.sort((a,b)=>a-b);bench.push({version,meanMs:times.reduce((a,b)=>a+b,0)/times.length,p95Ms:times[Math.floor(times.length*.95)]});
  }
  const summary={passed:true,records:records.map(r=>({version:r.version,maxEval:r.maxEval,maxViolation:r.maxViolation,results:r.results.map(({left,trace,final,...x})=>({...x,final:final.grabs.map(g=>({held:g.gripped,distance:g.distance,angle:g.angle}))}))})),independence,leftDifference,bench,errors};
  fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(summary,null,2));console.log(JSON.stringify(summary,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
