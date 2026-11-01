// Pure animation/aim checks: no browser, Jolt worker, or scene modification.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),Aim=require('./attack-aim.js'),F=require('./flight.js'),I=require('./idle.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
T.load(read('data/throws.json'));const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),projector=require('./target-rig.js').create(names,parents,reference),project=p=>projector.project(p);
const idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),manifest).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(p=>read(p).clips).map(F.decodeJump),reports=[];
// Nearby targets test attainable upper-body steering; arbitrary rear targets
// no longer authorize a pelvis/roll fallback. Angles are yaw/pitch offsets.
const vectors=[[0,0],[-.08,0],[.08,0],[0,-.04],[0,.04],[.04,.02]],distance=(a,b)=>R.length(R.sub(a,b));
for(const name of ['big-throw','small-throw'])for(const charge of name==='big-throw'?[100]:[10,37,100])for(const rate of [0,360,-360]){
 const settings=C.sanitize({mode:'spaceGym',spinLag:.6,spinInertia:1,aimWeight:1,jumpEvents:[{id:'throw',time:.1,spinVersion:2,instantSpin:true,flip:rate,twist:rate?150:0,jumpPercent:0,attack:name,attackDelay:.2,throwCharge:charge}],trimOut:6}),seq=F.sequence(idle,jumps,settings,parents,reference,null,new Map(),{horizon:6}),track=seq.segments[0].attack,sample=t=>seq.sample(t).pose;
 const launchAt=(pose,mapPose=p=>p)=>track.launchAt(pose,track.releaseVelocity(t=>mapPose(sample(t),t))),plan=Aim.create({track,names,parents,reference,sampleHit:sample,launchAt,project}),raw=sample(track.releaseTime);
 for(const v of vectors){
  const neutralAt=t=>project(sample(t)),neutral=track.launchAt(neutralAt(track.releaseTime),track.releaseVelocity(neutralAt)),origin=plan.aimReferenceOrigin,ray=name==='big-throw'?neutral.axis:[neutral.v[0],0,neutral.v[2]],target=R.add(origin,R.mul(R.unit(R.rotate(R.qexp([name==='big-throw'?v[1]:0,v[0],0]),ray)),3)),at=t=>project(plan.apply(sample(t),t,target)),launch=track.launchAt(at(track.releaseTime),track.releaseVelocity(at)),toward=plan.throwDirectionFor(target),error=name==='big-throw'?distance(R.unit(launch.axis),R.unit(toward)):distance(R.unit([launch.v[0],0,launch.v[2]]),R.unit([toward[0],0,toward[2]])),dCOM=distance(Aim.center(raw,plan.rig),Aim.center(at(track.releaseTime),plan.rig));
  assert(launch.p.concat(launch.q,launch.v,launch.omega).every(Number.isFinite),'finite launch');
  reports.push({name,charge,rate,target,offset:v,error,dCOM,velocity:launch.v,parameters:plan.solution(target).parameters,solverError:plan.solution(target).error});
 }
 console.log(JSON.stringify({name,charge,rate,maxError:Math.max(...reports.slice(-vectors.length).map(r=>r.error))}));
}
fs.mkdirSync(new URL('../../Saved/BodyflipLab/ThrowAim/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/BodyflipLab/ThrowAim/results.json',import.meta.url),JSON.stringify(reports,null,2));
// Joint limits may prevent an upper-only turn. Report the actual residual,
// never manufacture a pelvis/roll correction or rewrite projectile velocity.
assert(reports.filter(r=>r.offset.every(v=>v===0)).every(r=>r.error<1e-6),'the unturned release direction must remain reachable');
assert(reports.every(r=>Math.abs(r.error-r.solverError)<1e-6),'reported residual matches displayed release');
assert(reports.every(r=>r.parameters.length<=(r.name==='big-throw'?2:1)),'no roll or pelvis aiming fallback');assert(reports.every(r=>r.dCOM<1e-7),'aim preserves COM');
console.log(JSON.stringify({passed:true,cases:reports.length,limited:reports.filter(r=>r.error>=1e-6).length,maxError:Math.max(...reports.map(r=>r.error))}));
