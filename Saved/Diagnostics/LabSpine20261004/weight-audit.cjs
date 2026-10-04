const fs=require('fs'),path=require('path'),assert=require('assert/strict'),lab='C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab';
const snapshot=JSON.parse(fs.readFileSync(path.join(lab,'snapshots/snapshot_0010.json'))),manifest=JSON.parse(fs.readFileSync(path.join(lab,'data/manifest.json'))),clip=manifest.clips.find(c=>c.name===snapshot.attack),meta=clip.variants.find(v=>v.id===snapshot.variant),b=fs.readFileSync(path.join(lab,meta.file));
const opt={duration:+snapshot.controls.duration,returnEasing:+snapshot.controls.returnEasing,inertia:+snapshot.controls.inertia,springReturn:true,worldInertia:true,inertiaDecay:+snapshot.controls.inertiaDecay,spineTurn:+snapshot.controls.spineTurn,boneInertia:snapshot.attackBoneInertia[snapshot.attack]},result=[];
for(const [name,file] of [['before','./recovery-before-weight-fix.js'],['after',path.join(lab,'recovery.js')]]){
 const R=require(file),m=R.prepare(meta,b.buffer.slice(b.byteOffset,b.byteOffset+b.length),clip,manifest.names,manifest.parents),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI,j=m.names.indexOf('spine_05');
 const pose=R.anchor(m,R.sample(m,snapshot.time,opt),meta.target),error=Math.max(...pose.points.flat().map((v,i)=>Math.abs(v-snapshot.displayedPose.points.flat()[i])));
 if(name==='before')assert(error<1e-10,'snapshot not reproduced');
 const cases=[];
 for(const weight of [0,.001,.01,.04,.05,.1,1]){
  const o={...opt,boneInertia:{...opt.boneInertia,spine:weight}},rows=[];
  for(let frame=0;frame<=16;frame++){const elapsed=Math.min(frame/60,opt.duration),p=R.sample(m,m.attackSeconds+elapsed,o),prev=R.sample(m,m.attackSeconds+Math.max(0,elapsed-1/60),o),local=R.localize(p.points,p.q,m.parents);rows.push({frame,elapsed,errorToIdle:angle(local.q[j],m.idle.q[j]),worldStep:angle(p.q[j],prev.q[j])});}
  cases.push({weight,rows});
 }
 result.push({name,snapshotError:error,cases});
}
fs.writeFileSync(path.join(__dirname,'weight-audit.json'),JSON.stringify(result,null,2));
for(const r of result){console.log(r.name);for(const c of r.cases.filter(c=>[0,.04,1].includes(c.weight)))console.log(JSON.stringify({weight:c.weight,rows:c.rows.filter(x=>[0,2,4,6,8,10,12,16].includes(x.frame))}));}
