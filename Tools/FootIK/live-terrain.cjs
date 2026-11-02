'use strict';
// Finite horizontal treads in a fixed world frame. Navigation height is keyed
// by time; reversing or turning through the same X/Z no longer aliases it.
const T=require('../../Labs/FootIKLab/terrain.js');
const S=require('../../Labs/FootIKLab/support.js');
const R=require('../../Labs/FootIKLab/recovery.js');
const NativeFloor=require('./native-terrain-floor.cjs');
const {add,sub,mul,dot,length,unit}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v,0,1);return v*v*(3-2*v);};
function create(snapshot){
 if(!Array.isArray(snapshot.tiles))throw Error('Finite tread array required');
 const shapeBases=new Map(),tileBasis=new WeakMap();
 const tiles=snapshot.tiles.map(input=>{
  const old=!input.point;
  const point=old?[0,input.y,0]:input.point.slice(),u=old?[1,0,0]:input.u.slice(),v=old?[0,0,1]:input.v.slice(),bounds=old?[input.x0,input.x1,input.z0,input.z1]:input.bounds.slice();
  if(typeof input.id!=='string'||![point,u,v].every(a=>a.length===3&&a.every(Number.isFinite))||bounds.length!==4||!bounds.every(Number.isFinite)||bounds[0]>=bounds[1]||bounds[2]>=bounds[3]||Math.abs(u[1])+Math.abs(v[1])>1e-8||Math.abs(length(u)-1)>1e-8||Math.abs(length(v)-1)>1e-8||Math.abs(dot(u,v))>1e-8)throw Error('Invalid finite horizontal tread');
  const local=p=>{const d=sub(p,point);return [dot(d,u),d[1],dot(d,v)];},world=p=>add(point,add(mul(u,p[0]),add([0,p[1],0],mul(v,p[2]))));
  const shape=offsets=>offsets.map(o=>[dot(o,u),o[1],dot(o,v)]);
  const t=T.create({terrain:'flat',height:0,depth:35,steps:1});t.tiles.splice(0,t.tiles.length,{id:input.id,x0:bounds[0],x1:bounds[1],z0:bounds[2],z1:bounds[3],y:0});
  const tile={...input,point,u,v,bounds,y:point[1],shaped:input.shaped!==false,surface:S.rectangle(input.id,point,u,v,bounds,.1),local,world,shape,query:t};
  // Terrain is an immutable snapshot. Equal bases perform identical dot
  // products; keep signed zero distinct to preserve their exact arithmetic.
  const key=[...u,...v].map(x=>Object.is(x,-0)?'-0':String(x)).join(',');
  if(!shapeBases.has(key))shapeBases.set(key,shapeBases.size);tileBasis.set(tile,shapeBases.get(key));return tile;
 });
 const hit=(x,z)=>{
  let best=null;
  for(const t of tiles){const p=t.local([x,t.y,z]);if(t.query.hit(p[0],p[2])&&(!best||t.y>best.y))best=t;}
  return best;
 };
 const height=(x,z)=>hit(x,z)?.y??-Infinity;
 const nativeFloor=NativeFloor.create(tiles);
 const floorFor=(ankle,offsets)=>{
  if(nativeFloor){const found=nativeFloor(ankle,offsets);if(found!==null)return found;}
  let best=-Infinity;const shapes=[];
  for(const t of tiles){
   // Reuse only within this query: callers may change offsets before the next
   // call, so no identity cache can accidentally retain an obsolete shoe.
   const basis=tileBasis.get(t),p=t.local(ankle),shape=shapes[basis]||(shapes[basis]=t.shape(offsets));
   // The canonical single-tile query returns the original ankle when there
   // is no overlap. Explicit footprint rejection distinguishes empty space.
   let overlaps=false;
   for(let box=0;box<shape.length&&!overlaps;box+=8){
    const corners=shape.slice(box,box+8),xs=corners.map(o=>p[0]+o[0]),zs=corners.map(o=>p[2]+o[2]);
    if(Math.max(...xs)>t.bounds[0]+1e-9&&Math.min(...xs)<t.bounds[1]-1e-9&&Math.max(...zs)>t.bounds[2]+1e-9&&Math.min(...zs)<t.bounds[3]-1e-9)overlaps=true;
   }
   if(overlaps)best=Math.max(best,t.y+t.query.floorFor(p,shape));
  }
  return Number.isFinite(best)?best:ankle[1];
 };
 const landing=(ankle,offsets)=>{
  const centre=offsets.slice(0,8).reduce((p,o)=>add(p,mul(o,1/8)),ankle.slice()),tile=hit(centre[0],centre[2]);if(!tile)return null;
  const found=tile.query.landing(tile.local(ankle),tile.shape(offsets));if(!found)return null;
  const target=tile.world(found.target);target[1]=floorFor(target,offsets);
  return {target,tile,local:tile.local(target),height:tile.y};
 };
 const local=(point,tile)=>tile.local(point);
 // Reserve the same heel-roll margin against the edge in the actual direction
 // of travel; a rotated tread's local V axis is not necessarily that direction.
 const rollRetreat=(hit,contact,travel)=>{
  const t=hit.tile,p=t.local(contact),d=[dot(travel,t.u),0,dot(travel,t.v)];let distance=Infinity,backDistance=Infinity;
  for(const k of [0,2])if(Math.abs(d[k])>1e-8){
   const edge=t.bounds[k===0?(d[k]>0?1:0):(d[k]>0?3:2)],opposite=t.bounds[k===0?(d[k]>0?0:1):(d[k]>0?2:3)];
   const dist=(edge-p[k])/d[k],back=(p[k]-opposite)/d[k];if(dist>=0)distance=Math.min(distance,dist);if(back>=0)backDistance=Math.min(backDistance,back);
  }
  if(!Number.isFinite(distance)||!Number.isFinite(backDistance))return hit.target;
  const near=t.world(add(p,mul(d,distance+.001))),behind=t.world(add(p,mul(d,-backDistance-.001)));
  if(height(near[0],near[2])<=hit.height+.001||height(behind[0],behind[2])>hit.height+.001)return hit.target;
  const margin=Math.min(.06,Math.max(0,backDistance-.008));
  return sub(hit.target,mul(unit(travel),margin));
 };
 const distance=(point,tile)=>{const p=tile.local(point),x=clamp(p[0],tile.bounds[0],tile.bounds[1]),z=clamp(p[2],tile.bounds[2],tile.bounds[3]);return Math.hypot(p[0]-x,p[2]-z);};
 const influence=(pose,legs,navHeight,geometry)=>{
  const points=legs.flatMap(l=>geometry(pose,l).map(o=>add(pose.points[l.foot],o)));let nearest=Infinity;
  for(const t of tiles)if(t.shaped&&Math.abs(t.y-navHeight)>.005)for(const p of points)nearest=Math.min(nearest,distance(p,t));
  return 1-smooth(nearest/.32);
 };
 return {tiles,hit,height,floorFor,reachable:nativeFloor?.reachable,rotationClearance:nativeFloor?.rotationClearance,landing,local,rollRetreat,influence,start:-Infinity,end:Infinity,rootHeight:()=>0};
}
function rootSampler(rows){
 if(!Array.isArray(rows)||rows.length<2||rows.some((r,i)=>!Number.isFinite(r.time)||r.position?.length!==3||!r.position.every(Number.isFinite)||(i&&r.time<=rows[i-1].time)))throw Error('Ordered timed navigation roots required');
 function index(time){let i=1;while(i<rows.length-1&&rows[i].time<time)i++;return i;}
 return {
  at(time){const i=index(time),a=rows[i-1],b=rows[i],u=clamp((time-a.time)/(b.time-a.time),0,1);return add(a.position,mul(sub(b.position,a.position),u));},
  direction(time){let i=index(time);for(let d=0;d<rows.length;d++){for(const j of d?[i-d,i+d]:[i])if(j>0&&j<rows.length){const p=sub(rows[j].position,rows[j-1].position);p[1]=0;if(length(p)>1e-8)return unit(p);}}return [0,0,1];},
  speed(time){const i=index(time),d=sub(rows[i].position,rows[i-1].position);d[1]=0;return length(d)/(rows[i].time-rows[i-1].time);}
 };
}
module.exports={create,rootSampler};
