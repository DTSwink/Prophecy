// Independent contact-yaw regression: cached real NN clips, no server/inference.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),Surface=require('./surface.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),rig=read('data/rig.json');
const deg=180/Math.PI,clamp=x=>Math.max(-1,Math.min(1,x)),distance=(a,b)=>R.length(R.sub(a,b));
const checks=[],failures=[],cases=[],synthetic=[];
const check=(name,ok,detail)=>{checks.push(name);if(!ok)failures.push({name,detail});};
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*deg;
const heading=(p,l,n=[0,1,0])=>{const f=S.footFrame(p,l.foot,l.toe,l.side);return R.unit(R.cross(n,R.cross(f.forward,f.up)));};
const headingError=(p,l,n=[0,1,0])=>{const h=heading(p,l,n),body=R.rotate(p.q[l.pelvis],[0,-1,0]),wanted=R.unit(R.sub(body,R.mul(n,R.dot(body,n))));return Math.atan2(R.dot(n,R.cross(h,wanted)),R.dot(h,wanted))*deg;};
function pole(p,l){const axis=R.unit(R.sub(p.points[l.foot],p.points[l.hip])),v=R.sub(p.points[l.knee],p.points[l.hip]),bend=R.sub(v,R.mul(axis,R.dot(axis,v))),q=R.qinv(p.q[l.pelvis]);return {axis:R.rotate(q,axis),pole:R.rotate(q,R.unit(bend)),arm:R.length(bend)};}
function poleStep(a,b){const p=R.rotate(R.fromTo(a.axis,b.axis),a.pole);return Math.atan2(R.dot(R.cross(p,b.pole),b.axis),R.dot(p,b.pole))*deg;}
function inspect(label,data,settings,kind='stairs'){
 const run=K.decode(data,rig.parents),source=JSON.stringify(run.poses),m=(kind==='incline'?Surface:K).prepare(run,{...settings,terrain:kind});
 const out={label,kind,...m.metrics,maxMaterialError:0,maxRetainedPivotDrift:0,maxFootRotationStep:0,maxPoleStep:0,maxPoleAcceleration:0,maxPoleError:0,pinPairs:0,pivotTransfers:0,pureNNFrames:0,alteredPureNNFrames:0,maxBodyYaw:0};
 const priorPoleStep=[0,0];
 for(let i=0;i<m.frames.length;i++){
  const f=m.frames[i];
  if(f.influence===0){out.pureNNFrames++;if(JSON.stringify(f.pose)!==JSON.stringify(f.raw))out.alteredPureNNFrames++;}
  for(let side=0;side<2;side++){
   const l=S.leg(f.raw,run.names,side?'R':'L'),c=f.feet[side].contact,p=f.pose;
   if(c?.localPoint){
    out.maxMaterialError=Math.max(out.maxMaterialError,distance(R.add(p.points[l.foot],R.rotate(p.q[l.foot],c.localPoint)),c.point));
    out.maxBodyYaw=Math.max(out.maxBodyYaw,Math.abs(headingError(p,l,c.normal||[0,1,0])));
   }
   if(!i)continue;
   const prev=m.frames[i-1],old=prev.feet[side].contact;
   out.maxFootRotationStep=Math.max(out.maxFootRotationStep,angle(p.q[l.foot],prev.pose.q[l.foot]));
   if(c?.localPoint&&old?.localPoint&&old.stanceId===c.stanceId){
    // Compare the actual same material point across poses, not newly reported
    // local points that could make a sliding pin look exact by construction.
    if(distance(c.localPoint,old.localPoint)<1e-6){
     out.pinPairs++;
     const material=R.add(p.points[l.foot],R.rotate(p.q[l.foot],old.localPoint));
     out.maxRetainedPivotDrift=Math.max(out.maxRetainedPivotDrift,distance(material,old.point));
    }else out.pivotTransfers++;
   }
   const a=pole(prev.pose,l),b=pole(p,l),nn=pole(f.raw,l),step=poleStep(a,b);
   if(kind==='stairs'&&f.influence===1&&prev.influence===1&&a.arm>.02&&b.arm>.02){
    out.maxPoleStep=Math.max(out.maxPoleStep,Math.abs(step));
    if(i>1&&m.frames[i-2].influence===1)out.maxPoleAcceleration=Math.max(out.maxPoleAcceleration,Math.abs(step-priorPoleStep[side]));
    out.maxPoleError=Math.max(out.maxPoleError,Math.acos(clamp(R.dot(b.pole,R.rotate(R.fromTo(nn.axis,b.axis),nn.pole))))*deg);
   }
   priorPoleStep[side]=step;
  }
 }
 check(label+'/'+kind+' finite complete clip',m.frames.every(f=>f.pose.points.flat().every(Number.isFinite)));
 check(label+'/'+kind+' pureNN frames untouched',out.alteredPureNNFrames===0,out.alteredPureNNFrames);
 check(label+'/'+kind+' rawNN immutable',source===JSON.stringify(run.poses));
 check(label+'/'+kind+' exact material pin',out.maxMaterialError<1e-7,out.maxMaterialError);
 check(label+'/'+kind+' retained material point does not slide',out.maxRetainedPivotDrift<1e-6,out.maxRetainedPivotDrift);
 check(label+'/'+kind+' complete shoe clears terrain',m.metrics.maxPenetration<(kind==='incline'?1e-4:1e-5),m.metrics.maxPenetration);
 check(label+'/'+kind+' reachable legs',m.metrics.maxReachError<1e-6,m.metrics.maxReachError);
 const saved=JSON.stringify(m.sample(67/60));m.sample(4.4);m.sample(.2);
 check(label+'/'+kind+' reverse seeks deterministic',JSON.stringify(m.sample(67/60))===saved);
 if(label==='phase91'&&kind==='stairs'){
  const f=m.sample(67/60),l=S.leg(f.pose,run.names,'R'),release=m.frames.slice(0,135).findLastIndex(q=>!!q.feet[1].contact),retained=m.frames[release];
  out.frame67={state:f.feet[1].state,yaw:headingError(f.pose,l),contact:f.feet[1].contact};
  out.lastRetainedRight={frame:release/2,yaw:headingError(retained.pose,l),contact:retained.feet[1].contact};
  // A finite riser needs departure room: contact may release before the old
  // diagnostic frame. Verify the actual final contact, not a frozen timestamp.
  check('67 prepares swing after finite-riser contact release',release>0&&release<134&&f.feet[1].state==='SWING'&&retained.feet[1].state==='ROLL');
  check('all retained shoes stay within planted yaw allowance',out.maxBodyYaw<45.5,out.maxBodyYaw);
  check('phase91 fullIK knee pole speed',out.maxPoleStep<2,out.maxPoleStep);
  check('phase91 fullIK knee pole acceleration',out.maxPoleAcceleration<.4,out.maxPoleAcceleration);
  check('phase91 poles follow transported NN',out.maxPoleError<4,out.maxPoleError);
  check('phase91 no new ankle snap',out.maxFootRotationStep<10,out.maxFootRotationStep);
 }
 cases.push(out);return {run,m};
}
const fixture=read('snapshots/ankle-turn-second-source.json'),settings=read('snapshots/ankle-turn-second-settings.json');
const current=inspect('phase91',fixture,settings);
inspect('phase21',read('snapshots/ankle-turn-source.json'),read('snapshots/ankle-turn-settings.json'));
for(const name of ['walk-forward-30','run-left-300','run-backward--45','walk-right--30']){
 const data=read('snapshots/nn-window-'+name+'.json'),s={gait:data.gait,direction:data.direction,rootYawSpeed:data.rootYawSpeed,phase:.21,clearance:1,height:16,depth:35,steps:12};
 inspect(name,data,s,'flat');inspect(name,data,s,'stairs');inspect(name,data,{...s,slopeAngle:45},'incline');
}
// A realistic rigid shoe/ball geometry, held on one material feature while the
// pelvis turns through >360deg then stops. Inclined normal exercises tangent yaw.
const p0=current.run.poses[0];
function plantRotation(p,l,normal,pitch){
 const body=R.rotate(p.q[l.pelvis],[0,-1,0]),f=R.unit(R.sub(body,R.mul(normal,R.dot(body,normal)))),right=R.unit(R.cross(normal,f)),a=pitch/deg;
 const forward=R.add(R.mul(f,Math.cos(a)),R.mul(normal,Math.sin(a))),up=R.add(R.mul(normal,Math.cos(a)),R.mul(f,-Math.sin(a))),target=R.fromAxes([right,up,forward]),frame=S.footFrame(p,l.foot,l.toe,l.side);
 const align=(q,f,u)=>R.qm(R.qm(target,R.qinv(R.fromAxes([R.unit(R.cross(u,f)),u,f]))),q);
 return {footQ:align(l.footQ,frame.forward,frame.up),toeQ:align(l.toeQ,frame.toeForward,frame.toeUp)};
}
for(const normal of [[0,1,0],R.unit([.4,1,-.3])])for(const side of ['L','R'])for(const pitch of [-25,25,0,4]){
 const l=S.leg(p0,current.run.names,side),rotation=plantRotation(p0,l,normal,pitch),shape=K.geometry(p0,l,rotation),low=Math.min(...shape.map(v=>R.dot(v,normal))),lowest=shape.filter(v=>R.dot(v,normal)<low+1e-8),offset=R.mul(lowest.reduce((a,b)=>R.add(a,b),[0,0,0]),1/lowest.length),foot=R.sub([.25,.8,-.5],offset),contact=R.add(foot,offset);
 const sample={foot,contact,rotation,localPoint:R.rotate(R.qinv(rotation.footQ),offset)},q=rotation.footQ,f=R.rotate(q,[0,Math.sign(l.toeLocal[1])||1,0]),up=R.rotate(q,[side==='L'?1:-1,0,0]),start=R.unit(R.cross(normal,R.cross(f,up))),body=R.rotate(p0.q[l.pelvis],[0,-1,0]);
 const apply=K.createPinYaw(normal,45),label=side+'/'+pitch+'/'+normal.join(','),actualCentre=R.mul([0,2,4,6].reduce((a,j)=>R.add(a,shape[j]),[0,0,0]),.25),centreLocal=R.rotate(R.qinv(q),actualCentre);
 let maxPivotDrift=0,maxCenterDrift=0,maxTransferDrift=0,maxPlaneShift=0,maxStep=0,maxStopDrift=0,maxStopGrowth=0,center=null,prior=null,firstTurn=null,final=null,heldMaterial=null,heldPoint=null;
 for(let tick=0;tick<340;tick++){
  const yaw=Math.min(tick,240)*3,desired=R.rotate(R.qexp(R.mul(normal,yaw/deg)),start),p={...p0,q:p0.q.slice()};p.q[l.pelvis]=R.qm(R.fromTo(body,desired),p0.q[l.pelvis]);
  const out=apply(sample,p,l),point=R.add(out.foot,R.rotate(out.rotation.footQ,sample.localPoint)),centre=R.add(out.foot,R.rotate(out.rotation.footQ,centreLocal));
  if(pitch===0){center??=centre;maxCenterDrift=Math.max(maxCenterDrift,distance(center,centre));}
  if(Math.abs(pitch)>=8)maxPivotDrift=Math.max(maxPivotDrift,distance(point,contact));
  if(pitch===4&&Math.abs(out.yaw||0)>1e-6){
   heldMaterial??=out.localPoint;heldPoint??=out.contact;
   maxTransferDrift=Math.max(maxTransferDrift,distance(R.add(out.foot,R.rotate(out.rotation.footQ,heldMaterial)),heldPoint));
  }
  maxPlaneShift=Math.max(maxPlaneShift,Math.abs(R.dot(R.sub(point,contact),normal)));
  if(prior)maxStep=Math.max(maxStep,angle(out.rotation.footQ,prior.rotation.footQ));
  if(tick===300)firstTurn=out;
  if(tick>300)maxStopDrift=Math.max(maxStopDrift,distance(out.foot,firstTurn.foot));
  if(tick>240&&prior)maxStopGrowth=Math.max(maxStopGrowth,Math.abs(out.yawError)-Math.abs(prior.yawError));
  prior=out;final=out;
 }
 const still={...p0,q:p0.q.slice()};still.q[l.pelvis]=R.qm(R.fromTo(body,start),p0.q[l.pelvis]);
 check(label+' no correction inside yaw allowance',K.createPinYaw(normal,45)(sample,still,l)===sample);
 const turned={...p0,q:p0.q.slice()},over=R.rotate(R.qexp(R.mul(normal,120/deg)),start);turned.q[l.pelvis]=R.qm(R.fromTo(body,over),p0.q[l.pelvis]);
 const blocked=K.createPinYaw(normal,45)(sample,turned,l,()=>false);
 check(label+' blocked yaw cannot move shoe or pivot',blocked.blocked&&distance(blocked.foot,sample.foot)<1e-10&&angle(blocked.rotation.footQ,sample.rotation.footQ)<1e-5);
 check(label+' yaw bounded after settling',Math.abs(final.yawError)<45.0001,final.yawError);
 check(label+' heel/toe material anchor invariant',maxPivotDrift<1e-7,maxPivotDrift);
 check(label+' flat sole center invariant',maxCenterDrift<1e-7,maxCenterDrift);
 check(label+' nearflat transferred material pivot invariant',maxTransferDrift<1e-7,maxTransferDrift);
 check(label+' no normal-axis shoe displacement',maxPlaneShift<1e-7,maxPlaneShift);
 check(label+' yaw step bounded at600deg/s',maxStep<5.0001,maxStep);
 check(label+' after stop soft-limit settling is monotonic around same pin',maxStopGrowth<1e-8,maxStopGrowth);
 synthetic.push({label,maxPivotDrift,maxCenterDrift,maxTransferDrift,maxPlaneShift,maxStep,maxStopDrift,maxStopGrowth,finalYaw:final.yawError});
}
const result={passed:!failures.length,checks:checks.length,failures,cases,synthetic};
fs.writeFileSync(new URL('snapshots/yaw-knee-regression.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
assert.equal(failures.length,0,JSON.stringify(failures));
