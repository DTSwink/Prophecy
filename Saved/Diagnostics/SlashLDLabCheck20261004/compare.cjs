const fs=require('fs'),path=require('path'),R=require('../../../Labs/AttackRecoveryLab/recovery.js');
const p=__dirname,lab=path.resolve('C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab'),manifest=JSON.parse(fs.readFileSync(lab+'/data/manifest.json')),cap=JSON.parse(fs.readFileSync(p+'/lab-trajectory.json')),s=cap.state,c=manifest.clips.find(c=>c.name==='slashLD'),v=c.variants.find(v=>v.id===2),buf=fs.readFileSync(lab+'/'+v.file);
const m=R.prepare(v,buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength),c,manifest.names,manifest.parents),o={enabled:true,duration:.28,returnEasing:.87,inertia:.76,boneInertia:s.attackBoneInertia.slashLD,inertiaHold:.05,inertiaDecay:.8,worldInertia:true,angleTimeSeconds:.29};
let err=0;for(const row of cap.samples){let a=R.anchor(m,R.sample(m,row.seconds,o),m.meta.target);for(let j=0;j<manifest.names.length;j++)err=Math.max(err,R.length(R.sub(a.points[j],row.points[j])));}
const rows=JSON.parse(fs.readFileSync(p+'/baseline.json')).rows,by=Object.fromEntries(rows.map(r=>[r.tick,r]));
const conv=(r,kind='future')=>{let q=[],points=[];for(let j=0;j<m.names.length;j++){let n=m.names[j],b=r.bones[n]?.[kind];q[j]=b?[-b.q[0],b.q[1],-b.q[2],b.q[3]]:[0,0,0,1];points[j]=b?[b.p[0]/100,-b.p[1]/100,b.p[2]/100]:[0,0,0];}return {points,q,axes:q.map(R.toAxes)};};
const prev=conv(by[100]),end=conv(by[102]),locals=[prev,end].map(x=>R.localize(x.points,x.q,m.parents)),last=locals[1];
const u={...m,poses:[prev,end],locals,meta:{...m.meta,frames:2,fps:30},attackSeconds:1/30,seedCache:null,turnCache:null,springCache:null};
u.worldVelocity=end.q.map((q,j)=>R.mul(R.qlog(R.qm(q,R.qinv(prev.q[j]))),30));
u.offsetVelocity=last.p.map((v,j)=>R.length(v)>1e-8&&R.length(locals[0].p[j])>1e-8?R.mul(R.qlog(R.fromTo(locals[0].p[j],v)),30):[0,0,0]);
u.idleOffsets=m.idle.p.map((v,j)=>R.length(v)>1e-8?R.mul(R.unit(v),R.length(last.p[j])):last.p[j]);u.idlePose=R.fk({q:last.q.map((q,j)=>u.upper[j]?u.idle.q[j]:q),p:last.p.map((v,j)=>u.upper[j]?u.idleOffsets[j]:v)},u.parents);
const pelvis=m.names.indexOf('pelvis'),hand=m.names.indexOf('hand_r'),spine=m.spine,T=R.returnTiming(u,o).duration;
R.sample(u,u.attackSeconds+1e-8,o); // Cache outgoing seed before changing lower pose.
function nativeSample(t,actual){
 const frozen=R.sample(u,u.attackSeconds+t,o),x=t/T,blend=x+(x*x*x*(10+x*(-15+6*x))-x)*o.returnEasing;
 const l={q:last.q.slice(),p:last.p.slice()};l.q[pelvis]=R.qslerp(end.q[pelvis],actual.q[pelvis],blend);l.p[pelvis]=actual.points[pelvis];
 const temp={...u,locals:[locals[0],l]},a=R.sample(temp,u.attackSeconds+t,o),loc=R.localize(a.points,a.q,m.parents);
 a.q[pelvis]=actual.q[pelvis];a.points[pelvis]=actual.points[pelvis];
 for(let j=0;j<m.names.length;j++)if(m.upper[j])a.points[j]=R.add(a.points[m.parents[j]],R.rotate(a.q[m.parents[j]],loc.p[j]));
 return {a,frozen};
}
let maxCm=0,maxDeg=0;const compare=[];
for(let tick=104;tick<=120;tick+=2){const actual=conv(by[tick]),{a,frozen}=nativeSample((tick-102)/60,actual),e=[];for(let j=0;j<m.names.length;j++)if(m.upper[j]){const cm=R.length(R.sub(a.points[j],actual.points[j]))*100,deg=R.length(R.qlog(R.qm(a.q[j],R.qinv(actual.q[j]))))*180/Math.PI;e.push({bone:m.names[j],cm,deg});maxCm=Math.max(maxCm,cm);maxDeg=Math.max(maxDeg,deg);}
 compare.push({tick,errors:e,handRelativeSpineActual:R.mul(R.sub(actual.points[hand],actual.points[spine]),100),handRelativeSpineFrozen:R.mul(R.sub(frozen.points[hand],frozen.points[spine]),100)});}
function handStats(model,kind){let out=[];for(let k=-3;k<=8;k++){let at=model.attackSeconds+k/60;const a=R.sample(model,at,o),b=R.sample(model,at-1/60,o),d=R.mul(R.sub(R.sub(a.points[hand],a.points[spine]),R.sub(b.points[hand],b.points[spine])),100);out.push({k,delta:d,speed:R.length(d)});}return out;}
const ueStats=[];for(let tick=99;tick<=113;tick++){const a=conv(by[tick],'presented'),b=conv(by[tick-1],'presented'),d=R.mul(R.sub(R.sub(a.points[hand],a.points[spine]),R.sub(b.points[hand],b.points[spine])),100);ueStats.push({tick,delta:d,speed:R.length(d)});}
const result={liveLabMaxErrorM:err,labTiming:R.returnTiming(m,o),unrealTiming:T,labFrames:v.frames,unrealLastPolicyFrame:23,labTarget:v.target,nativeMaxCm:maxCm,nativeMaxDeg:maxDeg,compare,labHand:handStats(m),unrealSeedHand:handStats(u),unrealHand:ueStats,seedRates:Object.fromEntries(['spine_01','spine_05','upperarm_r','lowerarm_r','hand_r'].map(n=>{let j=m.names.indexOf(n);return [n,{lab:m.worldVelocity[j],unreal:u.worldVelocity[j]}]}))};
result.wristLengthControl=[];
for(let tick=104;tick<=120;tick+=2){
 const actual=conv(by[tick]),{a}=nativeSample((tick-102)/60,actual),elbow=m.names.indexOf('lowerarm_r');
 const observedLength=R.length(R.sub(actual.points[hand],actual.points[elbow]));
 const predicted=R.add(a.points[elbow],R.mul(R.unit(R.sub(a.points[hand],a.points[elbow])),observedLength));
 result.wristLengthControl.push({tick,labLengthCm:100*R.length(R.sub(a.points[hand],a.points[elbow])),actualLengthCm:100*observedLength,remainingErrorCm:100*R.length(R.sub(predicted,actual.points[hand]))});
}
fs.writeFileSync(p+'/comparison.json',JSON.stringify(result,null,2));console.log(JSON.stringify({liveLabMaxErrorM:err,nativeMaxDeg:maxDeg,wristLengthControl:result.wristLengthControl},null,2));
