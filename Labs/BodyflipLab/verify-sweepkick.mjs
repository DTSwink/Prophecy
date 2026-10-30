import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js'),B=require('./airborne-motion.js'),A=require('./jump-attack.js'),Aim=require('./attack-aim.js'),K=require('./kick-attack.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),buffer=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),v=read('data/vanilla.json'),{names,parents}=m,reference=C.poseFromShared(m),meta=v.clips.find(c=>c.name==='sweepKick'),clip=C.decode(meta,buffer(meta.file),names,parents);
assert.equal(meta.frames,36);assert.equal(meta.fps,30);assert.deepEqual(meta.phases,{armed:8,hit:17});
assert.equal(meta.effector,'foot_r');assert.equal(C.effector(meta.name),'foot_r');assert(K.accepts(meta.name));assert.equal(C.sanitizeJump({attack:meta.name}).attack,meta.name);
assert.equal(createHash('sha256').update(fs.readFileSync(meta.source)).digest('hex'),meta.sourceSHA256,'Original FBX unchanged');
assert.equal(createHash('sha256').update(fs.readFileSync(new URL(meta.file,import.meta.url))).digest('hex'),meta.sha256);
assert.deepEqual(m.clips.find(c=>c.name===meta.name).variants[0].phases,meta.phases);
const previous=JSON.parse(execFileSync('git',['show','HEAD:Labs/BodyflipLab/data/manifest.json'],{maxBuffer:4e6}));
for(const c of previous.clips)assert.deepEqual(m.clips.find(n=>n.name===c.name),c,'Existing dataset family unchanged: '+c.name);
const oldModule={exports:{}};vm.runInNewContext(execFileSync('git',['show','HEAD:Labs/BodyflipLab/airborne-motion.js'],{encoding:'utf8'}),{module:oldModule,require});
let unchangedSamples=0,maxEntryError=0;
for(const name of ['KickL','KickR'])for(const directArmed of [false,true]){
 const metadata=v.clips.find(c=>c.name===name),source=C.decode(metadata,buffer(metadata.file),names,parents),args={clip:source,names,parents,reference,directArmed},before=oldModule.exports.recording(args),after=B.recording(args);
 for(let t=0;t<=after.lead;t+=1/240){const a=before.sample(t),b=after.sample(t);for(let i=0;i<names.length;i++)maxEntryError=Math.max(maxEntryError,R.length(R.sub(a.points[i],b.points[i])),R.length(R.qlog(R.qm(a.q[i],R.qinv(b.q[i])))));unchangedSamples++;}
}
assert(maxEntryError<1e-10,'Existing valid kick entries remain unchanged');
const deadlines=[];
for(const directArmed of [false,true]){
 const track=A.create({attack:meta.name},{sample:()=>({pose:reference}),airStart:.3,jumpStart:.3,abortTime:Infinity},new Map([[meta.name,clip]]),names,parents,{...C.defaults,kickToArmed:directArmed},reference),aim=Aim.create({clip,track,names,parents,reference,sampleHit:t=>track.sample(t).pose});
 assert(track.fullBodyKick);assert.equal(aim.deadline,'Hit');assert.equal(aim.ready,track.hitTime);assert(aim.weight(track.armedTime)<1);
 assert(Math.abs(track.hitTime-track.armedTime-9/30)<1e-10);deadlines.push({directArmed,armed:track.armedTime,hit:track.hitTime});
}
const result={clip:meta.name,frames:meta.frames,fps:meta.fps,phases:meta.phases,effector:meta.effector,circular:true,originalFamiliesUnchanged:previous.clips.length,unchangedSamples,maxEntryError,deadlines,sourceSHA256:meta.sourceSHA256,visualVerified:false};
fs.writeFileSync(new URL('sweepkick-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(result);
