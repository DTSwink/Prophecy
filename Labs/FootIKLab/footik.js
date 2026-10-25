/* Terrain corrections are deltas from the NN gait, never a replacement gait. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const T=typeof module!=='undefined'?require('./terrain.js'):root.FootTerrain;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qslerp}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
const defaults={gait:'walk',phase:0,terrain:'stairs',height:16,depth:35,steps:12,enabled:true,clearance:4,pelvis:30,ghost:false,targets:true,ramp:false,bicolor:true,bones:false,translucency:70,ghostTranslucency:70,loop:true,trimIn:0,trimOut:5,speed:1};
function sanitize(input={}){
 const s={...defaults,...input};
 for(const [k,a,b] of [['phase',0,1],['height',0,30],['depth',28,100],['steps',2,24],['clearance',0,20],['pelvis',0,60],['translucency',0,100],['ghostTranslucency',0,100],['trimIn',0,5-1/60],['trimOut',1/60,5],['speed',.1,2]])s[k]=clamp(Number.isFinite(+s[k])?+s[k]:defaults[k],a,b);
 s.steps=Math.round(s.steps);s.trimOut=Math.max(s.trimIn+1/60,s.trimOut);
 s.gait=s.gait==='run'?'run':'walk';s.terrain=['stairs','down','uneven','flat'].includes(s.terrain)?s.terrain:'stairs';
 for(const k of ['enabled','ghost','targets','ramp','bicolor','bones','loop'])s[k]=!!s[k];return s;
}
function decode(data,parents){
 const poses=data.poses.map((p,i)=>{const q=[[0,0,0,1],...p.axes.map(R.fromAxes)];return {points:[data.roots[i],...p.points],q,axes:q.map(R.toAxes)};});
 return {names:['root',...data.names],fps:data.fps,duration:data.duration,poses,locals:poses.map(p=>R.localize(p.points,p.q,parents)),source:data.source,parents};
}
function at(run,t){
 const f=clamp(t*run.fps,0,run.poses.length-1),i=Math.min(run.locals.length-2,Math.floor(f)),u=f-i;
 if(u<1e-9)return run.poses[i];
 const a=run.locals[i],b=run.locals[i+1];
 return R.fk({p:a.p.map((v,j)=>add(v,mul(sub(b.p[j],v),u))),q:a.q.map((v,j)=>qslerp(v,b.q[j],u))},run.parents);
}
const moved=(p,delta)=>({...p,points:p.points.map(v=>add(v,delta))});
function geometry(p,l,q=l){
 const points=p.points.slice(),axes=p.axes.slice();
 points[l.toe]=add(points[l.foot],rotate(q.footQ,l.toeLocal));axes[l.foot]=R.toAxes(q.footQ);axes[l.toe]=R.toAxes(q.toeQ);
 return S.footPoints({points,axes},l.foot,l.toe,l.side);
}
function landingRotation(q,l,remaining,fps){
 const forward=rotate(q.footQ,[0,Math.sign(l.toeLocal[1])||1,0]);
 const pitch=Math.asin(clamp(forward[1],-1,1)),limit=(5+40*smooth((remaining/fps-.22)/.13))*Math.PI/180,band=2*Math.PI/180;
 if(pitch<=limit-band)return q;
 const angle=limit-band*Math.exp(-(pitch-limit+band)/band),horizontal=Math.hypot(forward[0],forward[2]);
 if(horizontal<1e-6)return q;
 const desired=[forward[0]*Math.cos(angle)/horizontal,Math.sin(angle),forward[2]*Math.cos(angle)/horizontal],delta=R.fromTo(forward,desired);
 return {footQ:qm(delta,q.footQ),toeQ:qm(delta,q.toeQ)};
}
// A released toe must not continue the ground roll in midair as IK bends the
// calf. Keep natural ankle articulation above the actual toe-off pitch.
function releaseRotation(q,l,released){
 if(!released)return q;
 const local=[0,Math.sign(l.toeLocal[1])||1,0],start=rotate(released.footQ,local),forward=rotate(q.footQ,local);
 const heading=unit([start[0],0,start[2]]),axis=unit(cross(heading,[0,1,0]));
 const minimum=Math.atan2(start[1],dot(start,heading)),pitch=Math.atan2(forward[1],dot(forward,heading));
 if(pitch>=minimum)return q;
 const delta=R.qexp(mul(axis,minimum-pitch));
 return {footQ:qm(delta,q.footQ),toeQ:qm(delta,q.toeQ)};
}
// A straight NN knee has no geometric bend plane. Using its tiny cross product
// (or pelvis +Y, which is backwards in this rig) can turn the leg through 180deg.
// Use the anatomical hinge at extension, smoothly returning to the NN bend.
function stableLeg(p,names,side){
 const l=S.leg(p,names,side),axis=unit(sub(p.points[l.foot],p.points[l.hip]));
 const hinge=sub(p.axes[l.hip][2],mul(axis,dot(p.axes[l.hip][2],axis)));
 let anatomical=unit(cross(unit(hinge),axis));
 const forward=rotate(p.q[l.pelvis],[0,-1,0]);
 if(dot(anatomical,forward)<0)anatomical=mul(anatomical,-1);
 const rawBend=sub(l.upperAxis,mul(axis,dot(l.upperAxis,axis))),strength=length(rawBend);
 const rawPole=strength>1e-8?unit(rawBend):anatomical;
 const w=dot(rawPole,anatomical)>0?smooth((strength-.015)/.10):0;
 const pole=unit(add(mul(anatomical,1-w),mul(rawPole,w)));
 return {...l,normal:unit(cross(axis,pole)),axisLocal:rotate(qinv(p.q[l.pelvis]),axis),poleLocal:rotate(qinv(p.q[l.pelvis]),pole)};
}
function solve(p,l,target,parents,rotation=l){
 const hip=p.points[l.hip],delta=sub(target,hip),a=l.upper,b=l.lower;
 const d=clamp(length(delta),Math.abs(a-b)+1e-6,a+b-1e-7),axis=unit(delta);
 const originalAxis=rotate(p.q[l.pelvis],l.axisLocal),originalPole=rotate(p.q[l.pelvis],l.poleLocal);
 const pole=rotate(R.fromTo(originalAxis,axis),originalPole),normal=unit(cross(axis,pole));
 const along=(a*a-b*b+d*d)/(2*d),bend=Math.sqrt(Math.max(0,a*a-along*along));
 const knee=add(hip,add(mul(axis,along),mul(pole,bend))),foot=add(hip,mul(axis,d));
 const basis=(direction,n)=>{direction=unit(direction);n=unit(sub(n,mul(direction,dot(n,direction))));return R.fromAxes([direction,n,cross(direction,n)]);};
 const align=(before,after,q)=>qm(qm(basis(after,normal),qinv(basis(before,l.normal))),q);
 const hq=align(l.upperAxis,sub(knee,hip),l.hipQ),kq=align(l.lowerAxis,sub(foot,knee),l.kneeQ);
 const local=R.localize(p.points,p.q,parents);
 local.p[l.knee]=l.kneeLocal;local.p[l.foot]=l.ankleLocal;local.p[l.toe]=l.toeLocal;
 local.q[l.hip]=qm(qinv(p.q[parents[l.hip]]),hq);local.q[l.knee]=qm(qinv(hq),kq);
 local.q[l.foot]=qm(qinv(kq),rotation.footQ);local.q[l.toe]=qm(qinv(rotation.footQ),rotation.toeQ);
 return R.fk(local,parents);
}
function influence(p,legs,terrain,settings){
 if(settings.terrain==='flat'||settings.height===0)return 0;
 const extents=legs.flatMap(l=>geometry(p,l).map(o=>p.points[l.foot][2]+o[2]));
 const front=Math.max(...extents),back=Math.min(...extents);
 // A future tread cannot change the whole preceding stride on the approach.
 return smooth((front-terrain.start+.32)/.32)*(1-smooth((back-terrain.end)/.32));
}
function reachable(target,hip,reach,offsets,terrain){
 let p=target.slice();
 for(let pass=0;pass<12;pass++){
  const d=sub(p,hip);if(length(d)>reach)p=add(hip,mul(unit(d),reach));
  p[1]=Math.max(p[1],terrain.floorFor(p,offsets));
  const dy=p[1]-hip[1],horizontal=Math.hypot(p[0]-hip[0],p[2]-hip[2]);
  const radius=Math.sqrt(Math.max(0,reach*reach-dy*dy));
  if(horizontal>radius){p[0]=hip[0]+(p[0]-hip[0])*radius/horizontal;p[2]=hip[2]+(p[2]-hip[2])*radius/horizontal;}
 }
 return p;
}
// C1 soft reach: slows extension before the straight-knee singularity.
function softReach(distance,reach,weight=1){
 const band=.06*reach*weight,start=reach-band;
 return band>1e-8&&distance>start?start+band*(1-Math.exp(-(distance-start)/band)):Math.min(distance,reach);
}
function plantedRoll(p,l,hit){
 const captured={...p,points:p.points.slice()},delta=sub(hit.target,p.points[l.foot]);
 captured.points[l.foot]=hit.target;captured.points[l.toe]=add(p.points[l.toe],delta);
 const frame=S.footFrame(captured,l.foot,l.toe,l.side),forward=unit([frame.forward[0],0,frame.forward[2]]);
 const axis=unit(cross([0,1,0],forward)),surface=S.rectangle(hit.tile.id,[0,hit.height,0],[1,0,0],[0,0,1],[hit.tile.x0,hit.tile.x1,hit.tile.z0,hit.tile.z1],.1);
 const terminal={pose:captured,foot:hit.target,rotation:{footQ:l.footQ,toeQ:l.toeQ}};
 const positive=S.roll(terminal,{...l,plant:{right:axis}},surface,140);
 const negative=S.roll(terminal,{...l,plant:{right:mul(axis,-1)}},surface,140);
 const pitch=Math.asin(clamp(frame.forward[1],-1,1))*180/Math.PI;
 return {pitch,sample:angle=>{
  const r=(angle>=0?positive:negative)(Math.abs(angle)/140);
  const localPoint=rotate(qinv(r.rotation.footQ),sub(r.contact,r.foot));
  return {...r,angle,localPoint,pivotKey:localPoint.map(v=>Math.round(v*1e6)).join(',')};
 }};
}
// Minimum-curvature swing height with finite shoe-clearance constraints.
// Solve a banded convex obstacle problem, rather than raising each tread sample
// independently or inflating one global arc to satisfy its hardest corner.
function clearanceCurve(reference, floor, fixed, strength, ceiling=null){
 const n=reference.length,bands=[new Float64Array(n).fill(1),new Float64Array(n),new Float64Array(n)];
 for(let k=0;k<n-2;k++)for(let a=0;a<3;a++)for(let b=a;b<3;b++)bands[b-a][k+a]+=strength*[1,-2,1][a]*[1,-2,1][b];
 const h=(i,j)=>bands[Math.abs(i-j)][Math.min(i,j)];
 const active=new Map(fixed),upperActive=new Set();let y=reference.slice();
 for(let iteration=0;iteration<n*3;iteration++){
  const rhs=reference.slice(),diag=new Float64Array(n),l1=new Float64Array(n),l2=new Float64Array(n);
  for(let i=0;i<n;i++){
   if(active.has(i)){rhs[i]=active.get(i);diag[i]=1;continue;}
   for(let j=Math.max(0,i-2);j<=Math.min(n-1,i+2);j++)if(active.has(j))rhs[i]-=h(i,j)*active.get(j);
   const b2=i>1&&!active.has(i-2)?h(i,i-2):0,b1=i>0&&!active.has(i-1)?h(i,i-1):0;
   if(i>1)l2[i]=b2/diag[i-2];
   if(i>0)l1[i]=(b1-l2[i]*l1[i-1])/diag[i-1];
   diag[i]=Math.sqrt(h(i,i)-l1[i]*l1[i]-l2[i]*l2[i]);
  }
  const tmp=new Float64Array(n);
  for(let i=0;i<n;i++)tmp[i]=(rhs[i]-(i>0?l1[i]*tmp[i-1]:0)-(i>1?l2[i]*tmp[i-2]:0))/diag[i];
  for(let i=n-1;i>=0;i--)y[i]=(tmp[i]-(i+1<n?l1[i+1]*y[i+1]:0)-(i+2<n?l2[i+2]*y[i+2]:0))/diag[i];
  let worst=-1,violation=1e-7,isUpper=false;
  for(let i=0;i<n;i++)if(!active.has(i)){
   if(floor[i]-y[i]>violation){worst=i;violation=floor[i]-y[i];isUpper=false;}
   if(ceiling&&y[i]-ceiling[i]>violation){worst=i;violation=y[i]-ceiling[i];isUpper=true;}
  }
  if(worst>=0){active.set(worst,isUpper?ceiling[worst]:floor[worst]);if(isUpper)upperActive.add(worst);continue;}
  let release=-1,gradient=-1e-7;
  for(const [i] of active)if(!fixed.has(i)){
   let g=-reference[i];for(let j=Math.max(0,i-2);j<=Math.min(n-1,i+2);j++)g+=h(i,j)*y[j];
   if(upperActive.has(i))g=-g;
   if(g<gradient){gradient=g;release=i;}
  }
  if(release<0)break;active.delete(release);upperActive.delete(release);
 }
 return y;
}
function prepare(run,input){
 const settings=sanitize(input),terrain=T.create(settings),fps=120,count=Math.round(run.duration*fps)+1;
 const {parents,names}=run,origin=run.poses[0].points[0];
 const raw=Array.from({length:count},(_,i)=>moved(at(run,i/fps),[-origin[0],0,-origin[2]]));
 const base=raw.map(p=>moved(p,[0,terrain.rootHeight(p.points[0][2]),0]));
 const speed=(raw.at(-1).points[0][2]-raw[0].points[0][2])/run.duration;
 const legs=raw.map(p=>['L','R'].map(side=>stableLeg(p,names,side)));
 const weights=raw.map((p,i)=>influence(p,legs[i],terrain,settings)),plans=[];
 // Root arrival on the exit must not dissolve a still-planted trailing foot.
 // Finish through the existing complete-shoe fade beyond the final riser.
 const exitIndex=settings.terrain==='stairs'?base.findIndex((p,i)=>p.points[0][2]>=terrain.end&&weights[i]===0):-1;

 for(let side=0;side<2;side++){
  const offsets=raw.map((p,i)=>geometry(p,legs[i][side])),flags=[];let stance=false;
  for(let i=0;i<count;i++){
   const l=legs[i][side],lo=Math.max(0,i-1),hi=Math.min(count-1,i+1);
   const v=mul(sub(raw[hi].points[l.foot],raw[lo].points[l.foot]),fps/Math.max(1,hi-lo));
   const sole=raw[i].points[l.foot][1]+Math.min(...offsets[i].map(o=>o[1])),fast=Math.hypot(v[0],v[2]);
   stance=stance?sole<.045&&fast<speed*.85:sole<.028&&fast<speed*.58;flags.push(stance);
  }
  const spans=[];
  for(let i=0;i<count;){const start=i,planted=flags[i];while(i+1<count&&flags[i+1]===planted)i++;spans.push({start,end:i,planted});i++;}
  const targets=new Array(count),contacts=new Array(count).fill(null),states=new Array(count).fill('SWING'),stanceRolls=new Map();
  const rotations=legs.map(row=>({footQ:row[side].footQ,toeQ:row[side].toeQ})),limits=new Array(count);
  for(const span of spans)if(span.planted){
   const l=legs[span.start][side],footprint=offsets.slice(span.start,span.end+1).flat();
   const hit=terrain.landing(raw[span.start].points[l.foot],footprint);
   if(!hit)continue;
   hit.target[1]=terrain.floorFor(hit.target,offsets[span.start]);
   const shaped=hit.tile.id.startsWith('step')||hit.tile.id.startsWith('tile');
   let roll=shaped?plantedRoll(raw[span.start],l,hit):null;
   if(roll){
    const angles=[];
    for(let j=span.start;j<=span.end;j++){const f=S.footFrame(raw[j],l.foot,l.toe,l.side);angles.push(roll.pitch-Math.asin(clamp(f.forward[1],-1,1))*180/Math.PI);}
    const low=Math.min(0,...angles),high=Math.max(0,roll.pitch+70),swept=[];
    // Reserve room for the entire heel-to-toe arc, including the shoe's top
    // corners near a riser, rather than only its unrolled ankle footprint.
    for(let n=0;n<=24;n++){const r=roll.sample(low+(high-low)*n/24),shift=sub(r.foot,hit.target);for(const o of geometry(raw[span.start],l,r.rotation))swept.push(add(shift,o));}
    const fitted=terrain.landing(raw[span.start].points[l.foot],swept);
    if(fitted){
     hit.target=fitted.target;hit.target[1]=terrain.floorFor(hit.target,offsets[span.start]);roll=plantedRoll(raw[span.start],l,hit);
     // Overhang above a lower previous tread is harmless. Keep the material
     // heel contact on this tread while reserving toe-off room before a riser.
     if(terrain.height(hit.target[0],hit.tile.z1+.001)>hit.height+.001&&terrain.height(hit.target[0],hit.tile.z0-.001)<=hit.height+.001){
      const margin=Math.min(.06,Math.max(0,roll.sample(0).contact[2]-hit.tile.z0-.008));
      hit.target[2]-=margin;hit.target[1]=terrain.floorFor(hit.target,offsets[span.start]);roll=plantedRoll(raw[span.start],l,hit);
     }
    }
   }
   if(roll)stanceRolls.set(side+':'+span.start,roll);
   let previousExtra=0;
   for(let i=span.start;i<=span.end;i++){
    const source=raw[i].points[l.foot];
    if(!shaped){targets[i]=add(source,[0,hit.height,0]);states[i]='NN';continue;}
    const current=legs[i][side],frame=S.footFrame(raw[i],l.foot,l.toe,l.side);
    const sourcePitch=Math.asin(clamp(frame.forward[1],-1,1))*180/Math.PI;
    // A terrain landing approaches the tread with a shallow heel lead.
    // Replaying the NN's airborne toe-up peak here made swing flatten, then
    // dorsiflex again immediately before settling flat on the tread.
    const contactPitch=Math.min(sourcePitch,5);
    const natural=roll.pitch-contactPitch,hip=base[i].points[l.hip];
    let chosen=roll.sample(natural);
    const goal=softReach(length(sub(chosen.foot,hip)),current.reach,weights[i]);
    // As extension approaches its limit, roll farther onto the forefoot while
    // retaining the same material contact. The ankle follows the pivot arc.
    const end=Math.max(natural,roll.pitch+70);
    if(length(sub(chosen.foot,hip))>goal+1e-7){
     let before=chosen;
     for(let n=1;n<=7;n++){
      const next=roll.sample(natural+(end-natural)*n/7);
      if(!next.valid)break;
      if(length(sub(next.foot,hip))<=goal){
       let a=before,b=next;
       for(let k=0;k<12;k++){const mid=roll.sample((a.angle+b.angle)/2);if(length(sub(mid.foot,hip))>goal)a=mid;else b=mid;}
       chosen=b;break;
      }
      if(length(sub(next.foot,hip))<length(sub(chosen.foot,hip)))chosen=next;
      before=next;
     }
    }
    const extra=previousExtra+clamp(chosen.angle-natural-previousExtra,-540/fps,540/fps);
    chosen=roll.sample(natural+extra);previousExtra=extra;
    // Release only after the rolling contact itself exceeds useful leg reach.
    const loweredHip=add(hip,[0,-Math.min(.02,settings.pelvis/100),0]);
    if(i>span.start&&weights[i]>0&&chosen.foot[2]<hip[2]-.15&&length(sub(chosen.foot,loweredHip))>current.reach*.995)break;
    limits[i]=softReach(length(sub(chosen.foot,hip)),current.reach*.995,weights[i]);
    targets[i]=chosen.foot;rotations[i]=chosen.rotation;states[i]='PIN';
    offsets[i]=geometry(raw[i],current,chosen.rotation);
    contacts[i]={surface:hit.tile.id,point:chosen.contact,local:sub(chosen.contact,[0,hit.height,hit.tile.z0]),
     localPoint:chosen.localPoint,pivotKey:chosen.pivotKey,stanceId:side+':'+span.start,angle:chosen.angle,extraPitch:chosen.angle-natural,valid:chosen.valid};
   }
  }
  // A higher tread needs clearance before the source gait's flat-ground toe-off.
  // Reserve up to 50ms of the end of stance for that lift; keep the retained
  // material pin untouched until release. Level/down steps keep NN timing.
  for(let end=0;end<count-1;end++)if(states[end]==='PIN'&&states[end+1]!=='PIN'){
   let next=end+1;while(next<count&&!contacts[next]&&states[next]!=='NN')next++;
   if(next>=count||!targets[next]||targets[next][1]<=targets[end][1]+.08)continue;
   const current=contacts[end],surface=terrain.tiles.find(t=>t.id===current.surface);
   const nextSurface=contacts[next]?terrain.tiles.find(t=>t.id===contacts[next].surface):terrain.hit(targets[next][0],targets[next][2]);
   if(!surface||!nextSurface||nextSurface.y<=surface.y+.005)continue;
   let start=end;while(start>0&&contacts[start-1]?.stanceId===current.stanceId)start--;
   const lead=Math.min(Math.round(fps*.05),Math.max(0,end-start-Math.round(fps*.12)));
   if(!lead)continue;
   const release=end-lead,rollStart=Math.max(start,release-Math.round(fps*.20)),roll=stanceRolls.get(current.stanceId);
   if(!roll)continue;
   const angles=contacts.slice(rollStart,end+1).map(c=>c.angle),retimed=[];
   // A return to the NN gait needs less toe-down than another retained plant:
   // excessive pitch makes the toe demand a sharp vertical riser-clearance lift.
   const terminal=Math.max(angles[0],Math.min(angles.at(-1),roll.pitch+(contacts[next]?.valid?45:35)));
   for(let i=rollStart;i<=release;i++){
    // Complete the toe roll on the surface, carrying its velocity into lift.
    const u=(i-rollStart)/Math.max(1,release-rollStart);
    const angle=angles[0]+(terminal-angles[0])*(1.5*u*u-.5*u*u*u);
    const chosen=roll.sample(angle),l=legs[i][side],shape=geometry(raw[i],l,chosen.rotation);
    if(!chosen.valid||terrain.floorFor(chosen.foot,shape)>chosen.foot[1]+1e-6){retimed.length=0;break;}
    retimed.push({i,chosen,shape});
   }
   if(!retimed.length)continue;
   for(const {i,chosen,shape} of retimed){
    const old=contacts[i],l=legs[i][side];
    targets[i]=chosen.foot;rotations[i]=chosen.rotation;offsets[i]=shape;
    limits[i]=softReach(length(sub(chosen.foot,base[i].points[l.hip])),l.reach*.995,weights[i]);
    contacts[i]={...old,point:chosen.contact,local:sub(chosen.contact,[0,surface.y,surface.z0]),localPoint:chosen.localPoint,pivotKey:chosen.pivotKey,angle:chosen.angle,extraPitch:old.extraPitch+chosen.angle-old.angle,valid:chosen.valid};
   }
   for(let i=end-lead+1;i<=end;i++){states[i]='SWING';contacts[i]=null;targets[i]=undefined;limits[i]=undefined;rotations[i]={footQ:legs[i][side].footQ,toeQ:legs[i][side].toeQ};offsets[i]=geometry(raw[i],legs[i][side]);}
  }
  const swings=[];
  for(let i=0;i<count;i++){if(states[i]!=='SWING')continue;const start=i;while(i+1<count&&states[i+1]==='SWING')i++;swings.push({start,end:i});}
  for(const span of swings){
   const a=Math.max(0,span.start-1),b=Math.min(count-1,span.end+1),l=legs[a][side];
   const from=sub(targets[a]||base[a].points[l.foot],raw[a].points[l.foot]);
   const to=sub(targets[b]||base[b].points[l.foot],raw[b].points[l.foot]);
   let start=a;
   // Start preparing a higher landing at toe-off, not when the toe is already
   // next to its riser. The old proximity fade multiplied a prepared clearance
   // by almost zero, then restored it within three frames.
   if(settings.terrain==='stairs'&&to[1]>from[1]+.005&&raw[a].points[0][2]<terrain.start){
    for(let j=a;j<=b;j++)weights[j]=Math.max(weights[j],smooth((j-a)/Math.max(1,(b-a)*.5)));
   }
   if(weights[a]===0&&weights[b]>0&&!(settings.terrain==='stairs'&&to[1]>from[1]+.005)){while(start<b&&weights[start]===0)start++;}
   const path=[];let rotationRelease=0;
   const footDelta=qm(rotations[a].footQ,qinv(legs[a][side].footQ)),toeDelta=qm(rotations[a].toeQ,qinv(legs[a][side].toeQ));
   for(let i=span.start;i<=span.end;i++){
    // Settle the terrain offset earlier on descent, so the ramp root does
    // not drop past an unnecessarily high swing ankle. NN timing is unchanged.
    const u=clamp((i-start)/Math.max(1,b-start),0,1),e=clamp(smooth(u)+(to[1]<from[1]-.005?.2*Math.sin(Math.PI*u)**2:0),0,1),p=add(raw[i].points[l.foot],add(mul(from,1-e),mul(to,e)));
    const blendFrames=Math.min(fps*.10,(b-a)/2),release=smooth((i-a)/blendFrames),arrive=smooth(1-(b-i)/blendFrames);
    const nextFoot=qm(rotations[b].footQ,qinv(legs[b][side].footQ)),nextToe=qm(rotations[b].toeQ,qinv(legs[b][side].toeQ));
    rotations[i]={footQ:qm(qslerp(qslerp(footDelta,[0,0,0,1],release),nextFoot,arrive),legs[i][side].footQ),toeQ:qm(qslerp(qslerp(toeDelta,[0,0,0,1],release),nextToe,arrive),legs[i][side].toeQ)};
    if(contacts[a]&&targets[a][2]<base[a].points[l.hip][2]-.15){
     // Toe-off orientation follows swing progress, not a fixed 100ms timer.
     // Keep the released shoe pointed down while it still trails the pelvis.
     rotationRelease=Math.max(rotationRelease,Math.min(release,smooth((p[2]-base[i].points[l.hip][2]+.15)/.27)));
     const sourceRotation={footQ:qm(nextFoot,legs[i][side].footQ),toeQ:qm(nextToe,legs[i][side].toeQ)};
     const blend=Math.max(rotationRelease,arrive);
     rotations[i]={footQ:qslerp(rotations[a].footQ,qslerp(legs[i][side].footQ,sourceRotation.footQ,arrive),blend),toeQ:qslerp(rotations[a].toeQ,qslerp(legs[i][side].toeQ,sourceRotation.toeQ,arrive),blend)};
    }
    // Aim directly at the actual landing orientation, rather than replaying
    // the source foot's moving airborne rotation plus a contact delta.
    if(contacts[b]){
     const settle=smooth(1-(b-i)/Math.min(fps*.22,(b-a)*.5));
     rotations[i]={footQ:qslerp(rotations[i].footQ,rotations[b].footQ,settle),toeQ:qslerp(rotations[i].toeQ,rotations[b].toeQ,settle)};
     rotations[i]=landingRotation(rotations[i],legs[i][side],b-i,fps);
    }
    if(contacts[a])rotations[i]=releaseRotation(rotations[i],legs[i][side],rotations[a]);
    offsets[i]=geometry(raw[i],legs[i][side],rotations[i]);
    if(contacts[a]&&i-a<fps*.15&&p[2]>targets[a][2]){
     // Lift out of the retained toe contact before translating through a riser.
     // A colliding toe delays forward travel, rather than teleporting upward.
     const startFoot=targets[a],ceiling=Math.max(p[1],startFoot[1]+raw[i].points[l.foot][1]-raw[a].points[l.foot][1]+2*(i-a)/fps);
     if(terrain.floorFor(p,offsets[i])>ceiling){
      let lo=0,hi=1;
      for(let n=0;n<14;n++){const t=(lo+hi)/2,q=add(startFoot,mul(sub(p,startFoot),t));if(terrain.floorFor(q,offsets[i])<=ceiling)lo=t;else hi=t;}
      p[0]=startFoot[0]+(p[0]-startFoot[0])*lo;p[2]=startFoot[2]+(p[2]-startFoot[2])*lo;
     }
    }
    const floor=terrain.floorFor(p,offsets[i]);
    const changed=Math.abs(to[1]-from[1])>.005;
    path.push({i,p,u,need:Math.max(0,floor+(changed?settings.clearance/100*Math.sin(Math.PI*u):0)-p[1])});
   }
   // Bounded height envelope: never divide by a near-zero endpoint blend.
   for(let j=0;j<path.length;j++){
    const row=path[j];let lift=row.need;
    for(let k=Math.max(0,j-12);k<Math.min(path.length,j+13);k++)lift=Math.max(lift,path[k].need*Math.exp(-Math.abs(k-j)/5));
    const taper=smooth((row.i-a)/6)*smooth((b-row.i)/6);
    row.p[1]+=Math.max(row.need,lift*taper);targets[row.i]=row.p;
   }
  }
  for(let i=0;i<count;i++)targets[i]??=base[i].points[legs[i][side].foot];
  for(let i=0;i<count;i++)if(weights[i]<1){
   rotations[i]={footQ:qslerp(legs[i][side].footQ,rotations[i].footQ,weights[i]),toeQ:qslerp(legs[i][side].toeQ,rotations[i].toeQ,weights[i])};
   offsets[i]=geometry(raw[i],legs[i][side],rotations[i]);
  }
  plans.push({targets,states,contacts,offsets,rotations,limits,swings});
 }
 // The source knee plane becomes ill-conditioned near extension and can
 // oscillate at source-sample boundaries. Filter the pole in pelvis space,
 // transporting each neighbour into the current leg axis before averaging.
 for(let side=0;side<2;side++){
  const poles=legs.map(row=>row[side].poleLocal);
  for(let i=0;i<count;i++){
   const l=legs[i][side];let sum=[0,0,0];
   for(let k=-12;k<=12;k++){
    const j=clamp(i+k,0,count-1),transport=R.fromTo(legs[j][side].axisLocal,l.axisLocal);
    sum=add(sum,mul(rotate(transport,poles[j]),Math.exp(-.5*(k/5)**2)));
   }
   const filtered=unit(sub(sum,mul(l.axisLocal,dot(sum,l.axisLocal))));
   l.poleLocal=unit(add(mul(poles[i],1-weights[i]),mul(filtered,weights[i])));
  }
 }

 const planned=[],metrics={maxPenetration:0,maxReachError:0,maxPelvis:0,maxFlatDeviation:0,pins:[0,0]},pelvisGoals=[];
 for(let i=0;i<count;i++){
  const w=weights[i];
  if(w===0){
   pelvisGoals.push(0);
   planned.push({pelvisOffset:0,targets:legs[i].map(l=>base[i].points[l.foot]),planted:[false,false]});continue;
  }
  const targets=plans.map((plan,side)=>add(base[i].points[legs[i][side].foot],mul(sub(plan.targets[i],base[i].points[legs[i][side].foot]),w)));
  let low=-settings.pelvis/100,high=settings.pelvis/100;
  for(let side=0;side<2;side++){
   if(plans[side].states[i]!=='PIN')continue;
   const l=legs[i][side],hip=base[i].points[l.hip],target=targets[side];
   const reach=plans[side].limits[i]??l.reach*.995,horizontal=(target[0]-hip[0])**2+(target[2]-hip[2])**2,vertical=Math.sqrt(Math.max(0,reach*reach-horizontal));
   low=Math.max(low,target[1]-hip[1]-vertical);high=Math.min(high,target[1]-hip[1]+vertical);
  }
  // A lifted swing foot is not a reason to move the whole character.
  const goal=low<=high?clamp(0,low,high):clamp((low+high)/2,-settings.pelvis/100,settings.pelvis/100);
  pelvisGoals.push(goal);
  planned.push({pelvisOffset:0,targets,planted:[false,false]});
 }
 // Small look-ahead envelope prepares the pelvis before a planted leg reaches
 // extension; contact remains fixed rather than projecting the ankle off it.
 for(let i=0;i<count;i++){
  const w=weights[i];if(w===0)continue;
  let below=Math.min(0,pelvisGoals[i]),above=Math.max(0,pelvisGoals[i]);
  const horizon=Math.ceil(settings.pelvis/100/.4*fps)+1;
  for(let j=Math.max(0,i-horizon);j<=Math.min(count-1,i+horizon);j++){
   if(weights[j]===0)continue;
   const allowance=Math.abs(j-i)/fps*(j<i?.4:1.5);
   below=Math.min(below,pelvisGoals[j]+allowance);above=Math.max(above,pelvisGoals[j]-allowance);
  }
  const pelvisOffset=clamp(below+above,-settings.pelvis/100,settings.pelvis/100)*w,targets=planned[i].targets,planted=[],reaches=[];
  for(let side=0;side<2;side++){
   const l=legs[i][side],plan=plans[side],wanted=targets[side];
   const hip=add(base[i].points[l.hip],[0,pelvisOffset,0]);
   planted[side]=plan.states[i]==='PIN'&&plan.contacts[i]?.valid&&w>.999&&length(sub(wanted,hip))<l.reach*.995;
   reaches[side]=Math.max(l.reach*(1-.06*w),softReach(length(sub(wanted,hip)),l.reach,w));
   targets[side]=planted[side]?wanted:reachable(wanted,hip,reaches[side],plan.offsets[i],terrain);
  }
  planned[i]={pelvisOffset,targets,planted,reaches};
 }
 // Reach projection can move a swing toe onto an earlier riser. Anticipate that
 // resolved path as well, limiting *terrain correction* speed, not NN gait speed.
 // Retain exact planted contacts and do not spread correction onto flat frames.
 for(let pass=0;pass<3;pass++)for(let side=0;side<2;side++){
  const heights=planned.map((p,i)=>p.targets[side][1]-base[i].points[legs[i][side].foot][1]);
  for(let i=0;i<count;i++){
   if(weights[i]===0||planned[i].planted[side])continue;
   let lift=heights[i];
   for(const sign of [-1,1])for(let n=1;n<=12;n++){
    const j=i+sign*n;if(j<0||j>=count||weights[j]===0||planned[j].planted[side])break;
    lift=Math.max(lift,heights[j]-n/fps*1.5);
   }
   const l=legs[i][side],hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]),p=planned[i].targets[side].slice();
   let taper=1;for(let n=1;n<=12;n++)if(planned[Math.max(0,i-n)].planted[side]||planned[Math.min(count-1,i+n)].planted[side]){taper=smooth(n/12);break;}
   p[1]=base[i].points[l.foot][1]+heights[i]+(lift-heights[i])*weights[i]*taper;
   planned[i].targets[side]=reachable(p,hip,planned[i].reaches[side],plans[side].offsets[i],terrain);
  }
 }
 // A finite tread edge can remove a floor constraint in one sample. Descend
 // toward the contact instead of snapping down and declaring it planted.
 for(let side=0;side<2;side++)for(let i=1;i<count;i++){
  if(weights[i]===0||weights[i-1]===0)continue;
  const l=legs[i][side],prev=planned[i-1].targets[side][1];
  const target=planned[i].targets[side],drop=Math.min(0,base[i].points[l.foot][1]-base[i-1].points[l.foot][1])-1.5/fps;
  if(target[1]<prev+drop){
   const desired=target.slice();desired[1]=prev+drop;
   const hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]);
   const adjusted=reachable(desired,hip,planned[i].reaches[side],plans[side].offsets[i],terrain);
   if(length(sub(adjusted,target))>1e-6){planned[i].targets[side]=adjusted;planned[i].planted[side]=false;}
  }
 }
 // Plan rising swings from a retained contact to the next plant or NN exit pose.
 // Preserve lateral NN motion and contact timing; share progress along the incline.
 // Include exit swings too; fade their correction into the exact NN endpoint.
 for(let side=0;side<2;side++)for(const span of plans[side].swings){
  const a=Math.max(0,span.start-1),b=Math.min(count-1,span.end+1,exitIndex>a?exitIndex:count-1),plan=plans[side];
  const from=planned[a].targets[side],to=b===exitIndex?base[b].points[legs[b][side].foot]:planned[b].targets[side];
  if(!plan.contacts[a]||!planned[a].planted[side]||to[1]<=from[1]+.005||to[2]<=from[2]+.05)continue;
  const path=[];let arc=0;
  for(let i=a+1;i<b;i++){
   const u=(i-a)/(b-a),e=smooth(u),bump=4*u*(1-u);
   // Smooth shoulders clear the first/last riser without a tall mid-swing dome.
   const h=bump<=.5?bump:.5+.15*(1-Math.exp(-(bump-.5)/.15));
   const p=planned[i].targets[side].slice();
   p[2]=from[2]+(to[2]-from[2])*e;p[1]=from[1]+(to[1]-from[1])*e;
   const need=terrain.floorFor(p,plan.offsets[i])+settings.clearance/100*Math.sin(Math.PI*u)-p[1];
   arc=Math.max(arc,need/h);path.push({i,p,h});
  }
  for(const {i,p,h} of path){
   if(weights[i]===0||planned[i].planted[side])continue;
   p[1]+=arc*h;
   const original=planned[i].targets[side];
   for(let j=0;j<3;j++)p[j]=original[j]+weights[i]*(p[j]-original[j]);
   // The old exit arc moved ahead of the NN, then erased that lead in six
   // frames. Keep its clearance, but retain the NN-derived forward trajectory
   // instead of manufacturing a lead that must be braked away at the handoff.
   if(!planned[b].planted[side]){
    const e=smooth((i-a)/(b-a)),startOffset=from[2]-base[a].points[legs[a][side].foot][2],endOffset=to[2]-base[b].points[legs[b][side].foot][2];
    p[2]=base[i].points[legs[i][side].foot][2]+startOffset*(1-e)+endOffset*e;
   }
   const l=legs[i][side],hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]);
   planned[i].targets[side]=reachable(p,hip,planned[i].reaches[side],plan.offsets[i],terrain);
  }
 }
 // Reach projection can move a shoe corner across a riser after arc planning.
 // Spread that small added lift over neighbouring samples instead of exposing
 // a one-sample floor clamp. Preserve contact endpoints and never lower clearance.
 // A swing returning to the NN at the exit needs the same treatment as a landing.
 for(let side=0;side<2;side++)for(const span of plans[side].swings){
  const a=Math.max(0,span.start-1),b=Math.min(count-1,span.end+1,exitIndex>a?exitIndex:count-1),plan=plans[side];
  if(!plan.contacts[a]||(!plan.contacts[b]&&b!==exitIndex)||b-a<5)continue;
  let clipped=false;
  for(let i=a+2;i<b-1;i++){
   const y=planned[i].targets[side][1],floor=terrain.floorFor(planned[i].targets[side],plan.offsets[i]);
   if(Math.abs(y-floor)<1e-6&&2*y-planned[i-1].targets[side][1]-planned[i+1].targets[side][1]>.003)clipped=true;
  }
  if(!clipped)continue;
  const lo=Math.max(0,a-1),hi=Math.min(count-1,b+1),reference=[],fixed=new Map();
  for(let i=lo;i<=hi;i++){reference.push(planned[i].targets[side][1]);if(i<=a||i>=b||planned[i].planted[side])fixed.set(i-lo,reference.at(-1));}
  const heights=clearanceCurve(reference,reference,fixed,(fps*.025)**4);
  for(let i=a+1;i<b;i++){
   if(weights[i]===0||planned[i].planted[side])continue;
   const l=legs[i][side],hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]),p=planned[i].targets[side].slice();
   p[1]=heights[i-lo];planned[i].targets[side]=reachable(p,hip,planned[i].reaches[side],plan.offsets[i],terrain);
  }
 }
 // Fit clearance to the actual shoe path. Entry swings prepare their first
 // higher landing; retained-contact swings also shed the global arc's surplus
 // height as the foot comes forward. Preserve horizontal motion and toe-off.
 for(let side=0;side<2;side++)for(const span of plans[side].swings){
  const a=Math.max(0,span.start-1),b=Math.min(count-1,span.end+1,exitIndex>a?exitIndex:count-1),plan=plans[side];
  const from=planned[a].targets[side],to=b===exitIndex?base[b].points[legs[b][side].foot]:planned[b].targets[side];

  if(to[1]<=from[1]+.005||to[2]<=from[2]+.05||b-a<5||!weights.slice(a,b+1).some(w=>w>0))continue;
  const lo=Math.max(0,a-1),hi=Math.min(count-1,b+1),reference=[],floor=[],fixed=new Map();
  for(let i=lo;i<=hi;i++){
   const p=planned[i].targets[side],u=clamp((i-a)/(b-a),0,1);
   const required=terrain.floorFor(p,plan.offsets[i])+settings.clearance/100*Math.sin(Math.PI*u);
   reference.push(plan.contacts[a]?Math.max(base[i].points[legs[i][side].foot][1],required):p[1]);
   floor.push(required);
   if(i<=a||i>=b||weights[i]===0||planned[i].planted[side])fixed.set(i-lo,i===b?to[1]:p[1]);
  }
  const heights=clearanceCurve(reference,floor,fixed,(fps*.075)**4);
  for(let i=a+1;i<b;i++){
   if(weights[i]===0||planned[i].planted[side])continue;
   const p=planned[i].targets[side].slice();
   const l=legs[i][side],hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]);
   // Preserve the toe-off trajectory while the shoe trails the hip. Once it
   // swings forward, remove surplus height without altering forward velocity.
   const release=plan.contacts[a]?smooth((p[2]-hip[2]+.15)/.30):1;
   p[1]=plan.contacts[a]?p[1]+Math.min(0,heights[i-lo]-p[1])*release:heights[i-lo];
   planned[i].targets[side]=reachable(p,hip,planned[i].reaches[side],plan.offsets[i],terrain);
  }
 }
 // A reach-released foot must not wait for the NN's remaining stance.
 // Author and smooth recovery in the moving, rotating pelvis frame. World
 // forward motion alone can still drag backwards relative to the character.
 // Rejoin the source with positive relative progress; convert shoe collision
 // bounds into that same frame so terrain and smoothing share the criterion.
 for(let side=0;side<2;side++)for(const span of plans[side].swings){
  const a=Math.max(0,span.start-1),plan=plans[side];
  let b=Math.min(count-1,span.end+1,exitIndex>a?exitIndex:count-1);
  const from=planned[a].targets[side],endpoint=planned[b].targets[side];
  if(!plan.contacts[a]||!planned[a].planted[side]||planned[b].planted[side]||endpoint[1]<=from[1]+.005||endpoint[2]<=from[2]+.05||b-a<5)continue;
  const prev=Math.max(0,a-4);
  const rootSpeed=(base[a].points[0][2]-base[prev].points[0][2])*fps/Math.max(1,a-prev);
  const pelvis=legs[a][side].pelvis;
  const origin=i=>add(base[i].points[pelvis],[0,planned[i].pelvisOffset,0]);
  const axis=i=>rotate(base[i].q[pelvis],[0,-1,0]);
  const localAt=i=>dot(sub(planned[i].targets[side],origin(i)),axis(i));
  const sourceLocal=i=>dot(sub(base[i].points[legs[i][side].foot],base[i].points[pelvis]),axis(i));
  const sourceSpeed=(sourceLocal(a)-sourceLocal(prev))*fps/Math.max(1,a-prev);
  if(sourceSpeed>=rootSpeed*.25)continue;
  const worldAt=(i,value)=>{
   const o=origin(i),f=axis(i),p=planned[i].targets[side];
   return o[2]+(value-f[0]*(p[0]-o[0])-f[1]*(p[1]-o[1]))/f[2];
  };
  const start=localAt(a);
  const velocityAt=j=>{const n=Math.min(count-1,j+1),p=Math.max(0,j-1);return (localAt(n)-localAt(p))*fps/Math.max(1,n-p);};
  const minimumSpeed=Math.min(rootSpeed*.25,Math.max(0,(localAt(b)-start)*fps/(b-a))*.5);
  if(minimumSpeed<.02)continue;
  let v0=minimumSpeed;
  for(let j=a+6;j<b;j++){
   const end=velocityAt(j),average=(localAt(j)-start)*fps/(j-a);
   if(end<minimumSpeed||average<=0)continue;
   const qa=3*(v0+end-2*average),qb=6*average-4*v0-2*end;
   const u=qa>0?clamp(-qb/(2*qa),0,1):0;
   if(Math.min(v0,end,qa*u*u+qb*u+v0)>=minimumSpeed-1e-7){b=j;break;}
  }
  const seconds=(b-a)/fps,distance=localAt(b)-start,secant=distance/seconds;
  let v1=Math.max(0,velocityAt(b));
  const norm=Math.hypot(v0/secant,v1/secant);if(norm>3){v0*=3/norm;v1*=3/norm;}
  const forwardAt=u=>start+distance*smooth(u)+seconds*(v0*u*(1-u)**2-v1*u*u*(1-u));
  const lo=a,hi=Math.min(count-1,b+1),reference=[],bounds=[],fixed=new Map();
  for(let i=lo;i<=hi;i++){
   const p=planned[i].targets[side],u=clamp((i-a)/(b-a),0,1),wanted=worldAt(i,forwardAt(u));
   if(i<=a||i>=b){reference.push(-localAt(i));bounds.push(-localAt(i));fixed.set(i-lo,-localAt(i));continue;}
   let limit=wanted;
   if(terrain.floorFor([p[0],p[1],limit],plan.offsets[i])>p[1]-1e-5){
    let low=from[2],high=limit;
    for(let n=0;n<20;n++){const mid=(low+high)/2;if(terrain.floorFor([p[0],p[1],mid],plan.offsets[i])<=p[1]-1e-5)low=mid;else high=mid;}
    limit=low-1e-5;
   }
   reference.push(-forwardAt(u));bounds.push(-(localAt(i)+(limit-p[2])*axis(i)[2]));
  }
  const forward=clearanceCurve(reference,bounds,fixed,(fps*.065)**4);
  for(let i=a+1;i<b;i++){
   if(weights[i]===0||planned[i].planted[side])continue;
   const l=legs[i][side],hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]),p=planned[i].targets[side].slice();
   p[2]=worldAt(i,-forward[i-lo]);
   planned[i].targets[side]=reachable(p,hip,planned[i].reaches[side],plan.offsets[i],terrain);
  }
 }
 // One final constrained trajectory fit, after all reach/clearance/recovery
 // edits. Smoothing only intermediate passes lets later clamps reintroduce
 // velocity kicks. Retain actual material pins and pure NN frames exactly.
 // Fit all three position axes, with a small horizontal corridor and analytic
 // leg-reach bounds. Height uses the complete shoe/riser obstacle, not a lagging
 // low-pass filter that could drive a foot through terrain.
 for(let side=0;side<2;side++){
  const original=planned.map(p=>p.targets[side].slice());
  for(let a=0;a<count;){
   if(weights[a]===0||planned[a].planted[side]){a++;continue;}
   let b=a;while(b+1<count&&weights[b+1]>0&&!planned[b+1].planted[side])b++;
   const lo=Math.max(0,a-2),hi=Math.min(count-1,b+2);
   for(let pass=0;pass<2;pass++)for(const axis of [0,2,1]){
    const reference=[],floor=[],ceiling=[],budget=[],fixed=new Map();
    for(let i=lo;i<=hi;i++){
     const l=legs[i][side],p=planned[i].targets[side],hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]);
     reference.push(original[i][axis]);
     if(i<a||i>b){floor.push(-Infinity);ceiling.push(Infinity);fixed.set(i-lo,p[axis]);continue;}
     let radius2=planned[i].reaches[side]**2;
     for(let j=0;j<3;j++)if(j!==axis)radius2-=(p[j]-hip[j])**2;
     const radius=Math.sqrt(Math.max(0,radius2));
     let lower=hip[axis]-radius,upper=hip[axis]+radius;
     if(axis===1){
      lower=Math.max(lower,terrain.floorFor(p,plans[side].offsets[i]));
      if(lower>upper){p[0]=original[i][0];p[2]=original[i][2];const r=Math.sqrt(Math.max(0,planned[i].reaches[side]**2-(p[0]-hip[0])**2-(p[2]-hip[2])**2));lower=Math.max(hip[1]-r,terrain.floorFor(p,plans[side].offsets[i]));upper=hip[1]+r;}
      // Smoothing may anticipate a nearby obstacle, but cannot manufacture
      // an unbounded lift dome. Aim for the NN/planned height plus clearance;
      // actual collision/reach requirements take priority over this budget.
      budget[i-lo]=Math.min(upper,Math.max(lower,Math.max(original[i][1],base[i].points[l.foot][1])+settings.clearance/100));
     }else{lower=Math.max(lower,original[i][axis]-.025);upper=Math.min(upper,original[i][axis]+.025);}
     floor.push(Math.min(lower,upper));ceiling.push(upper);
    }
    if(axis===1){
     // Preserve the existing outgoing lift velocity at a retained contact.
     // A tighter mid-swing ceiling must not pull that first sample upward.
     const unconstrained=clearanceCurve(reference,floor,fixed,(fps*.06)**4,ceiling);
     if(a>0&&planned[a-1].planted[side])fixed.set(a-lo,unconstrained[a-lo]);
     for(let i=a;i<=b;i++){
      // Introduce the ceiling gradually after toe-off, and only where lift
      // exceeds the NN by more than the margin. A hard low ceiling here would
      // replace the old high arc with abrupt braking immediately after a riser.
      const entry=a>0&&planned[a-1].planted[side]?smooth((i-a+1)/(fps*.20)):1;
      const margin=Math.max(.02,2*settings.clearance/100);
      const surplus=smooth((unconstrained[i-lo]-base[i].points[legs[i][side].foot][1]-margin)/margin);
      ceiling[i-lo]=Math.max(budget[i-lo],unconstrained[i-lo]+(budget[i-lo]-unconstrained[i-lo])*entry*surplus);
     }
    }
    const curve=clearanceCurve(reference,floor,fixed,(fps*.06)**4,ceiling);
    for(let i=a;i<=b;i++)planned[i].targets[side][axis]=curve[i-lo];
   }
   a=b+1;
  }
 }
 // Preserve the NN ankle articulation in flight, then hand orientation back
 // to the world-space contact plan. Never rotate a retained material pin.
 // Evaluate the complete shoe before accepting an orientation: ankle position
 // alone cannot tell whether a pitched toe would cross a stair tread.
 const swingRotations=[[],[]];
 for(let side=0;side<2;side++){
  const candidates=[],limits=new Float64Array(count);
  const nextContact=new Int32Array(count);let next=count;
  for(let i=count-1;i>=0;i--){if(planned[i].planted[side])next=i;nextContact[i]=next;}
  let released=null;
  for(let i=0;i<count;i++){
   const l=legs[i][side],plan=plans[side],original=plan.rotations[i];
   if(planned[i].planted[side])released=original;
   if(weights[i]===0)released=null;
   swingRotations[side][i]=original;
   if(weights[i]===0||planned[i].planted[side])continue;
   const p=moved(base[i],[0,planned[i].pelvisOffset,0]);
   const solved=solve(p,l,planned[i].targets[side],parents,original);
   const delta=qm(solved.q[l.knee],qinv(l.kneeQ));
   let natural={footQ:qm(delta,l.footQ),toeQ:qm(delta,l.toeQ)};
   if(nextContact[i]<count)natural=landingRotation(natural,l,nextContact[i]-i,fps);
   natural=releaseRotation(natural,l,released);
   candidates[i]=natural;
   const rotationAt=u=>({footQ:qslerp(original.footQ,natural.footQ,u),toeQ:qslerp(original.toeQ,natural.toeQ,u)});
   const clear=u=>terrain.floorFor(planned[i].targets[side],geometry(base[i],l,rotationAt(u)))<=planned[i].targets[side][1]+1e-7;
   let limit=1;
   for(let n=1;n<=16;n++)if(!clear(n/16)){
    let lo=(n-1)/16,hi=n/16;
    for(let k=0;k<9;k++){const mid=(lo+hi)/2;if(clear(mid))lo=mid;else hi=mid;}
    limit=lo;break;
   }
   limits[i]=limit*weights[i];
  }
  // Anticipate contact/clearance limits on both sides, so a constraint cannot
  // abruptly twist the ankle on the frame it becomes active. This is cached
  // with the trajectory and adds no work to playback.
  const blendFrames=Math.ceil(.12*fps);
  for(let i=0;i<count;i++){
   if(!candidates[i])continue;
   let amount=limits[i];
   for(let j=Math.max(0,i-blendFrames);j<=Math.min(count-1,i+blendFrames);j++)amount=Math.min(amount,limits[j]+smooth(Math.abs(i-j)/blendFrames));
   const original=plans[side].rotations[i],natural=candidates[i];
   swingRotations[side][i]={footQ:qslerp(original.footQ,natural.footQ,amount),toeQ:qslerp(original.toeQ,natural.toeQ,amount)};
  }
 }
 const frames=[];
 for(let i=0;i<count;i++){
  const w=weights[i],{pelvisOffset,targets,planted}=planned[i];
  if(w===0){frames.push({pose:base[i],raw:base[i],feet:legs[i].map(l=>({side:l.side,state:'NN',target:base[i].points[l.foot],contact:null,error:0,penetration:0})),pelvisOffset:0,root:base[i].points[0],influence:0});continue;}
  let pose=moved(base[i],[0,pelvisOffset,0]);pose.points[0]=base[i].points[0];const feet=[];
  for(let side=0;side<2;side++){
   const l=legs[i][side],plan=plans[side],rotation=swingRotations[side][i];let target=targets[side];
   pose=solve(pose,l,target,parents,rotation);
   const error=length(sub(pose.points[l.foot],target)),floor=terrain.floorFor(pose.points[l.foot],S.footPoints(pose,l.foot,l.toe,l.side));
   const penetration=Math.max(0,floor-pose.points[l.foot][1]),soleGap=pose.points[l.foot][1]-floor;
   const pin=planted[side]&&error<.005;
   if(pin)metrics.pins[side]++;
   metrics.maxPenetration=Math.max(metrics.maxPenetration,penetration);metrics.maxReachError=Math.max(metrics.maxReachError,error);
   const contact=pin?plan.contacts[i]:null;
   feet.push({side:l.side,state:error>.015?'REACH':pin?(Math.abs(contact.angle)>.1?'ROLL':'PIN'):'SWING',target,contact,error,penetration,soleGap,contactPitch:contact?.extraPitch||0});
  }
  metrics.maxPelvis=Math.max(metrics.maxPelvis,Math.abs(pelvisOffset));
  frames.push({pose,raw:base[i],feet,pelvisOffset,root:base[i].points[0],influence:w});
 }
 return {frames,terrain,settings,metrics,speed,duration:run.duration,fps,sample:t=>frames[clamp(Math.round(t*fps),0,count-1)]};
}
const api={defaults,sanitize,decode,at,prepare,geometry,stableLeg};
if(typeof module!=='undefined')module.exports=api;else root.FootIK=api;
})(globalThis);
