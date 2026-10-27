import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),G=require('./space-gym.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),p=names.indexOf('pelvis'),s=names.indexOf('spine_01'),upper=A.bones(names,parents);
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),dist=(a,b)=>R.length(R.sub(a,b));
assert.equal(C.sanitize({}).pelvisAttackCompensation,.5);
assert.equal(C.sanitize({pelvisAttackCompensation:2}).pelvisAttackCompensation,1);
assert.equal(C.sanitize({pelvisAttackCompensation:-1}).pelvisAttackCompensation,0);
let samples=0,maxUpperError=0,maxLegLocalError=0,maxRatioError=0,maxBoundaryStep=0;
const base=t=>{const pose=C.centerPose(reference,R.qm(R.qexp([1.1,.3+t*.2,-.4]),reference.q[p]),[0,1.4,0]);return {pose,root:pose.points[0]};};
// An explicit 60-degree twist must produce -30 / -60 at the pelvis,
// even with the whole character tilted in space.
const initial=base(0).pose,local=R.localize(initial.points,initial.q,parents);
local.q[s]=R.qm(R.qexp([Math.PI/3,0,0]),local.q[s]);const posed=R.fk(local,parents);
for(const amount of [.5,1]){const actual=A.compensate(posed,initial,names,parents,amount),counter=R.qm(R.qinv(initial.q[p]),actual.q[p]);assert(angle(counter,R.qexp([-amount*Math.PI/3,0,0]))<1e-9);assert(angle(actual.q[s],posed.q[s])<1e-9);}
// Full-body kicks have separate viewer/app parity coverage in verify-kick-integration.mjs.
for(const meta of read('data/vanilla.json').clips.filter(c=>!C.effector(c.name).startsWith('foot_'))){
 const bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),clip=C.decode(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),names,parents),catalog=new Map([[meta.name,clip]]);
 const attacks=[0,.5,1].map(amount=>A.create({attack:meta.name},G.action({time:.5},base),catalog,names,parents,{...C.defaults,softAttackLegs:false,pelvisAttackCompensation:amount})),zero=attacks[0];
 for(let t=zero.start;t<zero.end+.25;t+=1/120){
  const a=attacks.map(x=>x.sample(t).pose),la=a.map(x=>R.localize(x.points,x.q,parents));
  for(let k=1;k<3;k++){
   for(const i of upper)maxUpperError=Math.max(maxUpperError,angle(a[k].q[i],a[0].q[i]));
   if(t<=zero.hitTime)for(let i=0;i<names.length;i++)if(i!==p&&i!==s)maxLegLocalError=Math.max(maxLegLocalError,angle(la[k].q[i],la[0].q[i]));
   assert(dist(a[k].points[p],a[0].points[p])<1e-9,'Pelvis position stays on its existing trajectory');
   for(let i=0;i<names.length;i++)assert(dist(la[k].p[i],la[0].p[i])<1e-9,'Keep physical joint sockets');
  }
  const half=R.qlog(R.qm(R.qinv(a[0].q[p]),a[1].q[p])),full=R.qlog(R.qm(R.qinv(a[0].q[p]),a[2].q[p]));
  maxRatioError=Math.max(maxRatioError,dist(R.mul(half,2),full));samples++;
 }
 for(const t of [zero.start,zero.start+zero.duration,zero.hitTime,zero.end,zero.end+.25]){
  const before=attacks[2].sample(t-1e-7).pose,after=attacks[2].sample(t+1e-7).pose;
  maxBoundaryStep=Math.max(maxBoundaryStep,...before.q.map((q,i)=>angle(q,after.q[i])));
 }
}
assert(maxUpperError<1e-9);assert(maxLegLocalError<1e-9);assert(maxRatioError<1e-9);assert(maxBoundaryStep<1e-4);
const result={samples,maxUpperError,maxLegLocalError,maxRatioError,maxBoundaryStep};
fs.writeFileSync(new URL('attack-compensation-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(result);
