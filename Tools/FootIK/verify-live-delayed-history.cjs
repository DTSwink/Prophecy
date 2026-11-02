'use strict';
// No inference or external worker: exercise delayed native publication with
// exact displayed raw/history samples and an explicitly bounded checkpoint.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const P=require('./live-stair-planner.cjs'),K=require('../../Labs/FootIKLab/footik.js'),R=require('../../Labs/FootIKLab/recovery.js');
const dir=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const input=JSON.parse(fs.readFileSync(path.join(dir,'walk-flat.input.json'))),run=K.decode(input.source,input.parents);
const packaged=process.argv.includes('--packaged');
function create(options){
 if(!packaged)return P.create(options);
 global.__footikNN=()=>{throw Error('Unexpected policy call in actual-source handoff proof');};
 require('node:vm').runInThisContext(fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8'));
 const native=global.FootIKNative.command,command=x=>JSON.parse(native(JSON.stringify(x))),epoch='delayed-history';let initialized=false;
 const status=()=>command({op:'status'});
 return {
  plan(update={}){const currentTick=update.acceptedFrames?.at(-1)?.tick??(initialized?Math.max(0,status().through):(options.initialHistory?.currentTick??options.sourceStartTick??0));const result=command({...options,...update,op:'liveEvaluate',epoch,currentTick});initialized=true;return result;},
  accept(acceptedFrames){return command({op:'liveCommit',acceptedFrames});},
  commit(tick){command({op:'liveCommit',through:tick});return command({op:'liveFrames',start:tick,count:1})[0];},
  frame(tick){return command({op:'liveFrames',start:tick,count:1})[0];},
  get status(){return status();},
  get source(){const s=status();return {duration:s.generatedThrough-s.baseTick/120};},
  cancel(){command({op:'close'});}
 };
}
function actual(tick){
 const t=tick/120,a=t*.12,q=R.qexp([0,a,0]),p=K.at(run,t%run.duration),root=[2*(1-Math.cos(a))/.12,.5,2*Math.sin(a)/.12];
 const pose={points:p.points.map(v=>R.add(root,R.rotate(q,R.sub(v,p.points[0])))),q:p.q.map(v=>R.qm(q,v))};
 pose.axes=pose.q.map(R.toAxes);
 return {pose,raw:pose,root,rootHeading:[Math.sin(a),0,Math.cos(a)],pelvisOffset:0,influence:0,
  feet:[20,24].map((bone,i)=>({side:i?'R':'L',state:'NN',target:pose.points[bone],contact:null,error:0,penetration:0}))};
}
function window(start,end,sample=actual){
 const poses=[],roots=[],rootYawDegrees=[],rootRows=[];
 for(let tick=start;tick<=end;tick+=4){const f=sample(tick),flat=f.raw.points.map(v=>[v[0],v[1]-.5,v[2]]);roots.push(flat[0]);poses.push({points:flat.slice(1),axes:f.raw.axes.slice(1)});rootYawDegrees.push(Math.atan2(f.rootHeading[0],f.rootHeading[2])*180/Math.PI);rootRows.push({time:(tick-start)/120,position:f.root});}
 const duration=(end-start)/120;
 return {source:{...input.source,roots,poses,rootYawDegrees,duration,totalDuration:duration,directionMeta:{...input.source.directionMeta,totalDuration:duration}},sourceStartTick:start,
  terrain:{rootStartTick:start,rootRows,tiles:[{id:'flat',point:[0,.5,0],u:[1,0,0],v:[0,0,1],bounds:[-100,100,-100,100],shaped:true}]}};
}
const entries=(from,to)=>Array.from({length:to-from+1},(_,i)=>({tick:from+i,frame:actual(from+i)}));
async function main(){
 const started=performance.now(),cpu=process.cpuUsage(),seed=window(0,60),settings={...input.settings,terrain:'flat'};
 const planner=create({...input,...seed,settings,handoff:false,origin:[0,0,0]});await planner.plan();
 // The old plan ended at60. The ordinary game kept displaying actual NN motion
 // until300 while its background solver was unavailable.
 let result=await planner.plan({...window(296,444),acceptedFrames:entries(0,300)});assert(result.ready);assert.equal(planner.status.through,300);
 assert.equal(planner.status.actualHistoryRebases,1);assert(planner.status.retainedFrames<=95);
 for(let t=planner.status.baseTick;t<=300;t++){assert.deepEqual(planner.frame(t).pose,actual(t).pose);assert.deepEqual(planner.frame(t).feet,actual(t).feet);}
 if(!packaged)assert.equal(planner.source.roots[0][1],0,'Navigation elevation must be removed once from raw policy history');
 assert.equal(planner.frame(300).root[1],.5,'Navigation carrier must remain present once in displayed history');
 assert.throws(()=>planner.accept([{tick:600,frame:actual(600)}]),/gap/,'Ordinary gap checks remain strict');
 // A10-second native retention cap explicitly discards an obsolete unacknowledged
 // prefix. Reconstruct only the final0.75s and the new prospective1.2s.
 result=await planner.plan({...window(1796,1944),acceptedFrames:entries(600,1800),acceptedHistoryCheckpoint:{startTick:600,endTick:1800}});
 assert(result.ready);assert.equal(planner.status.through,1800);assert(planner.status.retainedFrames<=95);assert(planner.source.duration<2.1);
 for(let t=planner.status.baseTick;t<=1800;t++)assert.deepEqual(planner.frame(t).pose,actual(t).pose);
 const bad=entries(1800,1920);bad.splice(30,1);
 await assert.rejects(async()=>planner.plan({...window(1916,2064),acceptedFrames:bad,acceptedHistoryCheckpoint:{startTick:1800,endTick:1920}}),/checkpoint has a gap/);
 const missingRaw=entries(1800,1920);delete missingRaw.find(e=>e.tick===1832).frame.raw;
 await assert.rejects(async()=>planner.plan({...window(1916,2064),acceptedFrames:missingRaw,acceptedHistoryCheckpoint:{startTick:1800,endTick:1920}}),/raw30Hz/);
 const malformedHeading=entries(1800,1920);malformedHeading.find(e=>e.tick===1832).frame.rootHeading=[0,1,0];
 await assert.rejects(async()=>planner.plan({...window(1916,2064),acceptedFrames:malformedHeading,acceptedHistoryCheckpoint:{startTick:1800,endTick:1920}}),/headings/);
 const malformedPose=entries(1800,1920);malformedPose.find(e=>e.tick===1859).frame.pose.points[1][0]=NaN;
 await assert.rejects(async()=>planner.plan({...window(1916,2064),acceptedFrames:malformedPose,acceptedHistoryCheckpoint:{startTick:1800,endTick:1920}}),/pose\/contact checkpoint/);
 assert.equal(planner.status.through,1800,'Invalid checkpoint must leave the accepted state intact');
 // Recovery must use fresh controller commands, then continue advancing; merely
 // keeping the old displayed boundary forever is not a successful handoff.
 const displayed=new Map(entries(1708,1800).map(e=>[e.tick,e.frame]));let current=1800,consumed=0,maxCurrentRootError=0,maxRetained=planner.status.retainedFrames;
 for(const mode of ['stop','reverse','turn','stop']){
  const anchor=displayed.get(current),heading=Math.atan2(anchor.rootHeading[0],anchor.rootHeading[2]),root=anchor.root.slice(),startTick=current;
  const sample=tick=>{
   if(tick<=startTick)return displayed.get(tick);
   const dt=(tick-startTick)/120,f=actual(tick),angle=mode==='turn'?heading+Math.PI/2*Math.min(1,dt/.3):heading;
   const nextRoot=mode==='stop'?root:mode==='reverse'?R.add(root,[-2*Math.sin(heading)*dt,0,-2*Math.cos(heading)*dt]):R.add(root,[2*dt,0,0]);
   const turn=R.qexp([0,angle-Math.atan2(f.rootHeading[0],f.rootHeading[2]),0]),pose={points:f.raw.points.map(v=>R.add(nextRoot,R.rotate(turn,R.sub(v,f.root)))),q:f.raw.q.map(q=>R.qm(turn,q))};pose.axes=pose.q.map(R.toAxes);
   return {...f,pose,raw:pose,root:nextRoot,rootHeading:[Math.sin(angle),0,Math.cos(angle)]};
  };
  result=await planner.plan(window(current-4,current+144,sample));assert(result.ready,'New '+mode+' command must publish');
  const applied=[];
  for(let tick=current+1;tick<=current+48;tick++){
   const frame=structuredClone(planner.commit(tick)),expected=sample(tick);
   maxCurrentRootError=Math.max(maxCurrentRootError,R.length(R.sub(frame.root,expected.root)));
   frame.rootHeading=expected.rootHeading;displayed.set(tick,frame);applied.push({tick,frame});consumed++;
  }
  planner.accept(applied);current+=48;maxRetained=Math.max(maxRetained,planner.status.retainedFrames);
 }
 assert.equal(consumed,192);assert.equal(planner.status.through,1992);assert(maxCurrentRootError<1e-8);assert(maxRetained<=145);
 // Retain real canonical material pins as well as airborne raw NN history.
 const stairs=JSON.parse(fs.readFileSync(path.join(dir,'walk-stairs.input.json'))),reference=K.prepare(K.decode(stairs.source,stairs.parents),stairs.settings);
 const last=reference.frames.findIndex((f,i)=>i>=240&&i<=340&&i%4===0&&f.feet.some(v=>v.contact));assert(last>=240);
 const crop=(from,to)=>{const source=structuredClone(stairs.source);source.poses=source.poses.slice(from/4,to/4+1);source.roots=source.roots.slice(from/4,to/4+1);source.rootYawDegrees=source.roots.map(()=>0);source.duration=source.totalDuration=(to-from)/120;source.directionMeta={...source.directionMeta,totalDuration:source.duration};return source;};
 const pins=create({...stairs,source:crop(0,60),handoff:false});await pins.plan();
 const receipts=Array.from({length:last+1},(_,tick)=>({tick,frame:{...structuredClone(reference.frames[tick]),rootHeading:[0,0,1]}}));
 result=await pins.plan({source:crop(last-4,last+144),sourceStartTick:last-4,acceptedFrames:receipts});assert(result.ready);
 for(let t=pins.status.baseTick;t<=last;t++){assert.deepEqual(pins.frame(t).pose.points,reference.frames[t].pose.points);assert.deepEqual(pins.frame(t).feet,packaged?JSON.parse(JSON.stringify(reference.frames[t].feet)):reference.frames[t].feet);}
 assert(pins.frame(last).feet.some(f=>f.contact),'Actual material pin survives the delayed boundary');
 const nonzero=create({...input,...window(480,540),settings,handoff:false,origin:[0,0,0],initialHistory:{previousTick:480,currentTick:484,previous:actual(480).pose,current:actual(484).pose}});
 result=await nonzero.plan();assert(result.ready);assert.equal(nonzero.status.through,484);assert.deepEqual(nonzero.frame(484).pose.points,actual(484).pose.points);assert.equal(nonzero.status.actualHistoryRebases,0);
 const used=process.cpuUsage(cpu),report={passed:true,packaged,delayedActualTicks:301,explicitCappedTicks:1201,retainedFrames:planner.status.retainedFrames,retainedSeconds:planner.source.duration,materialPinFrame:last,actualRebases:planner.status.actualHistoryRebases,strictGapAndRawValidation:true,nonzeroInitialEpoch:true,freshCommands:['stop','reverse','turn','stop'],consumedFreshFrames:consumed,maxCurrentRootErrorM:maxCurrentRootError,maxRetainedFrames:maxRetained,cpuMilliseconds:(used.user+used.system)/1000,wallMilliseconds:performance.now()-started};
 planner.cancel();pins.cancel();nonzero.cancel();fs.writeFileSync(path.join(dir,packaged?'live-delayed-history-packaged.json':'live-delayed-history.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
