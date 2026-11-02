'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const P=require('./live-stair-planner.cjs'),K=require('../../Labs/FootIKLab/footik.js'),R=require('../../Labs/FootIKLab/recovery.js');
const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),input=JSON.parse(fs.readFileSync(path.join(folder,'walk-flat.input.json'))),run=K.decode(input.source,input.parents);
// Bounded single-process check; report CPU and wall separately. BelowNormal
// can starve for minutes while the user's editor is active.
function window(startTick,endTick){
 const from=startTick/120,end=endTick/120,roots=[],poses=[];
 for(let tick=startTick;tick<=endTick;tick+=4){
  const time=tick/120,p=K.at(run,time%run.duration),root=[0,0,2*time],delta=R.sub(root,p.points[0]);
  roots.push(root);poses.push({points:p.points.slice(1).map(v=>R.add(v,delta)),axes:p.axes.slice(1)});
 }
 return {...input.source,roots,poses,duration:end-from,totalDuration:end-from,rootYawDegrees:roots.map(()=>0),directionMeta:{...input.source.directionMeta,totalDuration:end-from}};
}
async function main(){
 const referenceRun=K.decode(window(0,2400),input.parents),started=performance.now(),cpu=process.cpuUsage(),planner=P.create({...input,source:window(0,240),settings:{...input.settings,terrain:'flat'},handoff:false});
 await planner.plan();let maxRetained=0,maxRootError=0,maxPositionError=0;
 for(let second=0;second<=20;second++){
  const tick=second*120;
  for(let i=planner.status.through+1;i<=tick;i++){
   const frame=planner.commit(i),reference=K.at(referenceRun,i/120),root=[0,0,i/60];
   maxRootError=Math.max(maxRootError,R.length(R.sub(frame.root,root)));
   for(let bone=0;bone<26;bone++)maxPositionError=Math.max(maxPositionError,R.length(R.sub(frame.pose.points[bone],R.add(root,R.sub(reference.points[bone],reference.points[0])))));
  }
  maxRetained=Math.max(maxRetained,planner.status.retainedFrames);
  if(second===20)break;
  const start=Math.max(0,tick-88),next=await planner.plan({source:window(start,tick+144),sourceStartTick:start});
  assert(next.ready,'Rebase rejected at '+second+': '+JSON.stringify(next.continuity));
 }
 assert(maxRootError<1e-8,'Root error '+maxRootError);assert(maxPositionError<1e-8,'Pose error '+maxPositionError);assert(maxRetained<=216,'Retained '+maxRetained);assert(planner.status.rebases>10);
 const used=process.cpuUsage(cpu),report={passed:true,seconds:20,ticks:2401,maxRootErrorM:maxRootError,maxPositionErrorM:maxPositionError,maxRetainedFrames:maxRetained,rebases:planner.status.rebases,planCpuMilliseconds:(used.user+used.system)/1000,wallMilliseconds:performance.now()-started,status:planner.status,note:'Repeated bounded-history rebases and exact flat NN passthrough; this is not an arbitrary staircase-turn or visual-quality test.'};
 planner.cancel();assert.equal(planner.status.retainedFrames,0);fs.writeFileSync(path.join(folder,'live-rebase.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
