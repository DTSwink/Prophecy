'use strict';
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),assert=require('node:assert/strict');
const K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js');
const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),file=path.join(__dirname,'live-stair-planner.cjs');
function load(text){const m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(__dirname);m._compile(text.replace('get source(){return clone(source);}','get checkpoint(){return model?.checkpoint;},get source(){return clone(source);}'),file);return m.exports;}
const before=load(fs.readFileSync(path.join(folder,'live-stair-planner-before-decode-cache.cjs'),'utf8')),after=load(fs.readFileSync(file,'utf8'));
let frames=0,pins=0,checkpoints=0;const cases=[];
function equal(a,b,label){assert.equal(a.status.baseTick,b.status.baseTick);assert.equal(a.status.generatedThrough,b.status.generatedThrough);for(let tick=a.status.baseTick;tick<=Math.round(a.status.generatedThrough*120);tick++){assert.deepEqual(a.frame(tick),b.frame(tick),label+' frame '+tick);frames++;if(a.frame(tick).feet.some(f=>f.contact))pins++;}assert.deepEqual(a.checkpoint,b.checkpoint,label+' full checkpoint');checkpoints++;}
async function main(){
 const allStart=performance.now();
 for(const name of ['walk-flat','walk-stairs','walk-down','run-uneven']){
  const input=JSON.parse(fs.readFileSync(path.join(folder,name+'.input.json'))),run=K.decode(input.source,input.parents),terrain=T.create(input.settings);
  function window(from,to){const source={...input.source,roots:input.source.roots.slice(from/4,to/4+1),poses:input.source.poses.slice(from/4,to/4+1),rootYawDegrees:Array.from({length:(to-from)/4+1},()=>0),duration:(to-from)/120,totalDuration:(to-from)/120};source.directionMeta={...source.directionMeta,totalDuration:source.duration};return {source,sourceStartTick:from,terrain:{rootStartTick:from,rootRows:source.roots.map((p,i)=>({time:i/30,position:[p[0],terrain.rootHeight(p[2]),p[2]]})),tiles:terrain.tiles.map(t=>({id:t.id,point:[0,t.y,0],u:[1,0,0],v:[0,0,1],bounds:[t.x0,t.x1,t.z0,t.z1],shaped:t.id.startsWith('step')||t.id.startsWith('tile')}))}};}
  function actual(tick){const p=K.at(run,tick/120),height=terrain.rootHeight(p.points[0][2]),pose={...p,points:p.points.map(v=>[v[0],v[1]+height,v[2]])};return {pose,raw:pose,root:pose.points[0],rootHeading:[0,0,1],pelvisOffset:0,influence:0,feet:[20,24].map((j,i)=>({side:i?'R':'L',state:'NN',target:pose.points[j],contact:null,error:0,penetration:0}))};}
  const initial=window(0,120),options={...input,...initial,origin:[0,0,0],handoff:false,initialHistory:{previousTick:0,currentTick:4,previous:actual(0).pose,current:actual(4).pose}},plans=[before.create(options),after.create(options)],timings=[];
  for(const p of plans){const t=performance.now();await p.plan();timings.push(performance.now()-t);}equal(...plans,name+' initial history');
  for(const p of plans)for(let tick=5;tick<=120;tick++)p.commit(tick);
  const tail=window(116,264);for(const p of plans)await p.plan(tail);equal(...plans,name+' seeded continuation');
  const receipts=Array.from({length:145},(_,i)=>({tick:120+i,frame:structuredClone(plans[0].frame(120+i))}));for(const e of receipts)e.frame.rootHeading=[0,0,1];
  for(const p of plans)p.accept(receipts);const final=window(260,384);for(const p of plans)await p.plan(final);equal(...plans,name+' material continuation');
  for(const p of plans)p.cancel();
  const short=window(0,48),delayed=[before.create({...input,...short,origin:[0,0,0],handoff:false}),after.create({...input,...short,origin:[0,0,0],handoff:false})];for(const p of delayed)await p.plan();
  const shown=Array.from({length:181},(_,tick)=>({tick,frame:actual(tick)}));for(const p of delayed)await p.plan({...window(176,324),acceptedFrames:shown});equal(...delayed,name+' expired candidate and queued actual');
  for(const p of delayed)p.cancel();cases.push({name,initialMs:timings});
 }
 const report={passed:true,completeFrames:frames,materialPinFrames:pins,completeCheckpoints:checkpoints,cases,wallMs:performance.now()-allStart};fs.writeFileSync(path.join(folder,'live-decode-cache.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
