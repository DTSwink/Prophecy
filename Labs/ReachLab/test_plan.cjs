// Planned approach regression; the user's desktop session is never controlled.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),vm=require('vm');
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachPlan20261016');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto((process.env.REACH_TEST_URL||'http://127.0.0.1:8873')+'/reach');await page.waitForFunction(()=>reachLab.ready);await page.evaluate(async()=>{setPlaying(false);await settled();drawAll=()=>{};});
  const result=await page.evaluate(async()=>{
   const results=[],samples=[],solve=ReachCoupled.solve,plan=ReachCoupled.plan;let planCalls=0,maxEval=0,maxViolation=0,badGrips=0;
   ReachCoupled.plan=i=>{planCalls++;return plan(i);};
   ReachCoupled.solve=i=>{const r=solve(i);maxEval=Math.max(maxEval,r.evaluations);if(samples.length<60)samples.push(copy(i));return r;};
   const update=ReachGrab.update;ReachGrab.update=(g,h,w,t)=>{const held=g.gripped;update(g,h,w,t);if(!held&&g.gripped&&(g.angle>t.grip||g.distance>=1.25||g.close<1))badGrips++;};
   for(const name of ['TestNN_Right_Recorded','TestNN_Right_Stalled_250','TestNN_Right_Frozen_Start_31']){
    const s=await getJSON('/snapshots/'+name+'.json');await reachLab.restore(s,{save:false});const first=[null,null],trace=[];let maxElbowStep=0,maxWristStep=0,maxLeftSettledStep=0,checkpoint=null;const callsBefore=planCalls;
    const frames=name.endsWith('Recorded')?330:name.endsWith('250')?80:140;
    for(let i=0;i<frames;i++){
     const previous=copy(pose);await step(1);
     for(let k=0;k<2;k++){
      if(grabs[k].gripped&&first[k]===null)first[k]=ticks;
      const q=pose[hands[k]].slice(3),p=ReachWrist.constrain(phat.wrists[k],pose[arms[k][2]].slice(3),q);maxViolation=Math.max(maxViolation,1-Math.abs(dot(q,p)));
     }
     maxElbowStep=Math.max(maxElbowStep,norm(sub(pose[16].slice(0,3),previous[16].slice(0,3))));maxWristStep=Math.max(maxWristStep,norm(sub(pose[17].slice(0,3),previous[17].slice(0,3))));
     if(ticks>=200&&ticks<=300)maxLeftSettledStep=Math.max(maxLeftSettledStep,norm(sub(pose[12].slice(0,3),previous[12].slice(0,3))));
     trace.push({tick:ticks,right:copy(pose[17]),elbow:copy(pose[16]),angle:grabs[1].angle,distance:grabs[1].distance});
     if(i===12)checkpoint=snapshot();
    }
    const final=snapshot(),calls=planCalls-callsBefore;
    await reachLab.restore(checkpoint,{save:false});for(let i=0;i<12;i++)await step(1);const one=snapshot();await reachLab.restore(checkpoint,{save:false});for(let i=0;i<12;i++)await step(1);
    const deterministic=['pose','solverState','grabs'].every(k=>JSON.stringify(one[k])===JSON.stringify(snapshot()[k]));
    results.push({name,first,maxElbowStep,maxWristStep,maxLeftSettledStep,planCalls:calls,deterministic,final:final.grabs.map(g=>({held:g.gripped,distance:g.distance,angle:g.angle})),trace});
   }
   // Unrelated floor-root edits and a change of coordinate origin must not
   // influence the arm plan or subsequent motion.
   const s=await getJSON('/snapshots/TestNN_Right_Stalled_250.json'),outputs=[];
   for(const mode of ['normal','rootOnly','translated']){
    const t=copy(s),shift=[53,-37,21],move=p=>[...add(p.slice(0,3),shift),...p.slice(3)];
    if(mode==='rootOnly'){t.basePose[0]=[87,-64,31,...rotationQ([25,17,63])];t.pose[0]=copy(t.basePose[0]);}
    if(mode==='translated'){
     t.basePose=t.basePose.map(move);t.pose=t.pose.map(move);
     for(let k=0;k<2;k++){
      const g=t.grabs[k];t.settings.hands[k].target=add(t.settings.hands[k].target,shift);g.ball=move(g.ball);
      for(const start of [6+k*3,12+k*3])for(let j=0;j<3;j++)t.solverState[start+j]+=shift[j]*.01;
      if(g.armPlan){g.armPlan.target=add(g.armPlan.target,shift);g.armPlan.shoulder=add(g.armPlan.shoulder,shift);}
     }
    }
    await reachLab.restore(t,{save:false});for(let i=0;i<80;i++)await step(1);
    outputs.push({pose:pose.map(p=>mode==='translated'?[...sub(p.slice(0,3),shift),...p.slice(3)]:p),held:grabs.map(g=>g.gripped)});
   }
   const independence={rootOnlyMaxError:Math.max(...outputs[0].pose.slice(1).map((p,j)=>norm(sub(p.slice(0,3),outputs[1].pose[j+1].slice(0,3))))),translationMaxError:Math.max(...outputs[0].pose.map((p,j)=>norm(sub(p.slice(0,3),outputs[2].pose[j].slice(0,3))))),held:outputs.map(o=>o.held)};
   return {results,maxEval,maxViolation,badGrips,independence,samples,runtimeErrors};
  });
  fs.writeFileSync(path.join(out,'verification-full.json'),JSON.stringify(result));
  assert(result.results.every(r=>r.first.every(t=>t!==null)&&r.final.every(g=>g.held)&&r.deterministic));assert(result.results[0].first[1]<100);
  assert(result.results.every(r=>r.planCalls===2),'One plan per hand; target tracking must not rerun the search');
  assert(result.maxEval<=2);assert(result.maxViolation<1e-12);assert.equal(result.badGrips,0);assert(result.results[1].maxWristStep<=2.001);assert(result.results[0].maxLeftSettledStep<.1);
  assert(result.independence.rootOnlyMaxError<1e-9&&result.independence.translationMaxError<1e-5);assert(result.independence.held.every(h=>h.every(Boolean)));assert.deepEqual(errors,[]);assert.deepEqual(result.runtimeErrors,[]);
  global.Recovery=require('../SwordHolsterLab/recovery.js');global.ReachWrist=require('./wrist.js');const bench=[];
  const oldInputs=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../Saved/Diagnostics/ReachEscape20261016/verification-full.json'))).records[1].inputs;
  for(const [version,file] of [['before',path.join(out,'coupled-before.js')],['after',path.join(__dirname,'coupled.js')]]){
   vm.runInThisContext(fs.readFileSync(file,'utf8'));for(let i=0;i<1000;i++)ReachCoupled.solve(oldInputs[i%oldInputs.length]);const times=[];
   for(let batch=0;batch<30;batch++){const start=performance.now();for(let i=0;i<100;i++)ReachCoupled.solve(oldInputs[i%oldInputs.length]);times.push((performance.now()-start)/100);}
   times.sort((a,b)=>a-b);bench.push({version,meanMs:times.reduce((a,b)=>a+b,0)/times.length,p95Ms:times[Math.floor(times.length*.95)]});
  }
  const summary={passed:true,...result,results:result.results.map(({trace,...r})=>r),samples:undefined,bench,errors};fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(summary,null,2));console.log(JSON.stringify(summary,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
