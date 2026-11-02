'use strict';
// Compare a single initial boundary seed against the previous two-stage seed.
// Both implementations retain the same full canonical solver and actual poses.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),assert=require('node:assert/strict');
const K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js');
const file=path.resolve(__dirname,'live-stair-planner.cjs'),dir=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const oldBlock='   candidate=canonicalPlan(nextRun,nextSettings,terrain,seeded);counters.plans++;\n   host.diagnostics=seeded.diagnostics;\n   initialHistoryPending=false;';
const text=fs.readFileSync(file,'utf8').replace(/\r\n/g,'\n');
const first=text.indexOf('   // Queued actual receipts'),last=text.indexOf('   initialHistoryPending=false;',first)+'   initialHistoryPending=false;'.length;
assert(first>=0&&last>first,'Expected exact initial-boundary seam');
const newBlock=text.slice(first,last);
function load(candidate){
 const source=(candidate?text:text.replace(newBlock,oldBlock)).replace('return {plan,commit,accept,frame:', 'return {debug:()=>model,plan,commit,accept,frame:');
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
 if(rb.continuity.futureChangeReference==='pre-boundary candidate'){
  if(ra.continuity.futureChangeReference==='pre-boundary candidate')assert.equal(rb.continuity.futureChangeM,ra.continuity.futureChangeM);
  delete ra.continuity.futureChangeM;delete rb.continuity.futureChangeM;delete ra.continuity.futureChangeReference;delete rb.continuity.futureChangeReference;
 }
 assert.deepEqual(rb,ra,mode+' '+stage+' reply/gates');
 return {frames:am.frames.length,contactFrames:am.frames.filter(f=>f.feet.some(v=>v.contact)).length,diagnosticDifference};
}
async function main(){
 const capture=read('slow-live-request.json'),results=[];
 const inputs=[{mode:'captured-first-curb',options:{...capture,handoff:false},update:{acceptedFrames:capture.acceptedFrames}},...['walk-flat','walk-stairs','run-stairs','walk-down','run-down','walk-uneven'].map(mode=>({mode,...fixture(mode)}))];
 for(const {mode,options,update,next} of inputs){
  const a=original.create(options),b=changed.create(options),c0=process.cpuUsage(),ar=await a.plan(structuredClone(update)),ca=process.cpuUsage(c0),c1=process.cpuUsage(),br=await b.plan(structuredClone(update)),cb=process.cpuUsage(c1);
  const result={mode,baselinePlans:a.status.plans,candidatePlans:b.status.plans,baselineCPU:(ca.user+ca.system)/1000,candidateCPU:(cb.user+cb.system)/1000,initial:compare(a,b,ar,br,mode,'initial')};
  if(next)result.continuation=compare(a,b,await a.plan(structuredClone(next)),await b.plan(structuredClone(next)),mode,'continuation');
  else{
   const filtered=changed.create(options),packet={acceptedFrames:update.acceptedFrames.filter(e=>e.tick>=options.sourceStartTick)},fr=await filtered.plan(packet);
   result.filteredPrefix=compare(b,filtered,br,fr,mode,'discarded prefix');result.omittedActualFrames=update.acceptedFrames.length-packet.acceptedFrames.length;filtered.cancel();
  }
  results.push(result);console.log(JSON.stringify(result));a.cancel();b.cancel();
 }
 const report={passed:true,completeFrames:results.reduce((n,r)=>n+r.initial.frames+(r.continuation?.frames||0)+(r.filteredPrefix?.frames||0),0),completeCheckpoints:results.reduce((n,r)=>n+1+(r.continuation?1:0)+(r.filteredPrefix?1:0),0),diagnosticOnlyChange:'Consolidated initial futureChangeM now compares the pre-boundary candidate to the final proposal; safety, velocity, pins and constraints are unchanged.',results};
 fs.writeFileSync(path.join(dir,'live-initial-consolidation.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:true,completeFrames:report.completeFrames,completeCheckpoints:report.completeCheckpoints}));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
