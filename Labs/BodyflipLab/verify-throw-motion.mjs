// Final motion is the authority: object derivatives, shared transfer and compensation.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),J=require('./jump-attack.js'),A=require('./attack-aim.js'),H=require('./attack-inertia.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),project=H.createProjection(names,parents,reference),pelvis=names.indexOf('pelvis'),chain=[1,2,3,4,5].map(i=>names.indexOf('spine_0'+i)),segment={sample:()=>({pose:reference}),airStart:0,jumpStart:0,abortTime:Infinity};T.load(read('data/throws.json'));
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),reports=[];let transferChecks=0,maxTransferError=0;
for(const name of ['big-throw','small-throw']){
 const settings=C.sanitize({distributePelvisTurn:true,kickToArmed:true,motionCompensation:false,softAttackLegs:true,pelvisAttackCompensation:1}),event={id:'throw',attack:name,throwCharge:name==='big-throw'?100:37,throwSpeed:1},make=s=>T.create(event,segment,null,names,parents,s,reference),off=make(settings),on=make({...settings,motionCompensation:true}),rigid=make({...settings,motionCompensation:true,softAttackLegs:false});
 assert(!off.inertia&&on.inertia,'soft compensation must actually be wired');assert.equal(off.model.controls.aimAtTarget,false,'no baked Throw Lab target aim');
 let compensation=0,rigidCompensation=0,maxBoundary=0;
 for(let t=0;t<off.returnEnd;t+=1/60){const a=off.sample(t).pose,b=on.sample(t).pose,c=rigid.sample(t).pose;assert(angle(a.q[pelvis],reference.q[pelvis])<1e-8,'distributed source turn leaves base pelvis unchanged');compensation=Math.max(compensation,angle(a.q[pelvis],b.q[pelvis]));rigidCompensation=Math.max(rigidCompensation,angle(a.q[pelvis],c.q[pelvis]));}
 assert(compensation>.001&&rigidCompensation>.001,'both compensation paths produce opposing body motion');
 for(let f=0;f<off.clip.poses.length;f+=.5){const raw=J.at(off.clip,f,parents),first=off.clip.locals[0],turned=J.attackAt(off.clip,f,names,parents,true),share=angle(raw.q[pelvis],first.q[pelvis])/5;for(const i of chain){maxTransferError=Math.max(maxTransferError,Math.abs(angle(raw.q[i],turned.q[i])-share));transferChecks++;}}
 for(const track of [off,on,rigid])for(const t of [track.start,track.start+track.duration,track.releaseTime,track.end,track.returnEnd]){const a=track.sample(t-1e-7).pose,b=track.sample(t+1e-7).pose;for(const i of [pelvis,...chain])maxBoundary=Math.max(maxBoundary,angle(a.q[i],b.q[i]));}
 assert(maxBoundary<1e-4,'no pose snap at entry/release/return');
 for(const [label,track] of [['off',off],['soft',on],['rigid',rigid]]){
  const raw=t=>project(track.sample(t).pose),launchAt=(pose,map=p=>p)=>{const at=t=>map(raw(t),t);return track.launchAt(pose,track.releaseVelocity(at),track.releaseAngularVelocity(at));},plan=A.create({track,names,parents,reference,sampleHit:raw,launchAt,project}),neutral=launchAt(raw(track.releaseTime));
  const origin=plan.aimReferenceOrigin,ray=name==='big-throw'?neutral.axis:[neutral.v[0],0,neutral.v[2]],target=R.add(origin,R.mul(R.unit(R.rotate(R.qexp([0,.08,0]),ray)),4));
  const at=t=>project(plan.apply(raw(t),t,target)),packet=track.launchAt(at(track.releaseTime),track.releaseVelocity(at),track.releaseAngularVelocity(at)),center=t=>A.launchCenter({...track.heldAt(at(t)),comOffset:packet.comOffset}),h=1e-5,measured=R.mul(R.sub(center(track.releaseTime),center(track.releaseTime-h)),1/h),velocityError=distance(packet.v,measured);
  assert(velocityError<.005,'exit velocity must match the held object left derivative: '+velocityError);
  assert.equal(angle(plan.correction(target).yaw,[0,0,0,1])<1e-8,true,'aim cannot add pelvis roll/yaw');assert(plan.solution(target).parameters.length<=(name==='big-throw'?2:1),'no roll or pelvis fallback parameter');
  assert(distance(packet.p,track.heldAt(at(track.releaseTime)).p)<1e-10,'release position continuous');
  const aimed=A.launchAim(packet,target,plan.throwDirectionFor(target)),error=distance(R.unit(aimed.direction),aimed.wanted);assert(error<1e-5,'nearby shaft/plane target is reachable: '+error);
  const frozen=()=>at(track.releaseTime);assert(distance(track.releaseVelocity(frozen),[0,0,0])<1e-9,'stationary hand cannot get a saved launch impulse');assert(distance(track.releaseAngularVelocity(frozen),[0,0,0])<1e-9,'stationary hand cannot get a saved spin');
  reports.push({name,compensation:label,velocityError,aimError:error,speed:R.length(packet.v),compensationAngle:compensation,rigidCompensationAngle:rigidCompensation,maxBoundary});
 }
}
assert(maxTransferError<1e-8);
fs.mkdirSync(new URL('../../Saved/BodyflipLab/ThrowMotion/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/BodyflipLab/ThrowMotion/results.json',import.meta.url),JSON.stringify({reports,transferChecks,maxTransferError},null,2));console.log(JSON.stringify({passed:true,reports,transferChecks,maxTransferError},null,2));
