import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),H=require('./handoff.js'),R=require('./recovery.js'),S=require('./support.js'),Surface=require('./surface.js');
const rig=JSON.parse(fs.readFileSync(new URL('data/rig.json',import.meta.url))),checks=[],cases=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
for(const expected of JSON.parse(fs.readFileSync(new URL('data/root-yaw-zero-hashes.json',import.meta.url)))){
 const model=Surface.prepare(require('./test-bank.cjs').load(expected.gait,.21),{...expected,rootYawSpeed:0});
 check(`shared solver ${expected.gait}/${expected.approach}/${expected.slopeAngle} unchanged`,createHash('sha256').update(JSON.stringify(model.frames)).digest('hex')===expected.hash);
}
const names=['walk-forward-0','walk-forward-30','run-left-300','run-backward--45','walk-right--30'];
for(const name of names){
 const data=JSON.parse(fs.readFileSync(new URL('snapshots/nn-window-'+name+'.json',import.meta.url))),run=K.decode(data,rig.parents);
 const settings={gait:data.gait,direction:data.direction,rootYawSpeed:data.rootYawSpeed,phase:.21,clearance:1,height:16,depth:35,steps:12,terrain:'flat'};
 const flat=K.prepare(run,settings);
 check(name+' flat is exactly the inferred NN orientation, no output spin',flat.frames.every((f,i)=>JSON.stringify(f.pose.q)===JSON.stringify(K.at(run,i/120).q)));
 check(name+' flat feet are not procedurally locked or corrected',flat.frames.every(f=>f.influence===0&&f.feet.every(p=>!p.contact)));
 const stairs=K.prepare(run,{...settings,terrain:'stairs'});
 check(name+' finite stair result',stairs.frames.every(f=>f.pose.points.flat().every(Number.isFinite)));
 const surface=Surface.prepare(run,{...settings,terrain:'incline',slopeAngle:45});
 check(name+' finite surface result with actual turning NN',surface.frames.every(f=>f.pose.points.flat().every(Number.isFinite)));
 for(const [terrain,model] of [['stairs',stairs],['incline',surface]]){
  let drift=0,contacts=0;
  for(const frame of model.frames)for(const foot of frame.feet)if(foot.contact?.localPoint){
   const l=S.leg(frame.pose,run.names,foot.side),point=R.add(frame.pose.points[l.foot],R.rotate(frame.pose.q[l.foot],foot.contact.localPoint));
   drift=Math.max(drift,R.length(R.sub(point,foot.contact.point)));contacts++;
  }
  check(name+'/'+terrain+' material pins retained',contacts>0&&drift<1e-7);
  check(name+'/'+terrain+' shoe clearance and leg reach retained',model.metrics.maxPenetration<1e-4&&model.metrics.maxReachError<1e-6);
 }
 for(const terrain of ['down','uneven'])check(name+'/'+terrain+' finite complete motion',K.prepare(run,{...settings,terrain}).frames.every(f=>f.pose.points.flat().every(Number.isFinite)));
 check(name+' shared Bodyflip API retained',Surface.apiVersion===1&&typeof Surface.createFeet==='function');
 if(!['run-left-300','walk-forward-30'].includes(name))continue;
 const plan=H.requestFor(stairs,run);
 check(name+' has a stair exit handoff',!!plan);
 check(name+' corrected world history is passed without counter-rotation',JSON.stringify(plan.request.seeds[0].axes)===JSON.stringify(stairs.frames[plan.index-4].pose.axes)&&JSON.stringify(plan.request.seeds[1].points)===JSON.stringify(stairs.frames[plan.index].pose.points));
 check(name+' continuation retains Run policy and upcoming yaw',plan.request.policy==='run'&&plan.request.rootYawDegrees.every((v,i)=>Math.abs(v-data.rootYawSpeed*(plan.time+(i-1)/30))<1e-8));
 const response=await fetch('http://127.0.0.1:8890/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...plan.request,verifyReference:true})}),continued=await response.json();assert(response.ok,continued.error);
 check(name+' corrected-history inference matches original NN with turning roots',continued.referenceError<2e-6&&continued.windowReferenceError<2e-6&&continued.pinDiagnostics.mode==='continuous_sigmoid');
 const result=H.apply(stairs,run,plan,continued),decoded=K.decode(continued,run.parents);
 check(name+' terrain prefix and handoff pose unchanged',result.frames.slice(0,plan.index+1).every((f,i)=>f.pose===stairs.frames[i].pose));
 check(name+' after velocity carry orientation is exact NN, without extra yaw',result.frames.slice(plan.index+12).every((f,j)=>{
  const expected=K.at(decoded,(j+12)/120);return f.pose.q.every((q,k)=>Math.abs(R.dot(q,expected.q[k]))>1-1e-6);
 }));
 check(name+' no procedural catch-up on exit',result.frames.slice(plan.index+12).every(f=>f.nn&&f.pose===f.raw&&f.feet.every(p=>p.state==='NN')));
 cases.push({name,handoff:result.handoff,windowError:continued.windowReferenceError,pins:continued.pinDiagnostics});
 fs.writeFileSync(new URL('snapshots/nn-window-handoff-'+name+'.json',import.meta.url),JSON.stringify({request:plan.request,result:continued}));
}
const result={passed:true,checks,cases};fs.writeFileSync(new URL('nn-root-window-integration.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:true,checks:checks.length,cases}));
