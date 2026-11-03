'use strict';
// Wall-entry rotation/arrival reproduction: recorded causal NN replies,
// no inference or live edits. Also covers the following slide transition.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),z=require('node:zlib'),Module=require('node:module');
const R=require('./recovery.js'),S=require('./support.js'),K=require('./footik.js'),C=require('./surface-coupling.js'),J=require('./slide-joints.js'),Bank=require('./test-bank.cjs');
const dir=path.resolve(process.argv[2]||path.join(__dirname,'../../Saved/Diagnostics/FootIKWall20261103'));
const read=n=>JSON.parse(z.gunzipSync(fs.readFileSync(path.join(dir,n))));
let checks=0;const check=(v,message)=>{assert.ok(v,message);checks++;};
function axialStep(m){
 const knee=m.names.indexOf('calf_l'),foot=m.names.indexOf('foot_l');let maximum=0;
 for(let i=36;i<=56;i++){const p=m.frames[i].pose,b=m.frames[i-1].pose,axis=R.unit(R.sub(b.points[foot],b.points[knee])),w=R.qlog(R.qm(p.q[knee],R.qinv(b.q[knee])));maximum=Math.max(maximum,Math.abs(R.dot(w,axis))*180/Math.PI);}
 return maximum;
}
function wallAngle(m,frame){const p=m.frames[frame*2].pose,f=S.footFrame(p,m.names.indexOf('foot_r'),m.names.indexOf('ball_r'),'R');return Math.acos(Math.max(-1,Math.min(1,R.dot(f.up,[0,0,-1]))))*180/Math.PI;}
function thighMotion(m){
 const j=m.names.indexOf('thigh_r'),velocity=i=>R.mul(R.qlog(R.qm(m.frames[i].pose.q[j],R.qinv(m.frames[i-1].pose.q[j]))),120*180/Math.PI);
 let step=0,velocityChange=0;for(let i=24;i<=42;i++){const v=velocity(i);step=Math.max(step,R.length(v)/120);velocityChange=Math.max(velocityChange,R.length(R.sub(v,velocity(i-1))));}
 return {step,velocityChange};
}
(async()=>{
 const before=read('entry-before.model.json.gz'),arrivalBefore=read('thigh-final.model.json.gz'),after=read('arrival-final.model.json.gz'),fixture=read('arrival-final.fixture.json.gz'),joints=J.build(undefined,after.names,after.parents);
 const oldThigh=thighMotion(arrivalBefore),newThigh=thighMotion(after);
 check(newThigh.step<oldThigh.step*.75,'Wall-approach thigh speed reduced without shifting the peak outside the measured approach');
 check(newThigh.velocityChange<oldThigh.velocityChange*.5,'Thigh no longer reverses as abruptly at contact');
 const firstPin=m=>m.frames.findIndex((f,i)=>i>24&&f.feet[1].contact?.surface==='incline'),pinTicks=m=>m.frames.slice(24,43).filter(f=>f.feet[1].contact?.surface==='incline').length;
 check(firstPin(after)===firstPin(arrivalBefore)&&pinTicks(after)>=pinTicks(arrivalBefore),'Smoothing keeps first contact timing and does not sacrifice the pin');
 const oldAxial=axialStep(before),newAxial=axialStep(after);
 check(newAxial<1.1&&newAxial<oldAxial*.1,'No axial calf flip through F18-28');
 check(wallAngle(after,16)<35&&wallAngle(after,16)<wallAngle(before,16)-35,'Right shoe prepares for the wall before contact');
 let ankleError=0,drift=0,contacts=0;
 for(const f of after.frames){
  check(f.pose.points.flat().every(Number.isFinite)&&f.pose.q.flat().every(Number.isFinite),'Finite pose');
  if(!f.slide)for(const side of ['l','r']){const j=after.names.indexOf('foot_'+side),k=after.parents[j];ankleError=Math.max(ankleError,joints.project(j,f.pose.q[k],f.pose.q[j]).correctionRad-joints.project(j,f.raw.q[k],f.raw.q[j]).correctionRad);}
  for(const foot of f.feet)if(foot.contact){const j=after.names.indexOf('foot_'+foot.side.toLowerCase()),c=foot.contact;contacts++;drift=Math.max(drift,R.length(R.sub(R.add(f.pose.points[j],R.rotate(f.pose.q[j],c.localPoint)),c.point)));}
 }
 check(ankleError<1e-6,'Earlier alignment retains the actual ankle limits');
 check(contacts>0&&drift<1e-8,'Material heel/toe pin remains exact');
 const run=K.decode(fixture.request.source,after.parents),make=()=>C.createSession(run,fixture.request.settings,async(_,i)=>{assert.ok(fixture.response.steps[i],'Missing recorded NN reply');return fixture.response.steps[i];}),whole=make(),split=make();
 try{
  await whole.extend(fixture.request.endTime);
  for(const time of [.1,.25,.33,.4,fixture.request.endTime])await split.extend(time);
  assert.deepEqual(whole.model.frames,split.model.frames);checks++;
  assert.deepEqual(JSON.parse(JSON.stringify(whole.model.frames)),after.frames);checks++;
 }finally{whole.close();split.close();}
 // The shared yaw helper's optional explicit heading must leave its existing
 // ordinary flat/stair/down and disabled callers exactly unchanged.
 const old=new Module(path.join(__dirname,'footik-before-entry-test.js'),module);old.filename=path.join(__dirname,'footik-before-entry-test.js');old.paths=module.paths;old._compile(fs.readFileSync(path.join(dir,'before-footik.js'),'utf8'),old.filename);
 for(const gait of ['walk','run']){const bank=Bank.load(gait,.21);for(const terrain of ['flat','stairs','down']){assert.deepEqual(K.prepare(bank,{gait,terrain}).frames,old.exports.prepare(bank,{gait,terrain}).frames);checks++;}assert.deepEqual(K.prepare(bank,{gait,enabled:false}).frames,old.exports.prepare(bank,{gait,enabled:false}).frames);checks++;}
 const decoder=JSON.parse(fs.readFileSync(path.join(dir,'entry-decoder-check.json'),'utf8'));
 check(decoder.passed&&decoder.maxPositionErrorM===0&&decoder.maxPredictedAxesError===0&&decoder.recurrenceExact&&decoder.sharedContractUnchanged,'Signed calf output preserves predicted pose and recurrent policy');
 const slideStart=m=>m.frames.findIndex(f=>f.slide);
 check(slideStart(after)===slideStart(arrivalBefore),'Same slide entry frame');
 let handAcceleration=0;
 for(const side of ['l','r'])for(let i=126;i<=176;i++){const j=after.names.indexOf('hand_'+side),relative=k=>R.sub(after.frames[k].pose.points[j],after.frames[k].pose.points[1]);handAcceleration=Math.max(handAcceleration,R.length(R.add(R.sub(relative(i),R.mul(relative(i-1),2)),relative(i-2)))*120**2);}
 check(handAcceleration<20,'Accepted slide-hand motion has no renewed F67/F85 kick');
 const report={passed:true,checks,frames:after.frames.length,thigh:{before:oldThigh,after:newThigh},firstWallPinFrame:firstPin(after)/2,pinTicks:{before:pinTicks(arrivalBefore),after:pinTicks(after)},oldAxialStepDeg:oldAxial,newAxialStepDeg:newAxial,rightSoleAngleAt16:{before:wallAngle(before,16),after:wallAngle(after,16)},addedAnkleLimitDeg:ankleError*180/Math.PI,pinDriftM:drift,handAcceleration,decoder};
 fs.writeFileSync(path.join(dir,'arrival-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
