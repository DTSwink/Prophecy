import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),B=require('./bounce.js'),F=require('./flight.js');
const checks=[],reports=[],check=(ok,label)=>{assert(ok,label);checks.push(label);};
for(const normal of [[0,1,0],[Math.SQRT1_2,Math.SQRT1_2,0],[1,0,0]])for(const skew of [0,.5,1]){
 const direction=R.rotate(R.qexp(R.mul(R.qlog(R.fromTo(normal,[0,1,0])),skew)),normal),hip=R.mul(normal,.7),incoming=R.add(R.mul(normal,-2),[0,0,3]);
 const b=B.create({root:[0,0,0],hip,foot:[0,0,0],normal,direction,incoming,reach:1,maxReach:.99,upperLength:.5,lowerLength:.5,loadMs:100,buildMs:100,rebound:.5,launchSpeed:4.5,cap:20,rolling:()=>({foot:[0,0,0],valid:true}),anchorOffset:()=>hip,carry:F.carryVelocity});
 const label=normal.join(',')+'/'+skew,loaded=b.sample(b.loadDuration),end=b.released;
 check(b.didPush,'Reachable push '+label);
 check(Math.abs(loaded.v[2]-end.v[2])<1e-7,'Retain tangent velocity '+label);
 check(R.dot(end.v,normal)>-1e-5,'Do not retain inward velocity '+label);
 check(R.dot(end.v,direction)<=b.extension.targetSpeed+1e-5,'Respect launch budget '+label);
 for(const t of [b.loadDuration,b.releaseTime]){
  const h=1e-6,a=b.sample(t-h),z=b.sample(t),c=b.sample(t+h);
  check(R.length(R.sub(c.p,a.p))<1e-4,'Continuous position '+label+':'+t);
  check(R.length(R.sub(c.v,a.v))<.02,'Continuous velocity '+label+':'+t);
  check(R.length(R.sub(R.mul(R.sub(c.p,z.p),1/h),z.v))<.02,'Velocity follows displacement '+label+':'+t);
 }
 for(let i=0;i<=32;i++){
  const f=b.sample(b.loadDuration+(b.releaseTime-b.loadDuration)*i/32);
  check(f.p.concat(f.v).every(Number.isFinite)&&R.length(f.v)<20,'Finite contact trajectory '+label+':'+i);
  check(R.length(R.add(f.p,hip))<=.990001,'No pinned leg stretch '+label+':'+i);
 }
 const at=b.releaseTime+.3,expected=JSON.stringify(b.sample(at));b.sample(5);b.sample(0);
 check(JSON.stringify(b.sample(at))===expected,'Seek independent '+label);
 reports.push({normal,skew,load:b.loadDuration,push:b.releaseTime-b.loadDuration,velocity:end.v,reason:b.extension.reason});
}
console.log(JSON.stringify({passed:true,checks:checks.length,reports},null,2));
