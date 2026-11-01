// Explicit offline bake. Never writes live lab state or source FBXs.
import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {openReference,model,saved,C,R,V,data,assets,rig} from './lab-reference.mjs';
const root=new URL('../../',import.meta.url);
const read=p=>fs.readFileSync(new URL(p,root));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const stateBytes=read('Labs/ThrowLab/state.json');
const settings=C.sanitize(JSON.parse(stateBytes).settings);
// The reference reads this object at model construction; this affects only this process.
Object.assign(saved,settings);
const dir=new URL('Exports/Throws/FinalNoAim/',root);
fs.mkdirSync(dir,{recursive:true});
const clips=[],metadata=[],sim=await openReference();
try {
 for(const source of data.clips){
  const m=model(sim,source.id,1,{aimAtTarget:false,throwPercent:100});
  const other=model(sim,source.id,1,{aimAtTarget:false,throwPercent:100,target:[100,-30,80]});
  const end=Math.round(source.duration*60),frames=[],locals=[];
  let targetError=0,rawDifference=0;
  for(let f=0;f<=end;f++){
   const p=m.sample(f),p2=other.sample(f),raw=C.sample(m.clip,f/60,data.parents);
   const local=R.localize(p.points,p.q,data.parents);
   for(let j=0;j<data.names.length;j++){
    targetError=Math.max(targetError,Math.hypot(...R.sub(p.points[j],p2.points[j])),1-Math.abs(p.q[j].reduce((s,v,k)=>s+v*p2.q[j][k],0)));
    rawDifference=Math.max(rawDifference,Math.hypot(...R.sub(p.points[j],raw.points[j])));
   }
   frames.push(p.points.map((v,j)=>[...v,...p.q[j]]));
   locals.push(local.p.map((v,j)=>[...v,...local.q[j]]));
  }
  assert(targetError<1e-12);
  assert(frames.flat(2).every(Number.isFinite));
  const file=source.id==='big-throw'?'BigThrow_Final_NoAim.fbx':'SmallThrow_Final_NoAim.fbx';
  const clip={id:source.id,name:source.name+' final no aim',fps:60,duration:end/60,startFrame:0,frames,locals};
  clips.push(clip);
  metadata.push({id:source.id,file,source:source.source,sourceSha256:source.sha256,frameCount:frames.length,endFrame:end,armedFrame:m.controls.armed,releaseFrame:m.releaseFrame,throwPercent:100,aimAtTarget:false,halfAttack:m.controls.halfAttack,kind:m.kind,grip:m.grip,scale:m.scale,bind:assets[m.kind].bind,longAxis:assets[m.kind].longAxis,mass:assets[m.kind].mass,launch:m.launch,physics:{velocityRotation:m.controls.velocityRotation,speedScale:m.controls.speedScale,twist:m.controls.twist,aero:m.controls.aero},validation:{targetError,maxWorldPositionDifferenceFromRawMeters:rawDifference},bakedHandKeys:m.controls.keys.length,bakedForearmKeys:m.controls.forearmKeys.length});
 }
} finally {sim.dispose();}
assert.equal(hash(read('Labs/ThrowLab/state.json')),hash(stateBytes),'Live state changed while baking; retry snapshot.');
const output={schema:'throw-lab-y-up-metres-quaternion-v1',names:data.names,parents:data.parents,clips};
fs.writeFileSync(new URL('clips.json',dir),JSON.stringify(output));
fs.writeFileSync(new URL('settings-source.json',dir),JSON.stringify(settings,null,2));
fs.writeFileSync(new URL('manifest.json',dir),JSON.stringify({schema:1,bakedAt:new Date().toISOString(),stateSha256:hash(stateBytes),units:{position:'meters',linearVelocity:'meters/second',angularVelocity:'radians/second',quaternion:'xyzw',up:'Y',fps:60},sampling:'Frames are baked final world transforms; locals are parent-relative. Do not reapply hand/forearm keys or Half/Aim. Physical launch adjustments are metadata, not animation retiming.',algorithmSha256:Object.fromEntries(['Tools/Throws/lab-reference.mjs',...['recovery.js','core.js','vanilla.js','attack.js','projectile.js'].map(n=>'Labs/ThrowLab/'+n)].map(p=>[p,hash(read(p))])),clips:metadata},null,2));
console.log(JSON.stringify(metadata.map(({id,frameCount,releaseFrame,validation})=>({id,frameCount,releaseFrame,validation})),null,2));
