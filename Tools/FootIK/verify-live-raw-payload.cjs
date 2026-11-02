'use strict';
// Transport contract only: no inference, engine process or pose algorithm change.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const dir=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const input=JSON.parse(fs.readFileSync(path.join(dir,'walk-flat.input.json')));
const expected=JSON.parse(fs.readFileSync(path.join(dir,'walk-flat.expected.json')));
const runtime=fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8');
function assemble(metadata,source,acceptedThrough,records,checkpoint=false){
 let text=metadata.slice(0,-1);
 const property=()=>{if(text.length>1)text+=',';};
 if(source){property();text+='"source":'+source;}
 if(acceptedThrough>=0){
  property();text+='"acceptedThrough":'+acceptedThrough+',"acceptedFrames":[';
  text+=records.map(([tick,frame])=>'{'+'"tick":'+tick+',"frame":'+frame+'}').join(',');text+=']';
  if(checkpoint&&records.length)text+=',"acceptedHistoryCheckpoint":{"startTick":'+records[0][0]+',"endTick":'+records.at(-1)[0]+'}';
 }
 return text+'}';
}
function source(from,to){const s=structuredClone(input.source);s.roots=s.roots.slice(from/4,to/4+1);s.poses=s.poses.slice(from/4,to/4+1);s.rootYawDegrees=s.rootYawDegrees?.slice(from/4,to/4+1)||s.roots.map(()=>0);s.duration=s.totalDuration=(to-from)/120;s.directionMeta={...s.directionMeta,totalDuration:s.duration};return s;}
const frame=tick=>({...structuredClone(expected.frames[tick]),raw:structuredClone(expected.frames[tick].raw||expected.frames[tick].pose),rootHeading:[0,0,1]});
const records=(from,to)=>Array.from({length:to-from+1},(_,i)=>[from+i,JSON.stringify(frame(from+i))]);
function checkEnvelope(meta,s,through,rows,checkpoint){
 const target=JSON.parse(meta);if(s)target.source=JSON.parse(s);
 if(through>=0){target.acceptedThrough=through;target.acceptedFrames=rows.map(([tick,value])=>({tick,frame:JSON.parse(value)}));if(checkpoint)target.acceptedHistoryCheckpoint={startTick:rows[0][0],endTick:rows.at(-1)[0]};}
 const text=assemble(meta,s,through,rows,checkpoint);assert.deepEqual(JSON.parse(text),target);return text;
}
const spelling='{"pose":{"points":[],"q":[]},"numbers":[-0,5e-324,1.7976931348623157e+308,9007199254740992,1.0000000000000002],"label":"quote\\\" slash\\\\ newline\\n snowman\\u2603"}';
const a=checkEnvelope('{"op":"liveEvaluate","epoch":"escaped\\\"epoch"}','{"sourceValue":-0}',12,[[11,spelling],[12,spelling]],true);
assert(Object.is(JSON.parse(a).acceptedFrames[0].frame.numbers[0],-0));assert(Object.is(JSON.parse(a).source.sourceValue,-0));
checkEnvelope('{}','{"sourceValue":17}',-1,[],false);
checkEnvelope('{"op":"liveEvaluate","source":{"manual":true}}','',-1,[],false);
for(const [from,to,checkpoint] of [[0,120,false],[118,124,false],[0,300,true]])checkEnvelope('{"op":"liveEvaluate"}',JSON.stringify(source(0,144)),to,records(from,to),checkpoint);
function instance(){const context=vm.createContext({performance,__footikNN:()=>{throw Error('No inference is permitted');}});vm.runInContext(runtime,context);const command=context.FootIKNative.command;return text=>JSON.parse(command(text));}
const old=instance(),raw=instance(),metadata={op:'liveEvaluate',epoch:'raw-transport',parents:input.parents,settings:{...input.settings,terrain:'flat'},origin:[0,0,0],currentTick:4,sourceStartTick:0,initialHistory:{previousTick:0,currentTick:4,previous:frame(0).pose,current:frame(4).pose}};
let checked=0;
for(const packet of [
 {metadata,source:source(0,144),through:-1,rows:[]},
 {metadata:{...metadata,initialHistory:undefined,currentTick:20,sourceStartTick:16},source:source(16,164),through:20,rows:records(0,20)},
 {metadata:{...metadata,initialHistory:undefined,currentTick:24,sourceStartTick:20},source:source(20,168),through:24,rows:records(18,24)}]){
 const envelope=checkEnvelope(JSON.stringify(packet.metadata),JSON.stringify(packet.source),packet.through,packet.rows,false),decoded=JSON.parse(envelope);
 const x=old(JSON.stringify(decoded)),y=raw(envelope);assert.equal(x.ready,y.ready);assert(x.ready);assert.equal(x.throughTick,y.throughTick);assert.deepEqual(x.frame,y.frame);
 const query=JSON.stringify({op:'liveFrameTexts',start:packet.metadata.currentTick,count:40});const p=old(query),q=raw(query);assert.deepEqual(p,q);checked+=p.length;
}
for(const command of [old,raw])command('{"op":"close"}');
const report={passed:true,sourceEnvelopes:6,packagedCommands:3,completeSerializedFramesCompared:checked,rawNumericSpellingsPreserved:true,signedZero:true,subnormalAndMaximumDouble:true,escapedText:true,manualAndPredictedSources:true,fullDeltaAndCheckpointPackets:true};
fs.writeFileSync(path.join(dir,'live-raw-payload.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
