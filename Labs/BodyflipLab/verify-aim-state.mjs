// Legal-coordinate aiming, held rotations and projector bracket regressions.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),Aim=require('./attack-aim.js'),F=require('./flight.js'),I=require('./idle.js'),J=require('./joint-rig.js'),W=require('./wrist.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),meta=read('data/vanilla.json'),catalog=new Map(meta.clips.map(v=>[v.name,C.decode(v,bytes(v.file),names,parents)])),Project=require('./target-rig.js').create(names,parents,reference),project=p=>Project.project(p),joints=J.create(names,parents,reference);
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),m).motion(),distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));let checks=0,maxProjectionResidual=0;
for(const c of joints.joints.filter(c=>!c.hinge))for(const signY of [-1,1])for(const signZ of [-1,1])for(const radius of [.3,.8,.999]){
 const v=radius/Math.sqrt(2),constraint=W.compose([0,v*signY,v*signZ,Math.sqrt(1-radius*radius)],R.qexp([.2,0,0])),q=R.qm(R.qm(c.parentBasis,constraint),R.qinv(c.basis)),legal=joints.clampLocal(q,c),again=joints.clampLocal(legal,c),error=angle(again,legal);
 maxProjectionResidual=Math.max(error,maxProjectionResidual);assert(error<1e-8,`${c.name}: projection outside ellipse`);assert(angle(legal,joints.clampLocal(R.mul(q,-1),c))<1e-8,'Quaternion signs equivalent');checks+=2;
}
let held=null;
for(const name of ['headbutt','slashL','sweepKick']){
 const settings=C.sanitize({mode:'spaceGym',spinLag:.6,spinInertia:1,kickToArmed:true,jumpEvents:[{id:'a',time:.1,spinVersion:2,instantSpin:true,flip:360,twist:150,jumpPercent:0,attack:name,attackDelay:.2}]}),seq=F.sequence(idle,jumps,settings,parents,reference,null,catalog,{horizon:4}),track=seq.segments[0].attack,clip=catalog.get(name),sample=t=>seq.sample(t).pose,plan=Aim.create({clip,track,names,parents,reference,sampleHit:sample,project}),target=R.add(plan.origin,[1.5,0,0]),raw=sample(track.hitTime),full=plan.correction(target),part=plan.rotation(plan.ready,target,.8);
 for(let i=0;i<full.offsets.length;i++)for(let k=0;k<full.offsets[i].length;k++){assert(Math.abs(part.offsets[i][k]-.8*full.offsets[i][k])<1e-12);checks++;}
 for(const t of [plan.ready,track.end,track.returnEnd,track.returnEnd+1]){const fixed=plan.apply(raw,t,target,1,false),expected=plan.applyRotation(raw,full);assert(fixed.points.every((p,i)=>distance(p,expected.points[i])<1e-9),'Hold correction unchanged over time');checks++;}
 const zero=plan.apply(raw,track.returnEnd,target),baseline=project(raw);assert(zero.points.every((p,i)=>distance(p,baseline.points[i])<1e-9),'Return removes only correction');assert(angle(zero.q[1],baseline.q[1])<1e-9);checks+=2;
 if(held){const before=plan.applyRotation(raw,held),start=plan.applyRotation(raw,plan.rotation(track.start,target,1,false,held));assert(start.points.every((p,i)=>distance(p,before.points[i])<1e-9),'Next attack starts at previous held correction');checks++;}held=full;
 const fallback=Aim.create({clip,track,names,parents,reference,sampleHit:sample}),pose=fallback.apply(raw,track.hitTime,target);assert(distance(R.unit(R.sub(fallback.point(pose),Aim.center(pose,fallback.rig))),R.unit(R.sub(target,fallback.origin)))<1e-5,'Standalone default uses legal projector');checks++;
}
console.log({passed:true,checks,maxProjectionResidual});
