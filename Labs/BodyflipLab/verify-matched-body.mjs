import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('./flight.js'),C=require('./core.js'),R=require('./recovery.js'),I=require('./idle.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const manifest=read('data/manifest.json'),parents=manifest.parents,names=manifest.names;
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const response=await fetch('http://127.0.0.1:8876/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({gait:'run',duration:5,phase:0,drawn:true})});
assert(response.ok);const run=F.decodeNN(await response.json());
const idleBytes=fs.readFileSync(new URL('data/idle.bin',import.meta.url));
const idle=I.create(read('data/idle.json'),idleBytes.buffer.slice(idleBytes.byteOffset,idleBytes.byteOffset+idleBytes.byteLength),manifest).motion();
const base={mode:'jump',ramps:false,platforms:[{id:'floor',position:[0,-.2,0],size:[20,.4,66],rotation:[0,0,0,1]}],airFlip:false,matchLeg:true};
const checks=[],check=(label,ok)=>{assert(ok,label);checks.push(label);};
const distance=(a,b)=>R.length(R.sub(a,b)),qError=(a,b)=>1-Math.abs(a.reduce((n,v,i)=>n+v*b[i],0));
const smooth=t=>{t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);};
function target(segment,t,raw=false){
 const clip=F.trimStart(jumps.find(j=>j.name===segment.start)),clock=raw?t:segment.animationTime(t);
 let pose=F.localRoot(F.at(clip,clock,parents));
 if(clock>=segment.sourceLoopStart)pose=C.blend(pose,F.localRoot(F.at(jumps.find(j=>j.name.endsWith('_Loop_Fall')),clock-segment.sourceLoopStart,parents,true)),smooth((clock-segment.sourceLoopStart)/.25),parents);
 return R.localize(pose.points,pose.q,parents);
}
let maxRootError=0,maxPinError=0,maxJointError=0;
for(const variant of [
 {jumpFoot:'R'}, {jumpFoot:'L',runSeconds:.7}, {jumpFoot:'R',jumpBlend:.05,legBlend:.4},
 {jumpFoot:'R',jumpBlend:.4,legBlend:.05}, {jumpFoot:'R',loadMs:0}, {mode:'idle'}
]){
 const s=C.sanitize({...base,...variant}),motion=s.mode==='idle'?idle:run;
 const a=F.sequence(motion,jumps,s,parents).segments[0],b=F.sequence(motion,jumps,{...s,matchLeg:false},parents).segments[0];
 const label=JSON.stringify(variant),l=a.support.leg;
 check('Successful match '+label,a.matchDistance!==null);
 check('Normal-speed shared clock '+label,a.legRate===1&&Math.abs(a.animationTime(.4)-a.animationTime(.1)-.3)<1e-9&&Math.abs(a.animationTime(0)-a.matchTime)<1e-9);
 check('Contact and release times unchanged '+label,Math.abs(a.jumpStart-b.jumpStart)<1e-9&&Math.abs(a.airStart-b.airStart)<1e-9);
 for(let t=a.supportStart;t<a.jumpStart+1.2;t+=1/120){
  const p=a.sample(t),normal=b.sample(t);maxRootError=Math.max(maxRootError,distance(p.root,normal.root));
  if(t<=a.airStart)maxPinError=Math.max(maxPinError,distance(p.pose.points[l.foot],normal.pose.points[l.foot]));
 }
 for(const t of [Math.max(s.jumpBlend,a.release+s.legBlend)+.02,a.loopStart+.3]){
  const p=a.sample(a.jumpStart+t).pose,local=R.localize(p.points,p.q,parents),expected=target(a,t);
  for(let i=2;i<names.length;i++)maxJointError=Math.max(maxJointError,qError(local.q[i],expected.q[i]));
 }
 // With different blend durations, the finished group must already follow the
 // shared target even while the other group is still blending into it.
 if(s.jumpBlend!==s.legBlend){
  const t=s.jumpBlend<s.legBlend?s.jumpBlend+.02:a.release+s.legBlend+.02;
  const local=R.localize(a.sample(a.jumpStart+t).pose.points,a.sample(a.jumpStart+t).pose.q,parents),expected=target(a,t);
  const indices=s.jumpBlend<s.legBlend?[names.indexOf('spine_03'),names.indexOf('upperarm_l')]:[l.hip,l.knee,l.foot];
  check('Separate blend durations '+label,indices.every(i=>qError(local.q[i],expected.q[i])<1e-9));
 }
 const t=.3,p=a.sample(a.jumpStart+t).pose,red=a.animationLeg(a.jumpStart+t,p,true),purple=a.animationLeg(a.jumpStart+t,p),raw=target(a,t,true);
 const expected=R.localize(p.points,p.q,parents);
 for(const i of [l.hip,l.knee,l.foot,l.toe]){expected.q[i]=raw.q[i];if(i!==l.hip)expected.p[i]=raw.p[i];}
 const rawPose=R.fk(expected,parents);
 check('Red overlay keeps original timing '+label,distance(red.points[2],rawPose.points[l.foot])<1e-9);
 check('Purple overlay follows matched target '+label,purple.points.every(v=>v.every(Number.isFinite)));
 const other=a.animationLeg(a.jumpStart+t,p,false,true),opposite=l.side==='L'?'R':'L';
 const otherBones=['thigh','calf','foot','ball'].map(n=>names.indexOf(n+'_'+opposite.toLowerCase())),otherLocal=R.localize(other.pose.points,other.pose.q,parents),matched=target(a,t);
 check('Other leg overlay uses the opposite side and same matched clock '+label,other.foot===opposite&&otherBones.every(i=>qError(otherLocal.q[i],matched.q[i])<1e-9));
 const before=a.sample(a.jumpStart-1e-8).pose,after=a.sample(a.jumpStart+1e-8).pose;
 const beforeNormal=b.sample(b.jumpStart-1e-8).pose,afterNormal=b.sample(b.jumpStart+1e-8).pose;
 check('Matching adds no pose snap at push '+label,Math.max(...before.points.map((v,i)=>distance(v,after.points[i])-distance(beforeNormal.points[i],afterNormal.points[i])))<1e-5);
 const forward=JSON.stringify(a.sample(a.jumpStart+.35));a.sample(5);a.sample(0);
 check('Reverse seek is deterministic '+label,forward===JSON.stringify(a.sample(a.jumpStart+.35)));
}
check('Procedural root trajectory unchanged',maxRootError<1e-9);
check('Pinned foot unchanged',maxPinError<1e-9);
check('All animated joints share the matched source and fall transition',maxJointError<1e-9);
console.log(JSON.stringify({passed:checks.length,maxRootError,maxPinError,maxJointError}));
