'use strict';
// Baseline/current host planners; exact complete frames and state across exit
// and renewed stair contact. No NN, engine, canonical edits or packaged output.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),assert=require('node:assert/strict');
const K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js'),R=require('../../Labs/FootIKLab/recovery.js');
const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),file=path.join(__dirname,'live-stair-planner.cjs');
function load(text){const m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(__dirname);m._compile(text.replace('get source(){return clone(source);}','get checkpoint(){return model?.checkpoint;},get source(){return clone(source);}'),file);return m.exports;}
const packaged=process.argv.includes('--packaged'),before=load(fs.readFileSync(path.join(folder,'live-stair-planner-before-zero-influence.cjs'),'utf8')),after=packaged?require('./live-proof-runtime.cjs'):load(fs.readFileSync(file,'utf8'));
const input=JSON.parse(fs.readFileSync(path.join(folder,'walk-stairs.input.json'))),standard=T.create(input.settings);
function source(from,to,offset=0){const src=structuredClone(input.source);src.roots=src.roots.slice(from/4,to/4+1).map(v=>[v[0],v[1],v[2]+offset]);src.poses=src.poses.slice(from/4,to/4+1).map(p=>({...p,points:p.points.map(v=>[v[0],v[1],v[2]+offset])}));src.rootYawDegrees=src.roots.map(()=>0);src.duration=src.totalDuration=(to-from)/120;src.directionMeta={...src.directionMeta,totalDuration:src.duration};return src;}
function terrain(src,start,endpoint=false){return {rootStartTick:start,rootRows:src.roots.map((p,i)=>({time:i/30,position:[p[0],endpoint?1.68:standard.rootHeight(p[2]),p[2]]})),tiles:endpoint?[{id:'landing',point:[0,1.68,0],u:[1,0,0],v:[0,0,1],bounds:[-2,2,6.2,30],shaped:true},{id:'lower',point:[0,1.54,0],u:[1,0,0],v:[0,0,1],bounds:[-2,2,5.5,5.85],shaped:true}]:standard.tiles.map(t=>({id:t.id,point:[0,t.y,0],u:[1,0,0],v:[0,0,1],bounds:[t.x0,t.x1,t.z0,t.z1],shaped:t.id.startsWith('step')}))};}
let compared=0,pinFrames=0;
function equal(a,b,label){assert.equal(a.status.baseTick,b.status.baseTick);assert.equal(a.status.generatedThrough,b.status.generatedThrough);for(let i=a.status.baseTick;i<=Math.round(a.status.generatedThrough*120);i++){assert.equal(JSON.stringify(a.frame(i)),JSON.stringify(b.frame(i)),label+' frame '+i);compared++;if(a.frame(i).feet.some(f=>f.contact))pinFrames++;}if(!packaged)assert.deepEqual(a.checkpoint.plans.map(p=>p.flags),b.checkpoint.plans.map(p=>p.flags),label+' retained stance flags');}
async function main(){
 const started=performance.now(),cases=[];
 const endSource=source(0,96,7.5),endOptions={...input,source:endSource,terrain:terrain(endSource,0,true),origin:[0,0,0],handoff:false};
 let plans=[];for(const factory of [before,after]){const p=factory.create(endOptions),cpu=process.cpuUsage(),wall=performance.now();await p.plan();const used=process.cpuUsage(cpu);cases.push({branch:factory===before?'baseline':'optimized',cpuMs:(used.user+used.system)/1000,wallMs:performance.now()-wall});plans.push(p);}
 equal(...plans,'endpoint');for(const p of plans){for(let i=0;i<=48;i++)p.commit(i);}
 const endTail=source(44,144,7.5);for(const p of plans)await p.plan({source:endTail,sourceStartTick:44,terrain:terrain(endTail,44,true)});equal(...plans,'endpoint continued');for(const p of plans)p.cancel();
 const short=source(0,12),options={...input,source:short,terrain:terrain(short,0),origin:[0,0,0],handoff:false};plans=[before.create(options),after.create(options)];
 for(const p of plans)await p.plan();equal(...plans,'flat approach');assert(Array.from({length:13},(_,i)=>plans[0].frame(i).influence).every(v=>v===0));
 for(const p of plans)for(let i=0;i<=8;i++)p.commit(i);
 const stairs=source(4,240);for(const p of plans)await p.plan({source:stairs,sourceStartTick:4,terrain:terrain(stairs,4)});equal(...plans,'renewed stair influence');assert(pinFrames>0);
 for(const p of plans)for(let i=9;i<=240;i++)p.commit(i);
 const pinIndex=plans[0].frame(240).feet.findIndex(f=>f.contact);assert(pinIndex>=0,'Continuation boundary must carry a real material pin');
 const oldPin=structuredClone(plans[0].frame(240).feet[pinIndex].contact),tail=source(236,288);
 for(const p of plans)await p.plan({source:tail,sourceStartTick:236,terrain:terrain(tail,236)});equal(...plans,'material pin continuation');
 assert.deepEqual(plans[1].frame(240).feet[pinIndex].contact,packaged?JSON.parse(JSON.stringify(oldPin)):oldPin);if(!packaged)assert.deepEqual(plans[0].checkpoint.plans.map(p=>p.contacts),plans[1].checkpoint.plans.map(p=>p.contacts));for(const p of plans)p.cancel();
 const report={passed:true,packaged,completeFramesCompared:compared,materialPinFramesCompared:pinFrames,checkpointFlagsChecked:!packaged,laterNonzeroContinuationExact:true,activeMaterialPinPreserved:true,endpointTimings:cases,wallMs:performance.now()-started};fs.writeFileSync(path.join(folder,packaged?'live-zero-influence-packaged.json':'live-zero-influence.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(String(e));process.exitCode=1;});
