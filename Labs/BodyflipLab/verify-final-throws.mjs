import fs from 'node:fs';import crypto from 'node:crypto';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),A=require('./attack-aim.js'),J=require('./jump-attack.js'),read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),pkg=read('data/throws.json'),baked=read('../../Exports/Throws/FinalNoAim/clips.json'),meta=read('../../Exports/Throws/FinalNoAim/manifest.json'),manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest);T.load(pkg);let checks=0;
for(const file of ['clips.json','manifest.json'])assert.equal(pkg.finalNoAim.sha256[file],crypto.createHash('sha256').update(fs.readFileSync(new URL('../../Exports/Throws/FinalNoAim/'+file,import.meta.url))).digest('hex'));
const slashMeta=read('data/vanilla.json').clips.find(c=>c.name==='slashL'),bytes=fs.readFileSync(new URL(slashMeta.file,import.meta.url)),slashClip=C.decode(slashMeta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),names,parents);
const near=(a,b,label,tol=1e-9)=>{assert(R.length(R.sub(a,b))<tol,label);checks++;};
for(const entry of meta.clips){const m=T.model(entry.id,1),clip=baked.clips.find(c=>c.id===entry.id);assert(m.finalNoAim);assert.equal(m.clip.fps,60);for(let f=0;f<clip.frames.length;f++){const p=m.sample(f);for(let j=0;j<names.length;j++){near(p.points[j],clip.frames[f][j].slice(0,3),'exact final position');near(R.qlog(R.qm(p.q[j],R.qinv(clip.frames[f][j].slice(3)))),[0,0,0],'exact final rotation');}}
 const track=T.create({attack:entry.id,throwCharge:100},{sample:()=>({pose:reference}),airStart:0,jumpStart:0,abortTime:Infinity},null,names,parents,C.sanitize({distributePelvisTurn:true}),reference),at=t=>track.sample(t).pose,packet=track.launchAt(at(track.releaseTime));assert.equal(track.clip.meta.fps,60);near([track.releaseTime-track.start-track.duration],[(entry.releaseFrame-entry.armedFrame)/60],'source timing');near([R.length(packet.v)],[R.length(entry.launch.v)],'manifest launch magnitude');
 const plan=A.create({track,names,parents,reference,sampleHit:at,launchAt:p=>track.launchAt(p)});assert.equal(plan.weight(track.releaseTime),1);assert.equal(plan.weight(track.end),1);assert(Math.abs(plan.weight((track.end+track.returnEnd)/2)-.5)<1e-9);assert.equal(plan.weight(track.returnEnd),0);checks+=6;
 const slashPlan=A.create({clip:slashClip,track,names,parents,reference,sampleHit:at});
 const shared=J.create({attack:'slashL',throwCharge:100},{sample:()=>({pose:reference}),airStart:0,jumpStart:0,abortTime:Infinity},null,names,parents,C.sanitize({distributePelvisTurn:true}),reference,{clipOverride:track.clip});
 for(let k=0;k<=60;k++){const t=track.start+(track.returnEnd-track.start+.1)*k/60;near([plan.weight(t)],[slashPlan.weight(t)],'throw/slash share the same return envelope');const a=track.sample(t).pose,b=shared.sample(t).pose;for(let i=0;i<names.length;i++){near(a.points[i],b.points[i],'throw uses shared attack pose return');near(R.qlog(R.qm(a.q[i],R.qinv(b.q[i]))),[0,0,0],'throw uses shared attack rotation return');}}

}
// Source end marker must survive a different fast-Armed entry and playback rate.
for(const attackIn of [.1,.7])for(const throwSpeed of [.5,1,2]){
 const event={attack:'big-throw',attackDelay:.3,attackIn,attackOut:.25,throwSpeed},segment={sample:()=>({pose:reference}),airStart:.4,jumpStart:0,abortTime:Infinity},settings=C.sanitize({kickToArmed:true,distributePelvisTurn:true,motionCompensation:false}),track=T.create(event,segment,null,names,parents,settings,reference);
 assert.equal(track.match,25,'same direct-to-Armed entry as slashes');checks++;
 near([track.releaseTime-track.start-track.duration],[9/(60*throwSpeed)],'release follows Armed by source frame difference');
 near([track.end-track.releaseTime],[16/(60*throwSpeed)],'end follows Release by 50 minus 34 source frames');
 near([track.sourceFrame(track.end-track.start)],[50],'end is source F50 after variable entry');
 near([track.returnEnd-track.end],[C.attackReturn(settings).horizon],'return duration follows Attack out');
 assert(Math.abs(track.end-50/60)>1e-3,'end is not hardcoded scene frame 50');checks++;
}
console.log(JSON.stringify({passed:true,checks,source:'Exports/Throws/FinalNoAim',timingFPS:60,return:'shared duration-based return'}));
