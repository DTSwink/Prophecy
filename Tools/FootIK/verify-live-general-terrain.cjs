'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict');
const P=require('./live-stair-planner.cjs'),T=require('../../Labs/FootIKLab/terrain.js'),R=require('../../Labs/FootIKLab/recovery.js'),L=require('./live-terrain.cjs');
const K=require('../../Labs/FootIKLab/footik.js');
const input=JSON.parse(fs.readFileSync('Saved/Diagnostics/FootIKPort20261030/walk-stairs.input.json'));
const source=structuredClone(input.source),limit=76;source.poses=source.poses.slice(0,limit);source.roots=source.roots.slice(0,limit);source.rootYawDegrees=source.rootYawDegrees?.slice(0,limit);source.duration=source.totalDuration=(limit-1)/30;source.directionMeta={...source.directionMeta,totalDuration:source.duration};
const standard=T.create(input.settings),tiles=standard.tiles.map(t=>({...t,shaped:t.id.startsWith('step')})),rootRows=source.roots.map((p,i)=>({time:i/30,position:[p[0],standard.rootHeight(p[2]),p[2]]}));
function snapshot(angle){const turn=R.qexp([0,angle*Math.PI/180,0]),rotate=p=>R.rotate(turn,p);return {rootStartTick:0,tiles:tiles.map(t=>({id:t.id,shaped:t.shaped,point:rotate([0,t.y,0]),u:rotate([1,0,0]),v:rotate([0,0,1]),bounds:[t.x0,t.x1,t.z0,t.z1]})),rootRows:rootRows.map(r=>({...r,position:rotate(r.position)}))};}
function turnedSource(angle){const turn=R.qexp([0,angle*Math.PI/180,0]),rotate=p=>R.rotate(turn,p);return {...source,roots:source.roots.map(rotate),poses:source.poses.map(p=>({points:p.points.map(rotate),axes:p.axes.map(a=>a.map(rotate))})),rootYawDegrees:source.roots.map((p,i)=>(source.rootYawDegrees?.[i]||0)+angle)};}
async function main(){
 const results=[];let first;
 for(const angle of [0,90,180,37]){
  const start=performance.now(),terrain=snapshot(angle),planner=P.create({...input,source:turnedSource(angle),terrain,origin:[0,0,0],handoff:false});await planner.plan();
  const frames=Array.from({length:301},(_,i)=>planner.frame(i)),turn=R.qexp([0,-angle*Math.PI/180,0]);let maxError=0,pins=0,maxRoot=0,maxPenetration=0;
  for(let i=0;i<frames.length;i++){
   const f=frames[i];assert(f.pose.points.flat().every(Number.isFinite));pins+=f.feet.filter(v=>v.contact).length;
   maxRoot=Math.max(maxRoot,R.length(R.sub(f.root,terrain.rootRows[Math.floor(i/4)]?L.rootSampler(terrain.rootRows).at(i/120):[0,0,0])));
   maxPenetration=Math.max(maxPenetration,...f.feet.map(v=>v.penetration||0));
   if(first)for(let j=0;j<26;j++)maxError=Math.max(maxError,R.length(R.sub(R.rotate(turn,f.pose.points[j]),first[i].pose.points[j])));
  }
  first??=frames;assert(pins>0);assert(maxRoot<1e-8);assert(maxPenetration<1e-5);assert(maxError<5e-8,'Course rotation must not change the planned gait');
  results.push({angle,frames:frames.length,pins,maxRootErrorM:maxRoot,maxPenetrationM:maxPenetration,rotatedPlanDifferenceM:maxError,ms:performance.now()-start});
 }
 // One point can have different navigation elevations at different times.
 const loop=L.rootSampler([{time:0,position:[0,0,0]},{time:1,position:[2,1,0]},{time:2,position:[0,2,0]}]);
 assert.equal(loop.at(0)[1],0);assert.equal(loop.at(2)[1],2);assert.deepEqual(loop.direction(1.5),[-1,0,0]);
 const flatSnapshot=snapshot(37);flatSnapshot.tiles=flatSnapshot.tiles.map(t=>({...t,point:[t.point[0],.5,t.point[2]],shaped:true}));flatSnapshot.rootRows=flatSnapshot.rootRows.map(r=>({...r,position:[r.position[0],.5,r.position[2]]}));
 const flatSource=turnedSource(37),flat=P.create({...input,source:flatSource,terrain:flatSnapshot,handoff:false});await flat.plan();const run=K.decode(flatSource,input.parents);
 for(let i=0;i<=300;i++){const frame=flat.frame(i),raw=K.at(run,i/120);assert.equal(frame.influence,0);assert.deepEqual(frame.pose.points,raw.points.map(p=>R.add(p,[0,.5,0])));assert.deepEqual(frame.pose.q,raw.q);}
 const report={results,timedReverseRoot:true,flatExactNNFrames:301};fs.writeFileSync('Saved/Diagnostics/FootIKPort20261030/live-general-terrain.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
