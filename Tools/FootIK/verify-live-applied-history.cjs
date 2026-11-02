'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const P=require('./live-stair-planner.cjs'),K=require('../../Labs/FootIKLab/footik.js');
const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const input=JSON.parse(fs.readFileSync(path.join(folder,'walk-flat.input.json'))),run=K.decode(input.source,input.parents);
const source={...input.source,poses:input.source.poses.slice(0,17),roots:input.source.roots.slice(0,17),rootYawDegrees:input.source.rootYawDegrees?.slice(0,17),duration:16/30,totalDuration:16/30};
source.directionMeta={...source.directionMeta,totalDuration:source.duration};
async function main(){
 const start=performance.now(),cpu=process.cpuUsage(),previous=K.at(run,0),current=K.at(run,1/30);
 const p=P.create({...input,source,settings:{...input.settings,terrain:'flat'},handoff:false,initialHistory:{previousTick:0,currentTick:4,previous,current}});
 let result=await p.plan();assert(result.ready);assert.equal(p.status.through,4);assert.equal(p.status.initialHistoryFrames,5);
 assert.deepEqual(p.frame(4).pose.points,current.points);assert.deepEqual(p.frame(4).pose.q,current.q);
 const applied=Array.from({length:8},(_,i)=>({tick:i+5,frame:structuredClone(p.frame(i+5))}));
 // An asynchronously completed candidate is not proof of which frames were
 // actually displayed. Import a distinguishable host-owned contact receipt.
 applied[7].frame.feet[0].hostReceipt='actually-displayed-plan-A';
 p.accept(applied);assert.equal(p.status.through,12);assert.equal(p.frame(12).feet[0].hostReceipt,'actually-displayed-plan-A');
 result=await p.plan({source,sourceStartTick:0});assert(result.ready);assert.equal(p.frame(12).feet[0].hostReceipt,'actually-displayed-plan-A');
 assert.throws(()=>p.accept([{tick:14,frame:applied[7].frame}]),/gap/);
 const longer={...source,poses:input.source.poses.slice(0,25),roots:input.source.roots.slice(0,25),rootYawDegrees:input.source.rootYawDegrees?.slice(0,25),duration:.8,totalDuration:.8};longer.directionMeta={...longer.directionMeta,totalDuration:.8};
 const actual=K.prepare(K.decode(longer,input.parents),{...input.settings,terrain:'flat'});
 p.accept(Array.from({length:60},(_,i)=>({tick:13+i,frame:actual.frames[13+i]})));assert.equal(p.status.queuedAppliedFrames,8);
 result=await p.plan({source:longer,sourceStartTick:0});assert(result.ready);assert.equal(p.status.through,72);assert.equal(p.status.queuedAppliedFrames,0);assert.deepEqual(p.frame(72).pose.points,actual.frames[72].pose.points);
 const used=process.cpuUsage(cpu),report={passed:true,actualInitialSamples:5,importedAppliedSamples:68,deferredActualSamplesBeyondOldPrediction:8,prefixAndContactReceiptPreserved:true,cpuMilliseconds:(used.user+used.system)/1000,wallMilliseconds:performance.now()-start,status:p.status};
 p.cancel();assert.equal(p.status.retainedFrames,0);fs.writeFileSync(path.join(folder,'live-applied-history.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
