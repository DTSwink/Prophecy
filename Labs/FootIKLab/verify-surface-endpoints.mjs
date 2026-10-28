// From the repository root: node Labs/FootIKLab/verify-surface-endpoints.mjs
// Uses test-bank.cjs and the tracked data/{walk,run}-phases.{json,bin} + rig.json.
// No generated directional fixtures, running server, Python or Torch required.
// Runs all 16 cases sequentially and writes surface-endpoint-verification.json.
import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('./surface.js'),R=require('./recovery.js'),S=require('./support.js'),{load}=require('./test-bank.cjs');
const checks=[],cases=[],check=(name,ok)=>{assert(ok,name);checks.push(name);},dist=(a,b)=>R.length(R.sub(a,b));
const faces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]];
function clip(poly,axis,bound,sign){const out=[];if(!poly.length)return out;let a=poly.at(-1),da=sign*(a[axis]-bound);for(const b of poly){const db=sign*(b[axis]-bound);if((da>=0)!==(db>=0)){const t=da/(da-db);out.push(a.map((v,k)=>v+(b[k]-v)*t));}if(db>=0)out.push(b);a=b;da=db;}return out;}
function volumeDepth(p,names,side,surfaces){const l=S.leg(p,names,side),points=S.footPoints(p,l.foot,l.toe,side).map(o=>R.add(p.points[l.foot],o));let depth=0;for(const surface of surfaces){const local=points.map(surface.local),[x0,x1,z0,z1]=surface.bounds;for(const start of [0,8])for(const face of faces){let poly=face.map(i=>local[start+i]);for(const [axis,bound,sign] of [[0,x0,1],[0,x1,-1],[2,z0,1],[2,z1,-1]])poly=clip(poly,axis,bound,sign);for(const p of poly)depth=Math.max(depth,-p[1]);}}return depth;}
for(const upright of [0,1])for(const gait of ['walk','run'])for(const approach of ['toward','parallel'])for(const slopeAngle of [45,90]){
 const run=load(gait,.21),m=F.prepare(run,{gait,upright,approach,slopeAngle}),label=`${gait} ${approach} ${slopeAngle}deg Upright${upright}`;
 let finite=true,minRootGap=Infinity,maxVolumePenetration=0,velocityError=0,positionError=0,gravityError=0;
 for(let i=0;i<m.frames.length;i++){
  const f=m.frames[i],a=f.surface;finite&&=[...f.pose.points.flat(),...f.pose.q.flat(),...a.mass,...a.velocity,...a.acceleration].every(Number.isFinite);
  for(const s of m.terrain.surfaces){const p=s.local(a.mass),[x0,x1,z0,z1]=s.bounds;if(p[0]>=x0&&p[0]<=x1&&p[2]>=z0&&p[2]<=z1)minRootGap=Math.min(minRootGap,p[1]);}
  for(const side of ['L','R'])maxVolumePenetration=Math.max(maxVolumePenetration,volumeDepth(f.pose,run.names,side,m.terrain.surfaces));
  gravityError=Math.max(gravityError,dist(a.acceleration,R.add(a.gravity,R.add(a.supportForce,a.drive))));
  if(i+1<m.frames.length){const b=m.frames[i+1].surface,v=R.add(a.velocity,R.mul(a.acceleration,1/120));velocityError=Math.max(velocityError,dist(b.velocity,R.add(v,a.collisionImpulse)));positionError=Math.max(positionError,dist(b.mass,R.add(R.add(a.mass,R.mul(v,1/120)),a.collisionCorrection)));}
 }
 check(label+' finite poses/root',finite);
 check(label+' world gravity and root integration remain exact',velocityError<1e-9&&positionError<1e-9&&gravityError<1e-10);
 check(label+' capsule is clear from frame0 onward',minRootGap>=.22-1e-8);
 check(label+' full shoe faces clear finite planes',maxVolumePenetration<.0001);
 check(label+' accepted foot reach remains valid',m.metrics.maxReachError<1e-7&&m.metrics.maxContactDrift<1e-8);
 check(label+' no knee or ankle discontinuity',m.metrics.maxKneeStep<20&&m.metrics.maxAnkleStep<18);
 if(upright===1&&slopeAngle===90&&approach==='parallel'){
  check(label+' initial wall placement respects actual capsule radius',Math.abs(m.terrain.slope.local(m.frames[0].surface.mass)[1]-.22)<1e-9);
  check(label+' first sample does not eject22cm from wall',dist(m.frames[1].surface.mass,m.frames[0].surface.mass)<.06);
 }
 if(upright===1&&gait==='walk'&&slopeAngle===90&&approach==='toward'){
  const index=run.names.indexOf('calf_r'),a=m.frames[143],b=m.frames[144],step=R.length(R.qlog(R.qm(b.pose.q[index],R.qinv(a.pose.q[index]))))*180/Math.PI;
  check('Fully upright Walk wall72 avoids folded-leg pole spin before collision',step<12&&R.length(a.surface.collisionImpulse)===0&&!a.feet[1].contact&&!b.feet[1].contact);
 }
 cases.push({gait,upright,approach,slopeAngle,minRootGap,maxVolumePenetration,velocityError,positionError,gravityError,metrics:m.metrics});
}
const sourceSha256=crypto.createHash('sha256').update(fs.readFileSync(new URL('surface.js',import.meta.url))).digest('hex');
const report={passed:true,checks,cases,sourceSha256,fixes:["Keep the physical capsule extent and map its mesh root to the ground reference along the surface normal.","Preserve NN pelvis height/lower articulation in the surface frame; apply Upright around the pelvis.","Carry the signed stabilized NN knee hinge with its thigh, including straight samples; never choose an opposite bend to clear a plane.","Release with one position filter without turning collision projection into momentum."],limits:'Upright1 wall stances can legitimately fail contact/reach and fall; the test does not require them to climb.'};
fs.writeFileSync(new URL('surface-endpoint-verification.json',import.meta.url),JSON.stringify(report,null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,cases:cases.length,maxKnee:Math.max(...cases.map(c=>c.metrics.maxKneeStep)),maxAnkle:Math.max(...cases.map(c=>c.metrics.maxAnkleStep)),maxVolumePenetration:Math.max(...cases.map(c=>c.maxVolumePenetration)),sourceSha256}));
