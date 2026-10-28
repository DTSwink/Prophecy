import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),H=require('./handoff.js'),R=require('./recovery.js'),S=require('./support.js'),{load}=require('./test-bank.cjs');
const endpoint=process.env.FOOTIK_TEST_URL||'http://127.0.0.1:8878',checks=[],cases=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
async function resume(request){const r=await fetch(endpoint+'/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)}),data=await r.json();if(!r.ok)throw Error(data.error);return data;}
const settings=JSON.parse(fs.readFileSync(new URL('data/run-travel-before.json',import.meta.url))).settings;
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
for(const gait of ['run','walk']){
 const run=load(gait,.21),base=K.prepare(run,{...settings,gait}),plan=H.requestFor(base,run);
 check(gait+' has a clearance-driven handoff on a 60Hz game frame',!!plan&&plan.index%2===0);
 check(gait+' seeds the corrected current and exactly 1/30s previous pose',JSON.stringify(plan.request.seeds[0].points)===JSON.stringify(base.frames[plan.index-4].pose.points)&&JSON.stringify(plan.request.seeds[1].points)===JSON.stringify(base.frames[plan.index].pose.points));
 const data=await resume({...plan.request,verifyReference:true}),model=H.apply(base,run,plan,data);
 check(gait+' uses genuine recurrent lower and upper inference, verified against original controller',data.inferences===plan.request.frames-1&&data.referenceError<2e-6&&data.seedLower.length===2&&data.seedUpper.length===2);
 check(gait+' preserves every pre-handoff frame and the exact current pose',model.frames.slice(0,plan.index).every((f,i)=>f===base.frames[i])&&model.frames[plan.index].pose===base.frames[plan.index].pose);
 check(gait+' gives both feet to NN without later procedural catch-up',model.frames.slice(plan.index).every(f=>f.nn&&f.feet.every(p=>p.state==='NN'&&!p.contact)));
 const blendEnd=plan.index+Math.ceil(model.handoff.blendSeconds*model.fps);
 check(gait+' transition finishes on the newly inferred pose exactly',model.frames.slice(blendEnd).every(f=>f.pose===f.raw));
 let maxAngle=0,maxBoneError=0,maxRiserPenetration=0,maxRootError=0;
 for(let i=plan.index;i<model.frames.length;i++){
  const f=model.frames[i];
  for(const a of [...f.pose.points,...f.pose.q])assert(a.every(Number.isFinite),'Nonfinite inferred pose');
  const expected=R.add(plan.request.roots[1],R.mul(R.sub(plan.request.roots[2],plan.request.roots[1]),(i-plan.index)*30/model.fps));
  maxRootError=Math.max(maxRootError,R.length(R.sub(f.root,expected)));
  for(let j=1;j<run.names.length;j++){
   // The NN position decoder itself varies calf length by a few millimetres
   // (also present in the uncorrected walk bank). The handoff must not add
   // stretch beyond the newly inferred source geometry at this same frame.
   const p=run.parents[j];if(j>1)maxBoneError=Math.max(maxBoneError,Math.abs(R.length(R.sub(f.pose.points[j],f.pose.points[p]))-R.length(R.sub(f.raw.points[j],f.raw.points[p]))));
   if(i>plan.index)maxAngle=Math.max(maxAngle,angle(f.pose.q[j],model.frames[i-1].pose.q[j]));
  }
  for(const side of ['L','R']){
   const l=S.leg(f.pose,run.names,side),p=f.pose.points[l.foot],shape=S.footPoints(f.pose,l.foot,l.toe,side);
   if(shape.some(o=>p[2]+o[2]<model.terrain.end))maxRiserPenetration=Math.max(maxRiserPenetration,model.terrain.floorFor(p,shape)-p[1]);
  }
 }
 check(gait+' retains commanded root speed and level',maxRootError<1e-4);
 check(gait+' preserves inferred bone lengths and has no angular pop',maxBoneError<1e-5&&maxAngle<20);
 check(gait+' clears remaining risers during the NN handoff',maxRiserPenetration<1e-5);
 check(gait+' reverse seek is deterministic',Array.from({length:30},(_,j)=>(model.duration-j/60)).every(t=>model.sample(t)===model.frames[Math.round(t*model.fps)]));
 const difference=R.length(R.sub(model.sample((plan.time+.3)).pose.points[20],base.sample(plan.time+.3).raw.points[20]));
 check(gait+' continuation is not the old cached trajectory',difference>.005);
 if(gait==='run'){
  check('Current run hands off at73 rather than waiting until94',plan.time*60===73);
  const changed=JSON.parse(JSON.stringify(plan.request));changed.seeds[0].points.slice(1).forEach(p=>p[0]+=.01);
  const history=await resume(changed),historyDifference=Math.max(...data.poses[1].points.flatMap((p,j)=>p.map((v,k)=>Math.abs(v-history.poses[1].points[j][k]))));
  check('Changing only previous-pose history changes the first true NN prediction',historyDifference>1e-5);
  const repeated=await resume({...plan.request,verifyReference:true});
  check('Replay cache requires identical seed history and returns identical inference',repeated.cache==='identical-seed'&&JSON.stringify(repeated.poses)===JSON.stringify(data.poses));
 }
 cases.push({gait,...model.handoff,maxAngle,maxBoneError,maxRiserPenetration,maxRootError,difference});
}
const run=load('run',.21);let calls=0;
await H.prepare(run,{...settings,terrain:'flat'},()=>{calls++;});
await H.prepare(run,{...settings,enabled:false},()=>{calls++;});
check('Flat-only and disabled IK perform no continuation inference',calls===0);
let rejected=false;try{await H.prepare(run,settings,()=>{throw Error('worker unavailable');});}catch{rejected=true;}
check('Inference failure is surfaced rather than disguised as cached-gait handoff',rejected);
const cancelled=await H.prepare(run,settings,()=>Promise.resolve(null),()=>true);
check('Obsolete preparation cannot overwrite a newer scene',cancelled===null);
const result={passed:true,checks,cases};fs.writeFileSync(new URL('handoff-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
