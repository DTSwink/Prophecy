const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const lab='C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab';
const s=JSON.parse(fs.readFileSync(path.join(lab,'snapshots/snapshot_0007.json'))),manifest=JSON.parse(fs.readFileSync(path.join(lab,'data/manifest.json'))),clip=manifest.clips.find(c=>c.name===s.attack),meta=clip.variants.find(v=>v.id===s.variant),bytes=fs.readFileSync(path.join(lab,meta.file));
const opt={duration:+s.controls.duration,inertia:+s.controls.inertia,returnEasing:s.attackReturnEasing[s.attack],spineTurn:+s.controls.spineTurn,boneInertia:s.attackBoneInertia[s.attack]},results=[];
for(const [name,file] of [['before','./recovery-before-relative-seed.js'],['corrected',path.join(lab,'recovery.js')]]){
 const R=require(file),model=R.prepare(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length),clip,manifest.names,manifest.parents),end=model.attackSeconds,angle=(a,b)=>R.length(R.qlog(R.qm(b,R.qinv(a))))*180/Math.PI;
 const sample=t=>{const p=R.sample(model,t,opt);return s.controls.upperOnly?R.anchor(model,p,meta.target):p;};
 const display=sample(s.time),flat=x=>x.flat(Infinity),diff=(a,b)=>Math.max(...flat(a).map((v,i)=>Math.abs(v-flat(b)[i])));
 const rows=[];
 for(const tick of [-2,-1,0,1,2,3,4,5,6,8,12,16]){
  const a=sample(end+(tick-1)/60),b=sample(end+tick/60),row={tick};
  for(const bone of ['spine_01','spine_05','hand_r']){const j=manifest.names.indexOf(bone);row[bone]={stepCm:100*R.length(R.sub(b.points[j],a.points[j])),stepDegrees:angle(a.q[j],b.q[j])};}rows.push(row);
 }
 const dt=1e-7,a=sample(end-dt),b=sample(end),c=sample(end+dt),seam={};
 for(const bone of ['spine_01','spine_05','upperarm_r','lowerarm_r','hand_r']){const j=manifest.names.indexOf(bone);seam[bone]={incomingDegSec:angle(a.q[j],b.q[j])/dt,outgoingDegSec:angle(b.q[j],c.q[j])/dt,incomingCmSec:100*R.length(R.sub(b.points[j],a.points[j]))/dt,outgoingCmSec:100*R.length(R.sub(c.points[j],b.points[j]))/dt,positionGapCm:100*R.length(R.sub(c.points[j],b.points[j]))};}
 const item={name,options:opt,snapshotPointError:diff(display.points,s.displayedPose.points),snapshotAxesError:diff(display.axes,s.displayedPose.axes),rows,seam};
 if(name==='before'){assert(item.snapshotPointError<1e-10);assert(item.snapshotAxesError<1e-10);}
 results.push(item);
}
fs.writeFileSync(path.join(__dirname,'relative-seed-audit.json'),JSON.stringify(results,null,2));
for(const r of results)console.log(JSON.stringify({name:r.name,options:r.options,snapshotPointError:r.snapshotPointError,rows:r.rows.filter(x=>[0,1,2,3].includes(x.tick)),seam:r.seam},null,2));
