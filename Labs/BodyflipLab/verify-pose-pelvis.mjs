// Regression for the reported stationary Snatch / zero-wobble scene.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js'),F=require('./flight.js'),G=require('./space-gym.js'),I=require('./idle.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),m=read('data/manifest.json'),b=fs.readFileSync(new URL('data/idle.bin',import.meta.url)),idle=I.create(read('data/idle.json'),b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),m).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),reference=C.poseFromShared(m),error=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
const settings=C.sanitize({mode:'spaceGym',spaceFallAnimation:true,jumpBlend:.4,momentum3D:false,spinLag:.6,poseTuning:Object.fromEntries(['pose1','pose2','pose3','pose4'].map(id=>[id,{wobbleAmplitude:0}]))}),event={id:'first',time:58/60,spinVersion:2,instantSpin:true,jumpPercent:0,attack:'none',flip:0,twist:0,pose:'pose2'},rows=[];
for(const pose of ['pose1','pose2','pose3','pose4']){
 const e={...event,pose},sequence=G.sequence(idle,jumps,settings,m.parents,[e],null,reference),first=sequence.sample(2),base=G.sequence(idle,jumps,settings,m.parents,[{...e,pose:'none'}],null,reference);let sway=0,baselineSway=0;
 for(let t=2;t<4.7;t+=1/60){const f=sequence.sample(t);assert(!f.physical&&!f.spin.active);sway=Math.max(sway,...f.pose.q.map((q,i)=>i?error(q,first.pose.q[i]):0));baselineSway=Math.max(baselineSway,error(base.sample(t).pose.q[1],base.sample(2).pose.q[1]));}assert(sway<1e-10,'zero-wobble pose stays still');assert(baselineSway>.01,'fixture catches underlying idle sway');
 const clear={id:'clear',time:5,spinVersion:2,jumpPercent:0,pose:'none',poseOut:.3},changed=G.sequence(idle,jumps,settings,m.parents,[e,clear],null,reference);assert(error(changed.sample(6).pose.q[1],base.sample(6).pose.q[1])<1e-10,'No pose restores animated pelvis');
 const spinning=G.sequence(idle,jumps,settings,m.parents,[{...e,flip:120,twist:90}],null,reference);const a=spinning.sample(2),z=spinning.sample(2.5);assert(error(a.pose.q[1],z.pose.q[1])>.1,'commanded body rotation continues');
 const hold=JSON.stringify(spinning.sample(2));spinning.sample(4);spinning.sample(1);assert.equal(JSON.stringify(spinning.sample(2)),hold,'seek deterministic');rows.push({pose,sway,baselineSwayDegrees:baselineSway*180/Math.PI});
}
console.log(JSON.stringify({passed:true,rows}));
