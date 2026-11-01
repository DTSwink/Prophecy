import fs from 'node:fs';import assert from 'node:assert/strict';import vm from 'node:vm';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),K=require('./kick-attack.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);},m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),pelvis=names.indexOf('pelvis'),chain=[1,2,3,4,5].map(i=>names.indexOf('spine_0'+i)),metadata=read('data/vanilla.json'),catalog=new Map(metadata.clips.map(c=>[c.name,C.decode(c,bytes(c.file),names,parents)])),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
let samples=0,maxShareError=0,maxTopError=0,maxBaseError=0,maxBoundaryError=0,maxTransferStep=0;
for(const [name,clip] of catalog){if(K.accepts(name))continue;const original=JSON.stringify(clip.poses);let previous=null;
for(let f=0;f<=clip.poses.length-1;f+=.25){const raw=A.at(clip,f,parents),first=clip.locals[0],turned=A.attackAt(clip,f,names,parents,true),delta=R.qm(R.qinv(first.q[pelvis]),raw.q[pelvis]),share=R.length(R.qlog(delta))/5;
for(const i of chain)maxShareError=Math.max(maxShareError,Math.abs(angle(turned.q[i],raw.q[i])-share));
const source=R.fk(raw,parents),distributed=R.fk(turned,parents);maxTopError=Math.max(maxTopError,angle(source.q[chain[4]],distributed.q[chain[4]]));
if(previous)for(const i of chain)maxTransferStep=Math.max(maxTransferStep,angle(previous.q[i],turned.q[i]));previous=turned;samples++;
for(let i=0;i<names.length;i++)if(i!==pelvis&&!chain.includes(i))assert.equal(angle(raw.q[i],turned.q[i])<1e-8,true);
}
assert.equal(JSON.stringify(clip.poses),original);
for(const direct of [false,true]){const base=()=>({pose:reference}),settings={...C.defaults,kickToArmed:direct,motionCompensation:false,distributePelvisTurn:true},track=A.create({attack:name,attackIn:.2},{sample:base,airStart:0,jumpStart:0,abortTime:Infinity},catalog,names,parents,settings,reference);
for(let t=track.start;t<track.returnEnd;t+=1/120)maxBaseError=Math.max(maxBaseError,angle(track.sample(t).pose.q[pelvis],reference.q[pelvis]));
for(const t of [track.start,track.start+track.duration,track.hitTime,track.end,track.returnEnd]){const a=track.sample(t-1e-7).pose,b=track.sample(t+1e-7).pose;for(const i of [pelvis,...chain])maxBoundaryError=Math.max(maxBoundaryError,angle(a.q[i],b.q[i]));}
}}
assert(maxShareError<1e-8);assert(maxTopError<1e-8);assert(maxBaseError<1e-8);assert(maxBoundaryError<1e-4);assert(maxTransferStep<.5,'No introduced branch flip in source spine distribution');
// Actual manual legacy entry and regeneration key.
const app=fs.readFileSync(new URL('app.js',import.meta.url),'utf8'),clip=catalog.get('slashL'),settings=C.sanitize({attack:'slashL',distributePelvisTurn:true,motionCompensation:false}),context={R,C,BodyflipJumpAttack:A,BodyflipKickAttack:K,names,parents,idle:reference,clip,settings,clamp:(v,a,b)=>Math.max(a,Math.min(b,v))};vm.createContext(context);vm.runInContext(app.slice(app.indexOf('function manualPose('),app.indexOf('function manualSoft(')),context);const actual=context.manualPose(.5,reference);assert(angle(actual.q[pelvis],reference.q[pelvis])<1e-8);
vm.runInContext(app.slice(app.indexOf('function motionKey(){'),app.indexOf('async function prepareRun(')),context);const enabled=context.motionKey();settings.distributePelvisTurn=false;assert.notEqual(context.motionKey(),enabled);assert.equal(C.sanitize().distributePelvisTurn,false);assert.equal(C.sanitize({distributePelvisTurn:true}).distributePelvisTurn,true);
const report={passed:true,samples,maxShareError,maxTopError,maxBaseError,maxBoundaryError,maxTransferStep};fs.mkdirSync(new URL('../../Saved/Diagnostics/BodyflipAuthoredPelvis/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/Diagnostics/BodyflipAuthoredPelvis/distribution.json',import.meta.url),JSON.stringify(report,null,2));console.log(report);
