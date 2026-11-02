'use strict';
const K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js'),R=require('../../Labs/FootIKLab/recovery.js'),Live=require('./live-terrain.cjs');
const Boundary=require('./stair-boundary.cjs');
function run(input,angle,live=Live){
 const source=JSON.parse(JSON.stringify(input.source)),duration=Math.min(2,source.duration||source.totalDuration||2),count=Math.round(duration*30)+1;
 source.roots=source.roots.slice(0,count);source.poses=source.poses.slice(0,count);source.rootYawDegrees=source.rootYawDegrees?.slice(0,count);source.duration=source.totalDuration=duration;source.directionMeta={...source.directionMeta,totalDuration:duration};
 const standard=T.create(input.settings),q=R.qexp([0,angle*Math.PI/180,0]),turn=p=>R.rotate(q,p);
 const src={...source,roots:source.roots.map(turn),poses:source.poses.map(p=>({points:p.points.map(turn),axes:p.axes.map(a=>a.map(turn))})),rootYawDegrees:source.roots.map(()=>angle)};
 const snapshot={rootRows:source.roots.map((p,i)=>({time:i/30,position:turn([p[0],standard.rootHeight(p[2]),p[2]])})),tiles:standard.tiles.map(t=>({id:t.id,point:turn([0,t.y,0]),u:turn([1,0,0]),v:turn([0,0,1]),bounds:[t.x0,t.x1,t.z0,t.z1],shaped:t.id.startsWith('step')}))};
 const run=K.decode(src,input.parents),terrain=live.create(snapshot),roots=live.rootSampler(snapshot.rootRows),settings=K.sanitize(input.settings);
 const host={terrain,capture:true,origin:[0,0,0],rootAtTime:roots.at,travelAt:roots.direction,speedAt:roots.speed,headingAt:t=>K.rootHeading(run,t,settings),influence:(p,legs,t)=>terrain.influence(p,legs,roots.at(t)[1],K.geometry)};
 const model=K.prepare(run,settings,host),result={frames:model.frames,checkpoint:model.checkpoint};
 if(input.settings.terrain==='stairs'&&angle!==0){
  // Reproduce the second prospective pass after importing actual accepted
  // frames. The material pin and prior/current pose are boundary conditions.
  const first=model.frames.findIndex((f,i)=>i>=96&&i<model.frames.length-24&&f.feet.some((v,s)=>v.contact&&model.frames[i+4].feet[s].contact));
  if(first<0)throw Error('The second-pass fixture needs an actual retained material pin');
  const through=first+4;
  for(let i=0;i<=through;i++)Boundary.importFrame(model,i,model.frames[i],run.names);
  const seeded=K.prepare(run,settings,{...host,...Boundary.create(model,through)});
  for(let i=0;i<=through;i++)Boundary.importFrame(seeded,i,model.frames[i],run.names);
  result.seeded={frames:seeded.frames,checkpoint:seeded.checkpoint,through,materialPins:model.frames.slice(0,through+1).reduce((n,f)=>n+f.feet.filter(x=>x.contact).length,0)};
 }
 return result;
}
const api={run};globalThis.FootIKFloorCourse=api;module.exports=api;
