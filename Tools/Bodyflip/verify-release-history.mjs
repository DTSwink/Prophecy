// Unequal hand releases must read completed collision history, including seeks.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const dir='Saved/Diagnostics/BodyflipPort20261030';
const context=vm.createContext({readFile:p=>fs.readFileSync(p,'utf8'),print:()=>{}});
vm.runInContext(fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8'),context);
// Deterministic NN test callback: engine parity is separate from NN fidelity.
vm.runInContext(`
globalThis.__bodyflipAttack=id=>{const index=JSON.parse(readFile('Content/BodyflipLab/AttackIndex.json'));return readFile('Content/BodyflipLab/Attacks/'+index[id]);};
globalThis.__bodyflipNN=json=>{const r=JSON.parse(json),last=r.seeds.at(-1),origin=last.points[0];return JSON.stringify({names:r.names.slice(1),fps:30,duration:(r.frames-1)/30,roots:r.roots.slice(0,r.frames),poses:Array.from({length:r.frames},(_,i)=>({points:last.points.slice(1).map(p=>p.map((v,k)=>v-origin[k]+r.roots[i][k])),axes:last.axes.slice(1)}))});};
const B=BodyflipNative.raw;B({op:'assets',value:JSON.parse(readFile('Content/BodyflipLab/Assets.json'))});
B({op:'start',rigProfile:JSON.parse(readFile('Labs/BodyflipLab/fixtures/native-rig.json')),horizon:1/60,settings:{mode:'idle',motion:'kinematic',aim:false,spinLag:.6,trimOut:1.2,ramps:false,platforms:[{id:'floor',position:[0,-.2,0],size:[10,.4,20],rotation:[0,0,0,1]}],jumpEvents:[{id:'action',time:.1,jumpPercent:35,spinVersion:2,pushWith:'handBoth',flip:60,twist:35,attack:'none'}]}});
B({op:'sample',time:1.2});
`,context);
const evaluate=code=>vm.runInContext(code,context),sample=t=>evaluate(`B({op:'sample',time:${t}})`);
const frames=Array.from({length:73},(_,i)=>sample(i/60));
const event=frames.at(-1).events[0],releases=event.handReleases;
assert.equal(releases.length,2);
assert(Math.abs(releases[0].time-releases[1].time)>1/60,'Exercise unequal releases');
assert(releases.some(r=>r.early),'Exercise spin-forced early release');
let checks=2,maxBoundaryPosition=0,maxBoundaryAngle=0;const boundaries=[];
for(const release of releases){
 const a=sample(release.time-1e-5),b=sample(release.time+1e-5);
 for(let i=1;i<a.pose.points.length;i++){
  const distance=Math.hypot(...a.pose.points[i].map((v,k)=>v-b.pose.points[i][k]));
  const dot=Math.min(1,Math.abs(a.pose.q[i].reduce((v,q,k)=>v+q*b.pose.q[i][k],0)));
  const angle=2*Math.acos(dot);
  maxBoundaryPosition=Math.max(maxBoundaryPosition,distance);maxBoundaryAngle=Math.max(maxBoundaryAngle,angle);
  boundaries.push({side:release.side,bone:i,distance,angle});checks+=2;
 }
}
for(let i=frames.length-1;i>=0;i--){
 assert(frames[i].pose.points.flat().concat(frames[i].pose.q.flat()).every(Number.isFinite));
 assert.equal(JSON.stringify(sample(i/60)),JSON.stringify(frames[i]),'Reverse seek preserves complete frame '+i);checks+=2;
}
const result={passed:maxBoundaryPosition<.001&&maxBoundaryAngle<.01,checks,frames:frames.length,releases,maxBoundaryPosition,maxBoundaryAngle,boundaries};
fs.writeFileSync(dir+'/release-history.json',JSON.stringify(result,null,2));console.log(JSON.stringify({...result,boundaries:undefined}));
assert(maxBoundaryPosition<.001,'No position jump across hand release');
assert(maxBoundaryAngle<.01,'No rotation jump across hand release');
