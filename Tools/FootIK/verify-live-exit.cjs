'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const E=require('./live-exit.cjs'),K=require('../../Labs/FootIKLab/footik.js'),S=require('../../Labs/FootIKLab/support.js'),R=require('../../Labs/FootIKLab/recovery.js'),H=require('../../Labs/FootIKLab/handoff.js');
const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const input=JSON.parse(fs.readFileSync(path.join(folder,'walk-stairs.input.json'))),run=K.decode(input.source,input.parents),names=run.names;
const pose=structuredClone(K.at(run,.4)),origin=pose.points[0].slice();pose.points=pose.points.map(p=>R.sub(p,origin));
const lowest=Math.min(...['L','R'].flatMap(side=>{const l=S.leg(pose,names,side);return S.footPoints(pose,l.foot,l.toe,side).map(o=>pose.points[l.foot][1]+o[1]);}));
for(let i=1;i<pose.points.length;i++)pose.points[i][1]+=.10-lowest;
const base={frame:{pose,root:[0,0,0],influence:.7,feet:[{side:'L',contact:null,state:'SWING'},{side:'R',contact:null,state:'SWING'}]},currentTick:120,names,
 terrain:{rootStartTick:0,tiles:[{id:'landing',point:[0,0,0],u:[1,0,0],v:[0,0,1],bounds:[-4,4,-4,4]}],rootRows:[{time:0,position:[0,0,-1]},{time:1,position:[0,0,0]},{time:2,position:[0,0,1]}]}};
let checks=0;
const check=(a,wanted,label)=>{const before=JSON.stringify(a),actual=E.evaluate(a);assert.equal(actual.eligible,wanted,label+': '+JSON.stringify(actual));assert.equal(JSON.stringify(a),before,'Eligibility must not change actual history');checks++;return actual;};
check(base,true,'Eligibility retains nonzero terrain correction at exit');
for(const degrees of [37,90,180,-135]){
 const a=structuredClone(base),q=R.qexp([0,degrees*Math.PI/180,0]),turn=p=>R.rotate(q,p),lift=[4,1.7,-2];
 a.frame.pose.points=a.frame.pose.points.map(p=>R.add(turn(p),lift));a.frame.pose.q=a.frame.pose.q.map(v=>R.qm(q,v));a.frame.pose.axes=a.frame.pose.q.map(R.toAxes);a.frame.root=lift.slice();
 a.terrain.tiles=a.terrain.tiles.map(t=>({...t,point:R.add(turn(t.point),lift),u:turn(t.u),v:turn(t.v)}));a.terrain.rootRows=a.terrain.rootRows.map(row=>({...row,position:R.add(turn(row.position),lift)}));
 check(a,true,'Rotated/elevated finite landing '+degrees);
}
const reverse=structuredClone(base);reverse.terrain.rootRows=reverse.terrain.rootRows.map(r=>({...r,position:[r.position[0],r.position[1],-r.position[2]]}));check(reverse,true,'Reversed travel does not require positive course Z');
const stop=structuredClone(base);stop.terrain.rootRows=stop.terrain.rootRows.map(r=>({...r,position:[0,0,0]}));check(stop,true,'Stopped root on landing');
for(const [label,change,reason] of [
 ['material pin',a=>a.frame.feet[0].contact={surface:'landing',point:[0,0,0]},'material_contact'],
 ['void',a=>a.terrain.tiles=[],'no_ground'],
 ['mid ramp',a=>a.terrain.rootRows[2].position[1]=.16,'changing_incline'],
 ['no horizontal support',a=>a.terrain.tiles[0].point[1]=-.16,'no_level_support'],
 ['wall',a=>{a.terrain.tiles[0].v=[0,1,0];},'nonhorizontal_terrain'],
 ['short future',a=>a.terrain.rootRows[2].time=1.1,'short_navigation'],
 ['stale root window',a=>a.frame.root[0]=.1,'navigation_mismatch'],
 ['low toe',a=>{for(let j=1;j<a.frame.pose.points.length;j++)a.frame.pose.points[j][1]-=.1;},'shoe_not_clear'],
 ['upcoming raised tread',a=>a.terrain.tiles.push({id:'raised',point:[0,.16,0],u:[1,0,0],v:[0,0,1],bounds:[-.2,.2,.12,.24]}),'raised_ahead'],
 ['narrow gap between root samples',a=>{a.terrain.tiles=[{...a.terrain.tiles[0],bounds:[-4,4,-4,.10]},{...a.terrain.tiles[0],id:'after',bounds:[-4,4,.11,4]}];},'future_support_gap'],
 ['slide owner',a=>a.frame.slide=true,'surface_mode']
]){const a=structuredClone(base);change(a);assert.equal(check(a,false,label).reason,reason);}
// A small raised rectangle inside a shoe face, away from the root path: all
// original corners lie outside it, so a corner-only overlap test would miss it.
{
 const a=structuredClone(base),side='L',l=S.leg(a.frame.pose,names,side),ankle=a.frame.pose.points[l.foot],offsets=S.footPoints(a.frame.pose,l.foot,l.toe,side);
 const centre=offsets.slice(0,8).reduce((p,o)=>R.add(p,R.mul(o,1/8)),ankle.slice());
 // Put both foot and its blocker to the side without changing root support.
 for(const j of [l.foot,l.toe])a.frame.pose.points[j][0]+=1;centre[0]+=1;
 a.terrain.tiles.push({id:'shoe-obstacle',point:[centre[0],1,centre[2]],u:[1,0,0],v:[0,0,1],bounds:[-.001,.001,-.001,.001]});
 assert.equal(check(a,false,'Interior shoe-face blocker').reason,'raised_under_shoe');
}
const canonical=[];
for(const terrain of ['stairs','down']){
 const source=structuredClone(input.source);source.poses=source.poses.slice(0,61);source.roots=source.roots.slice(0,61);if(source.rootYawDegrees)source.rootYawDegrees=source.rootYawDegrees.slice(0,61);source.duration=source.totalDuration=2;source.directionMeta={...source.directionMeta,totalDuration:2};
 const decoded=K.decode(source,input.parents),settings={...input.settings,terrain,steps:2},model=K.prepare(decoded,settings),plan=H.requestFor(model,decoded);assert(plan,'Canonical lab fixture must exit '+terrain);
 // Preserve the exact carrier breakpoint where the ramp reaches its landing;
 // coarse resampling would invent an inclined root at the lab's60Hz event.
 const snapshot={tiles:model.terrain.tiles.map(t=>({...t})),rootStartTick:0,rootRows:model.frames.map((f,i)=>({time:i/120,position:f.root}))};
 const result=check({frame:model.frames[plan.index],terrain:snapshot,currentTick:plan.index,names:decoded.names},true,'Canonical lab handoff '+terrain);
 canonical.push({terrain,canonicalFrame:plan.index/2,eligible:true,minimumSoleGap:result.minimumSoleGap});
}
const report={passed:true,checks,canonical,coverage:'actual corrected shoes; finite rotated/elevated/backward/stopped landings; contact/ramp/void/wall/gap/raised footprint rejection; no input mutation'};
fs.writeFileSync(path.join(folder,'live-exit.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
