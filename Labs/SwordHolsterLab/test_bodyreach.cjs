const assert=require('node:assert/strict'),H=require('./holster.js'),B=require('./bodyreach.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),rad=Math.PI/180,I=[0,0,0,1];
const dist=(a,b)=>R.length(R.sub(a,b)),near=(a,b,e=1e-7)=>assert(dist(a,b)<e,`${a} != ${b}`);
const reports=[];
for(const motion of ['idle','walk'])for(const sheathe of [true,false]){
 const m=H.prepare(data,setup,{motion,sheathe,shrinkPercent:35,duration:8});
 const ctx=B.make(data,H.motion(data,motion,0));let prev=[0,0,0];
 assert(m.completionTick!==null,`${motion}/${sheathe} completes`);
 for(const f of m.sourceFrames){
  const base=H.motion(data,motion,f.tick/60);
  for(const j of [0,1,18,19,20,21,22,23,24,25])assert.deepEqual(f.pose[j],base[j],'pelvis/lower body untouched');
  for(let j=1;j<data.parents.length;j++){
   const p=data.parents[j];assert(Math.abs(dist(f.pose[j].p,f.pose[p].p)-dist(base[j].p,base[p].p))<.002,'bone lengths');
  }
  if(!f.body){assert.deepEqual(f.pose,base);continue;}
  const v=f.body.applied;
  assert(Number.isFinite(v[0]),'finite unrestricted spine twist');
  assert(Math.abs(v[0]-prev[0])<=90*rad/60+1e-9,'spine twist speed cap');
  assert(Math.hypot(v[1],v[2])<=45*rad+1e-9,'clavicle swing limit');
  assert(Math.hypot(v[1]-prev[1],v[2]-prev[2])<=90*rad/60+1e-9,'clavicle swing speed cap');
  const worldAxis=R.rotate(base[ctx.top].q,ctx.spineAxis);
  for(const [k,j] of ctx.spine.entries()){
   const delta=R.qm(f.pose[j].q,R.qinv(base[j].q));
   assert(H.angle(delta,R.qexp(R.mul(worldAxis,v[0]*(k+1)/5)))<1e-5,'net 20/40/60/80/100% signed-angle delta');
   // Removing only the additive turn recovers this frame's moving base orientation.
   near(R.rotate(R.qinv(delta),R.rotate(f.pose[j].q,[1,0,0])),R.rotate(base[j].q,[1,0,0]));
  }
  const topDelta=R.qm(R.qinv(base[ctx.top].q),f.pose[ctx.top].q);
  near(R.rotate(topDelta,ctx.spineAxis),ctx.spineAxis); // Pure spine twist: no added bend.
  const parent=data.parents[ctx.clav],inherited=R.qm(f.pose[parent].q,R.qinv(base[parent].q));
  const clavDelta=R.qm(R.qinv(R.qm(inherited,base[ctx.clav].q)),f.pose[ctx.clav].q);
  assert(Math.abs(R.dot(clavDelta.slice(0,3),R.cross(...ctx.clavBasis)))<1e-10,'no clavicle axial twist');
  if(f.body.remainingDegrees<=.25)assert(f.body.shoulderDistance<=f.body.baseShoulderDistance+.1,'reduces extension');
  prev=v;
 }
 const grip=m.frames.find(f=>f.phase==='Slide');assert(grip);
 if(!sheathe)assert(grip.body.remainingDegrees<=.25,'drawing waits for turn');
 const stable=m.frames.find(f=>f.body?.remainingDegrees<=.25)||grip;
 reports.push({motion,sheathe,gripTick:grip.tick,completionTick:m.completionTick,baseDistance:stable.body.baseShoulderDistance,assistedDistance:stable.body.shoulderDistance});
 assert.deepEqual(H.sample(m,.8),H.sample(H.prepare(data,setup,m.o),.8),'deterministic');
}
// Slow body + near-instant hand: reaching the grip alone must never start drawing.
const slow=H.prepare(data,setup,{sheathe:false,maxReachSpeed:10000,maxReachRotationSpeed:10000,maxSpineClavicleAngularSpeed:10,duration:30});
assert(slow.frames.some(f=>f.phase==='Reach'&&f.handError<=2&&f.body.remainingDegrees>1),'hand waits at grip');
const grip=slow.frames.find(f=>f.phase==='Slide');assert(grip&&grip.body.remainingDegrees<=.25);
// A held-out perturbation of both swing axes must not significantly improve the fitted shoulder.
const base=H.motion(data,'idle',1),ctx=B.make(data,base),target=slow.frames[60].body.clearTarget;
// World-Z turning is allowed: only rotation around the clavicle's own length is excluded.
const localZ=R.rotate(R.qinv(base[ctx.clav].q),[0,0,1]);
const yaw=[0,...ctx.clavBasis.map(axis=>R.dot(axis,localZ)*20*rad)];
const yawPose=B.apply(ctx,base,yaw),worldClavDelta=R.qm(yawPose[ctx.clav].q,R.qinv(base[ctx.clav].q));
assert(Math.abs(R.qlog(worldClavDelta)[2])>.1,'clavicle retains world-Z turning');
assert(Math.hypot(...R.sub(yawPose[ctx.shoulder].p,base[ctx.shoulder].p).slice(0,2))>1,'world-Z turn moves shoulder horizontally');
const optimum=B.optimize(ctx,base,target,[0,0,0],45),best=dist(B.apply(ctx,base,optimum,true),target);
for(let k=0;k<3;k++)for(const sign of [-1,1]){
 const v=[...optimum];v[k]+=sign*.1*rad;
 if(Math.hypot(v[1],v[2])>45*rad)continue;
 assert(dist(B.apply(ctx,base,v,true),target)>=best-.002,'bounded shoulder-distance optimum');
}
// High underlying gaze must not cap spine correction at the clavicle limit.
const gazeBase=H.motion(data,'idle',1.479,162),gazeCtx=B.make(data,H.motion(data,'idle',0,162));
const full=H.compose(setup.seated,H.compose(setup.holster,gazeBase[data.names.indexOf('pelvis')]));
const gazeTarget=H.handForTip(setup,.85,H.bladeTip(setup),H.point(full,setup.baseBladeLocal),full.q).p;
let gazeFit=[0,0,0];for(let i=0;i<5;i++)gazeFit=B.optimize(gazeCtx,gazeBase,gazeTarget,gazeFit,45);
assert(Math.abs(gazeFit[0])>90*rad,'spine can undo large gaze rotations');
assert(Math.hypot(gazeFit[1],gazeFit[2])<=45*rad+1e-9,'clavicle retains its angle cap');
const gazeDistance=dist(B.apply(gazeCtx,gazeBase,gazeFit,true),gazeTarget);assert(gazeDistance<44,'formerly 58.57 cm capped snapshot target is reachable');
const zeroClav=B.optimize(gazeCtx,gazeBase,gazeTarget,gazeFit,0);assert(Math.abs(zeroClav[0])>45*rad);assert.equal(Math.hypot(zeroClav[1],zeroClav[2]),0);
for(const sign of [-1,1]){
 const before=B.apply(gazeCtx,gazeBase,[sign*179.99*rad,0,0]),after=B.apply(gazeCtx,gazeBase,[sign*180.01*rad,0,0]);
 for(const j of gazeCtx.spine)assert(H.angle(before[j].q,after[j].q)<.021,'distributed twist stays continuous through 180 degrees');
}
console.log(JSON.stringify({passed:true,cases:reports,slowGripTick:grip.tick,gazeFitDegrees:gazeFit.map(v=>v/rad),gazeDistance},null,2));
