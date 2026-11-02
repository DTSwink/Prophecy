import assert from 'node:assert/strict';
import fs from 'node:fs';
import {Vector3,Quaternion,Matrix4} from '../../MimicKitUEFN/vendor/three.module.js';
import {fk,setWorldRotation,solveIK,rotatePelvisKeepingFeet} from './kinematics.js';
const out=new URL('../../../Saved/MimicKitSlowLoco/pose-editor/',import.meta.url);
const m=JSON.parse(fs.readFileSync(new URL('model-test.json',out),'utf8'));
const cases=[['starting',m.base]];
const savedPath=new URL('current.json',out);
if(fs.existsSync(savedPath))cases.push(['saved',JSON.parse(fs.readFileSync(savedPath,'utf8')).frame]);
function floor(pose,body){
 const g=m.geometry.find(x=>x.body_id===body),q=pose.q[body].clone().multiply(new Quaternion().fromArray(g.local_q));
 const center=new Vector3().fromArray(g.local_p).applyQuaternion(pose.q[body]).add(pose.p[body]);
 const e=new Matrix4().makeRotationFromQuaternion(q).elements;
 return center.z-Math.abs(e[2])*g.size[0]-Math.abs(e[6])*g.size[1]-Math.abs(e[10])*g.size[2];
}
let maxPosition=0,maxAngle=0,maxFloor=0,count=0,limited=0;
for(const [name,base] of cases)for(const axis of [0,1,2])for(const degrees of [-90,-45,-20,-5,0,5,20,45,90])for(const limits of [false,true]){
 const f=base.slice(),before=fk(m,f),q=new Quaternion().setFromAxisAngle(new Vector3().setComponent(axis,1),degrees*Math.PI/180).multiply(before.q[0]);
 const result=rotatePelvisKeepingFeet(m,f,q,limits),after=fk(m,f);count++;if(result.fraction<.99999)limited++;
 assert(f.every(Number.isFinite));
 for(const body of [11,14]){
  const dp=before.p[body].distanceTo(after.p[body]),da=before.q[body].angleTo(after.q[body]),df=Math.abs(floor(after,body)-floor(before,body));
  maxPosition=Math.max(maxPosition,dp);maxAngle=Math.max(maxAngle,da);maxFloor=Math.max(maxFloor,df);
  assert(dp<1e-7,`${name} ${axis} ${degrees}: foot position drift ${dp}`);assert(da<1e-7);assert(df<1.1e-7);
 }
 assert.deepEqual(f.slice(0,3),base.slice(0,3));assert.deepEqual(f.slice(6,26),base.slice(6,26));
 // The upper body follows the requested root rotation; only the legs compensate.
 if(!limits&&Math.abs(degrees)<=20){assert.equal(result.fraction,1);assert(after.q[0].angleTo(q)<1e-7)}
}
// Reproduce a mouse drag: each event starts at the same drag snapshot.
const base=m.base.slice(),before=fk(m,base);
for(let degrees=0;degrees<=30;degrees+=.5){const f=base.slice(),q=new Quaternion().setFromAxisAngle(new Vector3(0,1,0),degrees*Math.PI/180).multiply(before.q[0]);rotatePelvisKeepingFeet(m,f,q);const after=fk(m,f);for(const body of [11,14])assert(before.p[body].distanceTo(after.p[body])<1e-7)}
const broken=base.slice();setWorldRotation(m,broken,0,new Quaternion().setFromAxisAngle(new Vector3(0,1,0),20*Math.PI/180).multiply(before.q[0]));
const originalFootDropCm=[11,14].map(i=>(floor(fk(m,broken),i)-floor(before,i))*100);
// Near full extension: an impossible target must limit the pelvis, not move a foot.
const extended=base.slice();
for(const [hip,foot] of [[9,11],[12,14]]){const p=fk(m,extended);solveIK(m,extended,foot,p.p[hip].clone().add(new Vector3(0,0,-10)))}
const extendedBefore=fk(m,extended);
for(const axis of [0,1,2])for(const degrees of [-45,45]){
 const f=extended.slice(),q=new Quaternion().setFromAxisAngle(new Vector3().setComponent(axis,1),degrees*Math.PI/180).multiply(extendedBefore.q[0]);
 const result=rotatePelvisKeepingFeet(m,f,q),after=fk(m,f);assert(result.fraction<1);
 for(const body of [11,14]){assert(extendedBefore.p[body].distanceTo(after.p[body])<1e-7);assert(extendedBefore.q[body].angleTo(after.q[body])<1e-7);assert(Math.abs(floor(after,body)-floor(extendedBefore,body))<1.1e-7)}
}
const report={passed:true,cases:count,drag_samples:61,unreachable_rotation_cases:6,limited_rotations:limited,max_foot_position_error_m:maxPosition,max_foot_rotation_error_rad:maxAngle,max_foot_floor_height_change_m:maxFloor,unrelated_joint_coordinates_exact:true,previous_uncompensated_20_degree_foot_floor_change_cm:originalFootDropCm};
fs.writeFileSync(new URL('pelvis-pinning-verification.json',out),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
