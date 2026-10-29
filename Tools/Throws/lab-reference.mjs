// Independent reference evaluator uses the accepted lab functions, without a viewer/server.
import fs from 'node:fs';
import {createRequire} from 'node:module';
import {createProjectileSystem} from '../../Labs/ThrowLab/projectile.js';
const require=createRequire(import.meta.url);
export const R=require('../../Labs/ThrowLab/recovery.js'),C=require('../../Labs/ThrowLab/core.js'),V=require('../../Labs/ThrowLab/vanilla.js'),A=require('../../Labs/ThrowLab/attack.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url)));
export const data=read('../../Labs/ThrowLab/data/clips.json'),assets=read('../../Labs/ThrowLab/data/objects.json');
export const saved=C.sanitize(read('../../Labs/ThrowLab/approved/2026-10-29/saved-profile.json').settings);
export const rig=A.rig(data.names,data.parents);
export async function openReference(){return createProjectileSystem(assets,R,V);}
export function model(sim,id,amount,override={}){
 const clip=C.decode(data.clips.find(c=>c.id===id),data.parents),end=clip.duration*60,release=(saved.releases[id]??clip.duration*.5)*60;
 const controls={...V.config(saved.vanilla[id],end,release),...override};
 const kind=saved.throwObjects[id]==='sword'&&saved.imperialSpear?'spear':saved.throwObjects[id];
 const grip=saved.grips[id][kind],scale=saved.weaponScales[id][kind],target=override.target||saved.target;
 const raw=f=>C.sample(clip,f/60,data.parents);
 const keys=(pose,f)=>V.pose(V.pose(pose,data.parents,rig.elbow,controls.forearmKeys,f,true),data.parents,rig.hand,controls.keys,f);
 const preset=f=>keys(raw(f),f),options={key:id,kind,release:release/60,referenceRelease:release/60,sample:t=>preset(t*60),hand:rig.hand,duration:clip.duration,target,radius:saved.radius,controls,grip,scale};
 const seed=structuredClone(sim.reference(options));
 const fullPlan=A.prepare({rig,initial:raw(0),armedPose:raw(controls.armed),releasePose:preset(release),velocity:seed.v,...(kind!=='bomb'?{aimAxis:seed.axis,aimPoint:seed.p,aimBone:rig.hand}:{}),target,half:controls.halfAttack,aim:controls.aimAtTarget,armed:controls.armed});
 const full=f=>fullPlan.apply(raw(f),f),curve=A.chargeCurve(raw,controls.armed,release,end,rig);
 const speed=A.chargeSpeed(curve,amount,controls.slowdownBlend).multiplier,trigger=controls.armed*amount,releaseFrame=trigger+(release-controls.armed)/speed,finish=trigger+(curve.peak-controls.armed)/speed;
 const body=A.prepareBody({sample:full,rig,amount,trigger,returnFrame:release,end});
 let carry,partialPlan;
 const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(10+x*(-15+6*x));};
 function motion(f,useCarry=true){
  f=Math.max(0,Math.min(end,f));if(amount===1)return raw(f);const source=full(f);if(f<=trigger)return source;
  const entry=(f-trigger)*speed/Math.max(1e-9,Math.min(4,release-controls.armed));
  let pose=A.partialPose({source,charged:full(trigger),action:full(A.chargeFrame(curve,amount,(f-trigger)*speed)),rig,amount,recover:smooth((f-finish)/Math.max(1e-9,end-finish)),entry,ending:full(end),anchor:f>finish?full(finish):source,body,frame:f,anchorFrame:Math.min(f,finish)});
  if(useCarry&&amount>0){
   carry||={entry:A.prepareCarry({incoming:full,outgoing:f=>motion(f,false),rig,frame:trigger,duration:Math.min(4,release-controls.armed)/speed}),exit:A.prepareCarry({incoming:f=>motion(f,false),outgoing:f=>motion(f,false),rig,frame:finish,duration:Math.min(8,end-finish)})};
   if(entry<1)pose=A.carryPose(pose,carry.entry,f);else if(f>finish&&f<finish+8)pose=A.carryPose(pose,carry.exit,f);
  }return pose;
 }
 if(amount!==1&&controls.aimAtTarget){const rp=keys(motion(releaseFrame),releaseFrame),held=sim.held({...options,pose:rp});partialPlan=A.prepare({rig,initial:raw(0),releasePose:rp,velocity:R.rotate(fullPlan.rotation,seed.v),...(kind!=='bomb'?{aimAxis:R.rotate(held.q,assets[kind].longAxis),aimPoint:held.p,aimBone:rig.hand}:{}),target,half:controls.halfAttack,aim:true,armed:releaseFrame-trigger});}
 const sample=f=>{let pose=motion(f);if(amount===1)pose=fullPlan.apply(pose,f);else if(partialPlan&&f>trigger)pose=partialPlan.apply(pose,f-trigger);return keys(pose,Math.min(f,end));};
 const turn=partialPlan?R.qm(partialPlan.rotation,fullPlan.rotation):fullPlan.rotation;
 const held=sim.held({...options,pose:sample(releaseFrame)}),axis=R.rotate(held.q,assets[kind].longAxis||R.rotate(R.qinv(seed.q),seed.axis));
 return {clip,controls,kind,grip,scale,target,curve,seed,release,releaseFrame,finish,trigger,speed,sample,launch:{...held,v:R.mul(R.rotate(turn,seed.v),amount),omega:R.mul(axis,seed.twist*Math.PI/3),axis,twist:seed.twist}};
}
