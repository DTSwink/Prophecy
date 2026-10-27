import fs from 'node:fs';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js'),H=require('./attack-inertia.js'),K=require('./airborne-motion.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),{names,parents,...manifest}=read('data/manifest.json'),reference=C.poseFromShared({...manifest,names,parents}),metadata=read('data/vanilla.json');
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),distance=(a,b)=>R.length(R.sub(a,b)),results=[];
for(const name of ['KickL','KickR']){
 const meta=metadata.clips.find(c=>c.name===name),bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),clip=C.decode(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),names,parents);
 const motion=K.recording({clip,names,parents,reference});let strikeRoot=names.indexOf(C.effector(name));while(parents[strikeRoot]!==names.indexOf('pelvis'))strikeRoot=parents[strikeRoot];const preserve=[{bone:strikeRoot,weight:motion.strikeWeight}],options={source:motion.sample,names,parents,reference,duration:motion.stop+1.2,strikeRoot,strikeWeight:motion.strikeWeight},start=performance.now(),plan=K.createBalanced(options);plan.sample(plan.duration);const buildMs=performance.now()-start,legacy=K.create({...options,preserve});
 const hinges=H.legHinges(names,reference),sourceLocals=clip.poses.map(p=>R.localize(p.points,p.q,parents));
 const adjusted=new Set(hinges.flatMap(h=>[h.hip,h.knee,h.foot])),pelvis=names.indexOf('pelvis'),referenceLocal=R.localize(reference.points,reference.q,parents);
 const strike=hinges.find(h=>h.hip===strikeRoot),free=hinges.find(h=>h.hip!==strikeRoot),changed=new Set([strikeRoot,free.hip,free.knee,names.indexOf('spine_01'),names.indexOf('upperarm_l'),names.indexOf('upperarm_r')]);let maxStrikeDirectionError=0,maxStrikeOrientationError=0,maxPelvisAngle=0,maxLegacyPelvisAngle=0,maxAddedKneeAcceleration=0,maxLateral=0;const offsets=[];
 let maxJointError=0,maxSocketError=0,maxCOMError=0,maxKeyError=0,maxFootPathError=0,maxAnkleError=0,minKnee=Infinity,maxKnee=0,maxHingeError=0,rawH2=0,airH2=0,maxFineResidual=0,samples=0;
 for(let f=0;f<clip.poses.length;f++){
  const local=R.localize(motion.at(f).points,motion.at(f).q,parents);
  for(let i=2;i<names.length;i++)if(!adjusted.has(i))maxKeyError=Math.max(maxKeyError,angle(local.q[i],sourceLocals[f].q[i]));
  const a=motion.at(f),b=clip.poses[f];for(const h of hinges){for(const j of [h.knee,h.foot]){const x=R.rotate(R.qinv(a.q[pelvis]),R.sub(a.points[j],a.points[h.hip])),y=R.rotate(R.qinv(b.q[pelvis]),R.sub(b.points[j],b.points[h.hip]));maxFootPathError=Math.max(maxFootPathError,distance(x,y));}maxAnkleError=Math.max(maxAnkleError,angle(R.qm(R.qinv(a.q[pelvis]),a.q[h.foot]),R.qm(R.qinv(b.q[pelvis]),b.q[h.foot])));}
 }
 let last=null,lastRaw=null;
 for(let t=0;t<=plan.duration;t+=1/240){
  const a=plan.sample(t),b=plan.uncorrected(t),la=R.localize(a.points,a.q,parents),lb=R.localize(b.points,b.q,parents),bodies=H.bodies(a,plan.rig),rawBodies=H.bodies(b,plan.rig);
  maxCOMError=Math.max(maxCOMError,distance(K.center(bodies,plan.rig),plan.center));
  for(let i=1;i<names.length;i++){if(i!==pelvis&&!changed.has(i))maxJointError=Math.max(maxJointError,angle(la.q[i],lb.q[i]));maxSocketError=Math.max(maxSocketError,distance(la.p[i],lb.p[i]));}
  maxPelvisAngle=Math.max(maxPelvisAngle,angle(a.q[pelvis],b.q[pelvis]));maxLegacyPelvisAngle=Math.max(maxLegacyPelvisAngle,angle(legacy.sample(t).q[pelvis],b.q[pelvis]));const legCorrection=R.qlog(R.qm(la.q[free.hip],R.qinv(lb.q[free.hip])));maxLateral=Math.max(maxLateral,Math.hypot(plan.responseAt(t)[6],plan.responseAt(t)[7]));offsets.push(R.sub(a.points[strike.knee],b.points[strike.knee]));if(offsets.length>=3&&t<=motion.end){const n=offsets.length;maxAddedKneeAcceleration=Math.max(maxAddedKneeAcceleration,R.length(R.mul(R.add(R.sub(offsets[n-1],R.mul(offsets[n-2],2)),offsets[n-3]),240*240)));}
  if(t<=motion.end){maxStrikeDirectionError=Math.max(maxStrikeDirectionError,distance(R.sub(a.points[strike.foot],a.points[strike.hip]),R.sub(b.points[strike.foot],b.points[strike.hip])));for(const i of [strike.hip,strike.knee,strike.foot])maxStrikeOrientationError=Math.max(maxStrikeOrientationError,angle(a.q[i],b.q[i]));}
  for(const h of hinges){const u=R.unit(R.sub(a.points[h.knee],a.points[h.hip])),v=R.unit(R.sub(a.points[h.foot],a.points[h.knee])),bend=Math.atan2(R.dot(R.cross(u,v),R.rotate(a.q[h.knee],h.kneeAxis)),R.dot(u,v));minKnee=Math.min(minKnee,bend);maxKnee=Math.max(maxKnee,bend);const delta=R.qlog(R.qm(R.qinv(referenceLocal.q[h.knee]),la.q[h.knee]));maxHingeError=Math.max(maxHingeError,R.length(R.cross(delta,h.kneeAxis)));}
  if(last){const ah=R.length(H.momentum(last,bodies,plan.rig,1/240)),rh=R.length(H.momentum(lastRaw,rawBodies,plan.rig,1/240));airH2+=ah*ah;rawH2+=rh*rh;maxFineResidual=Math.max(maxFineResidual,ah);}
  last=bodies;lastRaw=rawBodies;samples++;
 }
 // Continuity across recording keys, entry/exit and the 120 Hz solve cache.
 const velocity=(f,t,h)=>R.mul(R.qlog(R.qm(f(t+h),R.qinv(f(t)))),1/h),eps=1e-6;
 let maxRotationVelocityJump=0,maxJointVelocityJump=0,maxKneeAccelerationJump=0;
 for(let t=1/120;t<plan.duration-1/120;t+=1/120){const q=t=>plan.sample(t).q[pelvis],left=velocity(q,t-eps,eps),right=velocity(q,t,eps);maxRotationVelocityJump=Math.max(maxRotationVelocityJump,distance(left,right));}
 for(const t of [motion.lead,motion.end,motion.stop,...clip.poses.map((_,f)=>motion.lead+f/meta.fps)]){
  for(const h of hinges)for(const bone of [h.hip,h.knee,h.foot]){const q=t=>{const p=plan.sample(t);return R.localize(p.points,p.q,parents).q[bone];};maxJointVelocityJump=Math.max(maxJointVelocityJump,distance(velocity(q,t-eps,eps),velocity(q,t,eps)));}
 }
 // Subtract the recorded trajectory: a fast native knee strike has genuine
 // large jerk, which must not be mistaken for an added balance discontinuity.
 for(const t of [...Array.from({length:Math.floor(plan.duration*120)-2},(_,i)=>(i+1)/120),motion.lead,motion.end,motion.stop,...clip.poses.map((_,f)=>motion.lead+f/meta.fps)]){const h=1e-5,p=s=>R.sub(plan.sample(s).points[strike.knee],plan.uncorrected(s).points[strike.knee]),at=p(t),left=R.mul(R.add(R.sub(at,R.mul(p(t-h),2)),p(t-2*h)),1/(h*h)),right=R.mul(R.add(R.sub(p(t+2*h),R.mul(p(t+h),2)),at),1/(h*h));maxKneeAccelerationJump=Math.max(maxKneeAccelerationJump,distance(left,right));}
 assert(maxKeyError<1e-8&&maxAnkleError<1e-8,'Recorded upper and ankle keys must survive');assert(maxFootPathError<.005,'Hinge retargeting preserves the recorded leg path within source length variation');assert(maxJointError<1e-8,'Unselected joints keep their authored motion');assert(maxStrikeDirectionError<1e-8&&maxStrikeOrientationError<1e-8,'Preserve the striking leg world direction and ankle orientation through chamber, strike and retraction');assert(maxSocketError<1e-8,'No stretching');assert(maxCOMError<1e-8,'No COM impulse from an internal kick');
 assert(minKnee>=-1e-5&&maxKnee<=150*Math.PI/180+1e-5,'No inverted or over-folded knee');assert(maxHingeError<1e-8);
 assert(plan.diagnostics.maxDisplayedResidual<1e-5,'Smoothing must not break conservation at solve ticks');assert(Math.sqrt(airH2/rawH2)<.025,'Continuous output must also conserve momentum, not only cached keys');
 assert(maxPelvisAngle<maxLegacyPelvisAngle*.7,'Reduce excessive pelvis compensation');assert(maxLateral<6*Math.PI/180,'Do not spread the free leg to counter twist');assert(maxAddedKneeAcceleration<40,'Remove the extra knee acceleration caused by the old balance solve');
 assert(maxRotationVelocityJump<.05&&maxJointVelocityJump<.05,'No velocity jumps at keys or transitions');
 assert(maxKneeAccelerationJump<.5,'No added knee acceleration jumps at source/cache keys or recovery');
 const saved=JSON.stringify(plan.sample(.713));plan.sample(plan.duration);plan.sample(.01);assert.equal(JSON.stringify(plan.sample(.713)),saved,'Reverse seeking');const count=plan.states.length;plan.sample(1e6);assert.equal(plan.states.length,count,'Bounded replay history');
 // Existing spin is preserved, not killed by the attack; COM may be ballistic.
 const target=[.35,-.2,.4],trajectory=t=>R.add(plan.center,[.4*t,-.5*9.81*t*t,.7*t]),spinning=K.createBalanced({...options,angularMomentum:target,trajectory});
 let maxSpinResidual=0,maxFlightCOMError=0,previous=H.bodies(spinning.sample(0),spinning.rig);
 for(let f=1;f<=Math.floor(spinning.duration*120);f++){const t=f/120,pose=spinning.sample(t),bs=H.bodies(pose,spinning.rig);maxSpinResidual=Math.max(maxSpinResidual,distance(H.momentum(previous,bs,spinning.rig,1/120),target));maxFlightCOMError=Math.max(maxFlightCOMError,distance(K.center(bs,spinning.rig),trajectory(t)));previous=bs;}
 assert(maxSpinResidual<1e-5&&maxFlightCOMError<1e-8,'Flight and incoming spin survive the kick');
 results.push({name,samples,buildMs,maxJointError,maxSocketError,maxCOMError,maxKeyError,maxFootPathError,maxAnkleError,maxStrikeDirectionError,maxStrikeOrientationError,kneeRangeDegrees:[minKnee,maxKnee].map(x=>x*180/Math.PI),maxHingeError,rawMomentumRMS:Math.sqrt(rawH2/(samples-1)),airborneMomentumRMS:Math.sqrt(airH2/(samples-1)),maxFineResidual,maxRotationVelocityJump,maxJointVelocityJump,maxKneeAccelerationJump,maxSpinResidual,maxFlightCOMError,pelvisDegrees:maxPelvisAngle*180/Math.PI,legacyPelvisDegrees:maxLegacyPelvisAngle*180/Math.PI,freeLateralDegrees:maxLateral*180/Math.PI,maxAddedKneeAcceleration,...plan.diagnostics});
}
const html=fs.readFileSync(new URL('kick-preview.html',import.meta.url),'utf8');for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
const receipt={scope:'Conserved airborne core with authored pose return disabled; viewer recovery checked by verify-attack-return.mjs',results};fs.writeFileSync(new URL('airborne-kicks-verification.json',import.meta.url),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt,null,2));
