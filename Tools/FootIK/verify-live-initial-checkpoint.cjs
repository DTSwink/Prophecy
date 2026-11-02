'use strict';
// Compare exact canonical contact-only initialization with its full first pass.
// The final canonical solve, retained material contacts and future are unchanged.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),assert=require('node:assert/strict');
const K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js');
const crypto=require('node:crypto');
const file=path.resolve(__dirname,'live-stair-planner.cjs'),dir=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const text=fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n');
const before=fs.readFileSync(path.join(dir,'live-stair-planner-before-initial-checkpoint.cjs'),'utf8');
const canonicalFile=path.resolve(__dirname,'../../Labs/FootIKLab/footik.js'),canonical=fs.readFileSync(canonicalFile,'utf8').replace(/\r\n/g,'\n');
const optionalSwing='   // An initializing host replaces every retained past sample with actual\n   // history. Keep shared weight updates/contact limits, omit its unused tail.\n   if(host.initialCheckpoint)continue;\n';
const guarded='  if(!host.initialCheckpoint){\n   for(let i=0;i<count;i++)targets[i]??=base[i].points[legs[i][side].foot];\n   for(let i=0;i<count;i++)if(weights[i]<1){\n    rotations[i]={footQ:qslerp(legs[i][side].footQ,rotations[i].footQ,weights[i]),toeQ:qslerp(legs[i][side].toeQ,rotations[i].toeQ,weights[i])};\n    offsets[i]=geometry(raw[i],legs[i][side],rotations[i]);\n   }\n  }';
const ordinary='  for(let i=0;i<count;i++)targets[i]??=base[i].points[legs[i][side].foot];\n  for(let i=0;i<count;i++)if(weights[i]<1){\n   rotations[i]={footQ:qslerp(legs[i][side].footQ,rotations[i].footQ,weights[i]),toeQ:qslerp(legs[i][side].toeQ,rotations[i].toeQ,weights[i])};\n   offsets[i]=geometry(raw[i],legs[i][side],rotations[i]);\n  }';
const optionalReturn=' if(host.initialCheckpoint)return host.initialCheckpoint({plans,legs,base,raw,speed,settings,terrain,fps,count});\n';
for(const seam of [optionalSwing,guarded,optionalReturn])assert.equal(canonical.split(seam).length,2,'Expected unique host seam');
const ordinarySource=canonical.replace(optionalSwing,'').replace(guarded,ordinary).replace(optionalReturn,''),ordinaryHash=crypto.createHash('sha256').update(ordinarySource).digest('hex');
assert.equal(ordinaryHash,'3237f4b9ca615c5e35fc4b892db731470797f354cd27599ae45075b864bfc045','Absent the opt-in, canonical arithmetic and all native-kernel dependencies must be byte-identical');
function load(candidate){
 const source=(candidate?text:before).replace('return {plan,commit,accept,frame:', 'return {debug:()=>model,plan,commit,accept,frame:');
 const mod=new Module(file,module);mod.filename=file;mod.paths=module.paths;mod._compile(source,file);return mod.exports;
}
const original=load(false),changed=load(true);
function firstDifference(a,b,where=''){
 if(Object.is(a,b))return null;if(typeof a!==typeof b||!a||!b||typeof a!=='object')return {where,a,b};
 if(Array.isArray(a)!==Array.isArray(b))return {where,a,b};
 const keys=Object.keys(a),other=Object.keys(b);if(keys.length!==other.length)return {where,keys,other};
 for(const k of keys){if(!Object.hasOwn(b,k))return {where,key:k};const d=firstDifference(a[k],b[k],where+'.'+k);if(d)return d;}return null;
}
const read=name=>JSON.parse(fs.readFileSync(path.join(dir,name)));
function fixture(name){
 const input=read(name+'.input.json'),expected=read(name+'.expected.json'),run=K.decode(input.source,input.parents),terrain=T.create(input.settings),origin=run.poses[0].points[0];
 const pinned=expected.frames.findIndex((f,i)=>i>=100&&i<420&&i%4===0&&f.feet.some(v=>v.contact)),current=pinned>=0?pinned:144,start=current-4;
 const crop=(from,to)=>{const source=structuredClone(input.source);source.poses=source.poses.slice(from/4,to/4+1);source.roots=source.roots.slice(from/4,to/4+1);source.rootYawDegrees=source.rootYawDegrees?.slice(from/4,to/4+1)||source.roots.map(()=>0);source.duration=source.totalDuration=(to-from)/120;source.directionMeta={...source.directionMeta,totalDuration:source.duration};return source;};
 const observed=tick=>{const f=structuredClone(expected.frames[tick]),raw=K.at(run,tick/120);f.raw={...raw,points:raw.points.map(v=>[v[0]-origin[0],v[1]+terrain.rootHeight(raw.points[0][2]-origin[2]),v[2]-origin[2]])};f.rootHeading=[0,0,1];return f;};
 const packet=(from,to)=>Array.from({length:to-from+1},(_,i)=>({tick:from+i,frame:observed(from+i)}));
 return {options:{...input,source:crop(start,current+60),sourceStartTick:start,origin,handoff:false,initialHistory:{previousTick:start,currentTick:current,previous:observed(start).pose,current:observed(current).pose}},update:{acceptedFrames:packet(0,current+4)},next:{source:crop(current+4,current+68),sourceStartTick:current+4,acceptedFrames:packet(current+2,current+8)}};
}
function compare(a,b,ar,br,mode,stage){
 const am=a.debug(),bm=b.debug();assert.equal(firstDifference(am.frames,bm.frames),null,mode+' '+stage+' frames');assert.equal(firstDifference(am.checkpoint,bm.checkpoint),null,mode+' '+stage+' checkpoint');
 const ra=structuredClone(ar),rb=structuredClone(br),diagnosticDifference={before:ra.continuity.futureChangeM,after:rb.continuity.futureChangeM};
 if(rb.continuity.futureChangeReference==='raw boundary checkpoint'){
  if(ra.continuity.futureChangeReference==='raw boundary checkpoint')assert.equal(rb.continuity.futureChangeM,ra.continuity.futureChangeM);
  delete ra.continuity.futureChangeM;delete rb.continuity.futureChangeM;delete ra.continuity.futureChangeReference;delete rb.continuity.futureChangeReference;
 }
 assert.deepEqual(rb,ra,mode+' '+stage+' reply/gates');
 return {frames:am.frames.length,contactFrames:am.frames.filter(f=>f.feet.some(v=>v.contact)).length,diagnosticDifference};
}
async function delayed(name,justPastTail=false){
 const input=read(name+'.input.json'),expected=read(name+'.expected.json'),run=K.decode(input.source,input.parents),terrain=T.create(input.settings),origin=run.poses[0].points[0];
 const pin=expected.frames.findIndex((f,i)=>i>=120&&i<=360&&i%4===0&&f.feet.some(v=>v.contact)),end=pin<0?144:pin;
 const crop=(from,to)=>{const source=structuredClone(input.source);source.poses=source.poses.slice(from/4,to/4+1);source.roots=source.roots.slice(from/4,to/4+1);source.rootYawDegrees=source.rootYawDegrees?.slice(from/4,to/4+1)||source.roots.map(()=>0);source.duration=source.totalDuration=(to-from)/120;source.directionMeta={...source.directionMeta,totalDuration:source.duration};return source;};
 const actual=tick=>{const frame=structuredClone(expected.frames[tick]),p=K.at(run,tick/120);frame.raw={...p,points:p.points.map(v=>[v[0]-origin[0],v[1]+terrain.rootHeight(p.points[0][2]-origin[2]),v[2]-origin[2]])};frame.rootHeading=[0,0,1];return frame;};
 const packet=(from,to)=>Array.from({length:to-from+1},(_,i)=>({tick:from+i,frame:actual(from+i)}));
 const options={...input,source:crop(0,justPastTail?end:60),origin,handoff:false},a=original.create(options),b=changed.create(options);
 await a.plan();await b.plan();
 const latest=justPastTail?end+2:end,first=justPastTail?end:end-4,update={source:crop(first,end+64),sourceStartTick:first,acceptedFrames:packet(0,latest)};
 const mode=name+(justPastTail?'-queued-active-model':'-expired-tail-rebase'),ar=await a.plan(structuredClone(update)),br=await b.plan(structuredClone(update));
 const initial=compare(a,b,ar,br,mode,'delayed');
 assert.equal(a.status.actualHistoryRebases,b.status.actualHistoryRebases);
 assert.equal(b.status.actualHistoryRebases>0,!justPastTail,'Fixture must exercise the intended retained-model branch');
 const next={source:crop(end,end+72),sourceStartTick:end,acceptedFrames:packet(latest-2,end+4)},continuation=compare(a,b,await a.plan(structuredClone(next)),await b.plan(structuredClone(next)),mode,'next');
 const result={mode,initial,continuation,actualHistoryRebases:b.status.actualHistoryRebases};a.cancel();b.cancel();return result;
}
async function main(){
 const capture=read('slow-live-request.json'),results=[];
 const inputs=[{mode:'captured-first-curb',options:{...capture,handoff:false},update:{acceptedFrames:capture.acceptedFrames}},...['walk-flat','run-flat','walk-stairs','run-stairs','walk-down','run-down','walk-uneven','run-uneven'].map(mode=>({mode,...fixture(mode)}))];
 const unsupported=fixture('walk-stairs');unsupported.options.initialHistory.previousTick++;unsupported.update.acceptedFrames=unsupported.update.acceptedFrames.filter(e=>e.tick>unsupported.options.sourceStartTick);inputs.push({mode:'unsupported-incomplete-prefix',...unsupported});
 const initialOnly=fixture('run-stairs');initialOnly.update={};delete initialOnly.next;inputs.push({mode:'initial-pair-only',...initialOnly});
 const receiptsOnly=fixture('walk-down');delete receiptsOnly.options.initialHistory;inputs.push({mode:'receipts-only-prefix',...receiptsOnly});
 for(const {mode,options,update,next} of inputs){
  const a=original.create(options),b=changed.create(options),c0=process.cpuUsage(),ar=await a.plan(structuredClone(update)),ca=process.cpuUsage(c0),c1=process.cpuUsage(),br=await b.plan(structuredClone(update)),cb=process.cpuUsage(c1);
  const result={mode,baselinePlans:a.status.plans,candidatePlans:b.status.plans,baselineCPU:(ca.user+ca.system)/1000,candidateCPU:(cb.user+cb.system)/1000,initial:compare(a,b,ar,br,mode,'initial')};
  if(next)result.continuation=compare(a,b,await a.plan(structuredClone(next)),await b.plan(structuredClone(next)),mode,'continuation');
  else if(update.acceptedFrames){
   const filtered=changed.create(options),packet={acceptedFrames:update.acceptedFrames.filter(e=>e.tick>=options.sourceStartTick)},fr=await filtered.plan(packet);
   result.filteredPrefix=compare(b,filtered,br,fr,mode,'discarded prefix');result.omittedActualFrames=update.acceptedFrames.length-packet.acceptedFrames.length;filtered.cancel();
  }
  results.push(result);console.log(JSON.stringify(result));a.cancel();b.cancel();
 }
 for(const name of ['walk-flat','run-flat','walk-stairs','run-stairs','walk-down','run-down','walk-uneven','run-uneven']){const result=await delayed(name);results.push(result);console.log(JSON.stringify(result));}
 for(const name of ['walk-stairs','run-down']){const result=await delayed(name,true);results.push(result);console.log(JSON.stringify(result));}
 const timings=[];
 for(const which of [false,true,true,false]){const p=(which?changed:original).create({...capture,handoff:false}),start=process.cpuUsage();await p.plan({acceptedFrames:capture.acceptedFrames});const used=process.cpuUsage(start);timings.push({candidate:which,cpuMs:(used.user+used.system)/1000});p.cancel();}
 const mean=which=>timings.filter(t=>t.candidate===which).reduce((n,t)=>n+t.cpuMs,0)/2;
 const report={passed:true,completeFrames:results.reduce((n,r)=>n+r.initial.frames+(r.continuation?.frames||0)+(r.filteredPrefix?.frames||0),0),completeCheckpoints:results.reduce((n,r)=>n+1+(r.continuation?1:0)+(r.filteredPrefix?1:0),0),ordinaryBodySha256:ordinaryHash,nativeKernelBodiesUnchanged:true,diagnosticOnlyChange:'Initial futureChangeM compares the raw checkpoint seed to the final proposal; safety, velocity, pins and constraints are unchanged.',timingABBA:{timings,baselineMs:mean(false),candidateMs:mean(true),speedup:mean(false)/mean(true)},results};
 fs.writeFileSync(path.join(dir,'live-initial-checkpoint.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:true,completeFrames:report.completeFrames,completeCheckpoints:report.completeCheckpoints}));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
