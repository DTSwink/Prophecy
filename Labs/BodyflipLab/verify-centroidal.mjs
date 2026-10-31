import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),M=require('./mass.js'),H=require('./momentum.js');
const manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),{names,parents}=manifest,reference=C.poseFromShared(manifest),rig=H.model(names,parents,reference);
const dist=(a,b)=>R.length(R.sub(a,b)),closeness=(a,b,tolerance,message)=>assert(dist(a,b)<tolerance,message+': '+dist(a,b));
let checks=0,maxResidual=0,maxLocal=0,maxCOM=0;const check=(label,yes)=>{assert(yes,label);checks++;};
const translated=(pose,v)=>({...pose,points:pose.points.map(p=>R.add(p,v))});
const local=R.localize(reference.points,reference.q,parents);
function articulated(t){const q=local.q.map(x=>x.slice());for(let i=2;i<q.length;i++){const amp=names[i].startsWith('spine')?.06:.17;q[i]=R.qm(q[i],R.qexp([amp*Math.sin(t*5+i),amp*.6*Math.cos(t*3-i),amp*.8*Math.sin(t*4+i/3)]));}return R.fk({p:local.p,q},parents);}
for(const dt of [1/60,1/120,1/240,1/480]){
 const a=articulated(.2),b=articulated(.2+dt),v=[1.3,-2.1,.7],offset=[9,-8,15],shiftA=translated(a,offset),shiftB=translated(b,R.add(offset,R.mul(v,dt)));
 closeness(H.momentum(a,b,rig,dt),H.momentum(shiftA,shiftB,rig,dt),1e-9,'Uniform translation must not change COM angular momentum');checks++;
 const omega=[1.1,-.7,2.3],spin=M.rotateAboutCOM(reference,R.qexp(R.mul(omega,dt)),rig),mid=M.rotateAboutCOM(reference,R.qexp(R.mul(omega,dt*.5)),rig),expected=M.product(M.tensor(mid,rig),omega),actual=H.momentum(reference,spin,rig,dt);
 check('Rigid rotation approaches I omega',dist(actual,expected)<.015*dt*60);
 for(const desired of [[0,0,0],[12,-5,3],[-7,15,9]]){
  const result=H.correct(a,b,desired,rig,dt),error=dist(result.momentum,desired),before=R.localize(b.points,b.q,parents),after=R.localize(result.pose.points,result.pose.q,parents);
  maxResidual=Math.max(maxResidual,error);check('Finite corrected momentum',result.momentum.every(Number.isFinite));
  check('Corrected momentum residual',error<.005);
  for(let i=2;i<parents.length;i++){maxLocal=Math.max(maxLocal,dist(R.qlog(R.qm(before.q[i],R.qinv(after.q[i]))),[0,0,0]),dist(before.p[i],after.p[i]));}
  maxCOM=Math.max(maxCOM,dist(M.center(b,rig),M.center(result.pose,rig)));
  check('Root anchor retained',result.pose.points[0]===b.points[0]||dist(result.pose.points[0],b.points[0])===0);
  if(desired.every(x=>x===0))check('Moving joints require a reaction even for zero total momentum',R.length(R.qlog(result.rotation))>1e-5);
 }
}
check('All physical joint-local poses preserved',maxLocal<1e-12);check('Candidate COM preserved',maxCOM<1e-12);
for(const I of [[[3,.2,-.3],[.2,2,.1],[-.3,.1,1]],[[1e-8,0,0],[0,3e-8,0],[0,0,2e-8]],[[1e8,2e6,0],[2e6,3e8,0],[0,0,2e8]]]){
 const expected=[1,-2,3],actual=H.solve(I,M.product(I,expected));closeness(actual,expected,1e-9,'Scaled SPD solve');checks++;
}
check('Degenerate zero inertia remains finite',H.solve([[0,0,0],[0,0,0],[0,0,0]],[1,2,3]).every(Number.isFinite));
assert.throws(()=>H.momentum(reference,reference,rig,0),/positive/);assert.throws(()=>H.solve([[NaN,0,0],[0,1,0],[0,0,1]],[0,0,0]),/Non-finite/);checks+=2;
closeness(H.velocity([[2,0,0],[0,3,0],[0,0,4]],[4,6,8],[2,3,4]),[1,1,1],1e-12,'Direct velocity formula');checks++;
// Known rigid correction oracle: recover the exact finite-difference momentum
// of that pose while preserving the arbitrary source articulation.
let maxOracle=0;for(let i=0;i<24;i++){const dt=1/240,a=articulated(i/40),b=articulated(i/40+dt),goal=M.rotateAboutCOM(b,R.qexp([.012*Math.sin(i),.015*Math.cos(i),.01]),rig),desired=H.momentum(a,goal,rig,dt),out=H.correct(a,b,desired,rig,dt);maxOracle=Math.max(maxOracle,out.error);check('Known correction oracle',out.error<.0002);}
const a=articulated(.2),b=articulated(.2+1/240);for(let i=0;i<100;i++)H.correct(a,b,[12,-5,3],rig,1/240);
let maxAxisError=0,maxAxisDeviation=0,maxTransverse=0;
for(const dt of [1/60,1/240])for(const axis of [[1,0,0],[0,1,0],[1,2,-3]]){
 const a=articulated(.4),b=articulated(.4+dt),direction=R.unit(axis),goal=M.rotateAboutCOM(b,R.qexp(R.mul(direction,.02)),rig),desired=H.momentum(a,goal,rig,dt);
 const result=H.correct(a,b,desired,rig,dt,{axis});maxAxisError=Math.max(maxAxisError,result.error);maxAxisDeviation=Math.max(maxAxisDeviation,R.length(R.cross(R.qlog(result.rotation),direction)));
 check('Fixed-axis finite-momentum oracle',result.error<.0001);
 const unrelated=R.add(desired,R.mul(R.unit(R.cross(direction,direction[0]>.9?[0,1,0]:[1,0,0])),4));
 const same=H.correct(a,b,unrelated,rig,dt,{axis});closeness(result.rotation,same.rotation,1e-10,'Transverse request cannot invent twist');checks++;
 maxTransverse=Math.max(maxTransverse,R.length(same.fullResidual));
}
check('Fixed-axis rotations remain on axis',maxAxisDeviation<1e-12);check('Transverse error is retained and reported',maxTransverse>3.9);
assert.throws(()=>H.correct(a,b,[0,0,0],rig,1/240,{axis:[0,0,0]}),/nonzero/);checks++;
const started=performance.now(),steps=1000;for(let i=0;i<steps;i++)H.correct(a,b,[12,-5,3],rig,1/240);const msPerStep=(performance.now()-started)/steps;
const result={passed:true,checks,bodies:rig.length,maxResidual,maxOracle,maxLocal,maxCOM,maxAxisError,maxAxisDeviation,maxTransverse,iterations:3,steps,msPerStep};
console.log(JSON.stringify(result,null,2));
