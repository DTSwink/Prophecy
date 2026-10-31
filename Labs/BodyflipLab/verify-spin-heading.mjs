import assert from 'node:assert/strict';import fs from 'node:fs';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./spin.js'),manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),reference=C.poseFromShared(manifest),{names,parents}=manifest;let checks=0;
for(const yaw of [0,.4,2.8,-2.8])for(const basis of [reference.q[0],[0,0,0,1]])for(const noise of [-1e-12,0,1e-12]){
 const rotation=R.qexp([0,yaw,0]),q=R.unit(R.qm(rotation,R.unit([basis[0],basis[1]+noise,basis[2]-noise,basis[3]]))),heading=S.heading(q);assert(Math.abs(Math.atan2(Math.sin(heading-yaw),Math.cos(heading-yaw)))<1e-8);checks++;
 const pose={...reference,q:reference.q.map((v,i)=>i?R.qm(rotation,v):q)};
 for(const axis of [0,3,7]){const motion=S.create(()=>({pose}),{event:{spinVersion:2,flip:180,twist:0,turnIn:0,turnAxis:axis},settings:C.sanitize({spinInertia:0,spinLag:0}),names,parents,reference}),wanted=R.rotate(rotation,C.flipAxis(axis));assert(R.length(R.sub(motion.state(0).axis,wanted))<1e-8);checks++;}
}
console.log({passed:true,checks});
