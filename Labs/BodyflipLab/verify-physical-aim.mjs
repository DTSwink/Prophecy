import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),M=require('./mass.js'),P=require('./physical-flight.js'),A=require('./attack-aim.js'),Aim=require('./physical-aim.js');
const manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),{names,parents}=manifest,reference=C.poseFromShared(manifest),rig=M.model(names,parents,reference);
const meta=JSON.parse(fs.readFileSync(new URL('data/vanilla.json',import.meta.url))).clips.find(c=>c.name==='slashL'),bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),clip=C.decode(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),names,parents);
const track={start:0,hitTime:.35,armedTime:.15,end:.5,returnEnd:.7},identity=[0,0,0,1],reports=[];
const distance=(a,b)=>R.length(R.sub(a,b));
for(const momentum3D of [false,true])for(const speed of [-2,2]){
 const zero={from:[0,0,0],to:[0,0,0],begin:0,duration:0},spinPlan={referenceI:M.tensor(reference,rig),flip:{...zero,to:[speed,0,0]},twist:zero};
 const seed=t=>({pose:reference,root:reference.points[0],phase:'SPACE',spin:{rotation:identity,spinPlan}}),raw=t=>{const q=R.qexp([Math.max(0,t)*speed,0,0]),pose=M.rotateAboutCOM(reference,q,rig);return {pose,root:pose.points[0],phase:'SPACE',spin:{rotation:q,spinPlan}};};
 const config={start:0,settings:{momentum3D},names,parents,reference,gravity:0,seedSource:seed};
 const neutral=P.create(raw,config),probe=A.create({clip,track,names,parents,reference,sampleHit:t=>neutral.sample(t).pose}),neutralHit=neutral.sample(track.hitTime).pose;
 const origin=A.center(neutralHit,probe.rig),ray=R.sub(probe.point(neutralHit),origin),target=R.add(origin,R.mul(R.rotate(R.qexp([0,.08,0]),ray),.97));
 const settings={momentum3D,aim:true,aimWeight:1,undoRotation:true,target},plain=Aim.create(raw,config,{clip,track,settings}),a=plain.sample(track.hitTime);
 const offset=t=>[2+.7*t,3+4*t,-1-.3*t],worldPose=(p,t)=>({...p,points:p.points.map(v=>R.add(v,offset(t)))}),shifted=Aim.create(raw,config,{clip,track,settings:{...settings,target:R.add(target,offset(track.hitTime))},worldPose}),b=shifted.sample(track.hitTime);
 const poseDifference=Math.max(...a.pose.points.map((v,i)=>distance(v,b.pose.points[i])));
 assert(poseDifference<1e-8,'Carrier displacement/velocity must not change the local aim solution');
 const plan=plain.plan,point=plan.point(a.pose),com=A.center(a.pose,plan.rig),error=distance(R.unit(R.sub(point,com)),R.unit(R.sub(target,com)));
 const contactError=distance(point,target);assert(contactError<.06,'Nearby target remains inside the contact tolerance without changing arm reach');assert(error<.08,'Direction converges under physical reaction');
 for(let t=0;t<=track.end;t+=1/60){const posed=plain.sample(t).pose,source=neutral.sample(t).pose,pa=R.localize(posed.points,posed.q,parents),pb=R.localize(source.points,source.q,parents);for(let j=0;j<names.length;j++)if(/^(clavicle|upperarm|lowerarm|hand)_/.test(names[j]))assert(R.length(R.qlog(R.qm(pa.q[j],R.qinv(pb.q[j]))))<1e-9,'Preserve the entire authored arm stroke');}
 const count=plain.statistics.evaluations,saved=JSON.stringify(a);plain.sample(.6);plain.sample(.1);assert.equal(JSON.stringify(plain.sample(track.hitTime)),saved);assert.equal(plain.statistics.evaluations,count,'Playback cannot restart aim optimization');
 reports.push({momentum3D,speed,error,contactError,poseDifference,evaluations:count});
}
console.log(JSON.stringify({passed:true,cases:reports.length,reports},null,2));
