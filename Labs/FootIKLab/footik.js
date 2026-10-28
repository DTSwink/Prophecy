/* Terrain corrections are deltas from the NN gait, never a replacement gait. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const T=typeof module!=='undefined'?require('./terrain.js'):root.FootTerrain;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qslerp}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
const defaults={gait:'walk',phase:0,terrain:'stairs',height:16,depth:35,steps:12,enabled:true,clearance:4,pelvis:30,ghost:false,targets:true,ramp:false,bicolor:true,bones:false,translucency:70,ghostTranslucency:70,loop:true,trimIn:0,trimOut:5,speed:1,direction:'forward',slopeAngle:45,approach:'toward',upright:.55,rootYawSpeed:0,rootYawStart:0,rootYawStop:null,footYawLimit:45,stepAccent:100,showRoot:false,inclineGravity:false,minGravityIncline:45,fullGravity:100,energyConservation:100,deleteFloorFrame:-1};
function sanitize(input={}){
 const s={...defaults,...input};delete s.oldAnkle;delete s.walkHandoff;
 s.pinReleaseSpeed=Math.max(0,Number.isFinite(+s.pinReleaseSpeed)?+s.pinReleaseSpeed:.2);
 // Per-preset edits leave the procedural presets and the other lab's scenes alone.
 s.platformLayouts={};
 for(const key of ['stairs','down','uneven','flat','incline']){
  const list=input.platformLayouts?.[key];if(!Array.isArray(list))continue;
  const ids=new Set();s.platformLayouts[key]=list.slice(0,128).filter(p=>p&&typeof p.id==='string'&&p.id.length<=100&&!ids.has(p.id)&&['position','rotation','size'].every(k=>Array.isArray(p[k])&&p[k].length===(k==='rotation'?4:3)&&p[k].every(Number.isFinite))&&Math.hypot(...p.rotation)>1e-8&&(ids.add(p.id),true)).map(p=>({id:p.id,position:p.position.map(v=>clamp(v,-10000,10000)),rotation:p.rotation.map(v=>v/Math.hypot(...p.rotation)),size:p.size.map(v=>clamp(v,.02,1000))}));
 }
 for(const [k,a,b] of [['minGravityIncline',0,90],['fullGravity',0,100],['energyConservation',0,100],['stepAccent',0,400],['footYawLimit',5,90],['phase',0,1],['height',0,30],['depth',28,100],['steps',2,24],['clearance',0,20],['pelvis',0,60],['translucency',0,100],['ghostTranslucency',0,100],['trimIn',0,5-1/60],['trimOut',1/60,5],['speed',.1,2],['slopeAngle',0,90],['upright',0,1]])s[k]=clamp(Number.isFinite(+s[k])?+s[k]:defaults[k],a,b);
 s.deleteFloorFrame=s.deleteFloorFrame===''||s.deleteFloorFrame===null||!Number.isFinite(+s.deleteFloorFrame)?-1:Math.max(-1,Math.round(+s.deleteFloorFrame));
 s.steps=Math.round(s.steps);s.trimOut=Math.max(s.trimIn+1/60,s.trimOut);
 s.rootYawSpeed=clamp(Number.isFinite(+s.rootYawSpeed)?+s.rootYawSpeed:0,-360,360);
 s.rootYawStart=Math.max(0,Number.isFinite(+s.rootYawStart)?+s.rootYawStart:0);
 s.rootYawStop=s.rootYawStop===null||s.rootYawStop===''||!Number.isFinite(+s.rootYawStop)?null:Math.max(s.rootYawStart,+s.rootYawStop);
 s.gait=s.gait==='run'?'run':'walk';s.terrain=['stairs','down','uneven','flat','incline'].includes(s.terrain)?s.terrain:'stairs';
 s.direction=['forward','backward','left','right'].includes(s.direction)?s.direction:'forward';s.approach=s.approach==='parallel'?'parallel':'toward';
 for(const k of ['enabled','ghost','targets','ramp','bicolor','bones','loop','showRoot','inclineGravity'])s[k]=!!s[k];return s;
}
// Distance along the commanded root course, in metres from the visible start.
// Angular speed stays deg/s; outside the interval retain the attained heading.
function commandYaw(settings,time,speed){
 const distance=Math.max(0,speed*time),stop=settings.rootYawStop??Infinity;
 return speed>1e-8?(settings.rootYawSpeed||0)*Math.max(0,Math.min(distance,stop)-(settings.rootYawStart||0))/speed:0;
}
// Controller facing, independent of pelvis animation and actual travel velocity.
// The synthetic root bone is identity; its axes cannot supply this heading.
function rootHeading(run,time,settings={},speed=run.directionMeta?.commandSpeed||0){
 const angles=run.rootYawDegrees;let yaw;
 if(angles?.length){const f=clamp(time*run.fps,0,angles.length-1),i=Math.floor(f);yaw=angles[i]+((angles[i+1]??angles[i])-angles[i])*(f-i);}
 else yaw=commandYaw(settings,time,speed);
 const facing=run.directionMeta?.facingDegrees??({forward:0,left:-90,backward:180,right:90}[run.direction]||0),a=(facing+yaw)*Math.PI/180;
 return [Math.sin(a),0,Math.cos(a)];
}
function decode(data,parents){
 const travel=[0];for(let i=1;i<data.roots.length;i++){const a=data.roots[i-1],b=data.roots[i];travel.push(travel[i-1]+Math.hypot(b[0]-a[0],b[2]-a[2]));}
 const poses=data.poses.map((p,i)=>{const q=[[0,0,0,1],...p.axes.map(R.fromAxes)];return {points:[data.roots[i],...p.points],q,axes:q.map(R.toAxes)};});
 return {names:['root',...data.names],travel,fps:data.fps,duration:data.duration,periodSeconds:data.periodSeconds,nnRootWindow:!!data.nnRootWindow,rootYawSpeed:data.rootYawSpeed||0,rootYawDegrees:data.rootYawDegrees,direction:data.direction||data.command?.direction||'forward',directionMeta:data.directionMeta||data.command,poses,locals:poses.map(p=>R.localize(p.points,p.q,parents)),source:data.source,parents};
}
function travelAt(run,t){
 const f=clamp(t*run.fps,0,run.travel.length-1),i=Math.min(run.travel.length-2,Math.floor(f)),u=f-i;
 return run.travel[i]+(run.travel[i+1]-run.travel[i])*u;
}
function at(run,t){
 const f=clamp(t*run.fps,0,run.poses.length-1),i=Math.min(run.locals.length-2,Math.floor(f)),u=f-i;
 if(u<1e-9)return run.poses[i];
 const a=run.locals[i],b=run.locals[i+1];
 return R.fk({p:a.p.map((v,j)=>add(v,mul(sub(b.p[j],v),u))),q:a.q.map((v,j)=>qslerp(v,b.q[j],u))},run.parents);
}
const moved=(p,delta)=>({...p,points:p.points.map(v=>add(v,delta))});
function yawPose(p,degrees){
 if(!degrees)return p;
 const turn=R.qexp([0,degrees*Math.PI/180,0]),origin=p.points[0];
 const q=p.q.map(v=>qm(turn,v));
 return {...p,points:p.points.map(v=>add(origin,rotate(turn,sub(v,origin)))),q,axes:q.map(R.toAxes)};
}
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
 const local=[0,Math.sign(l.toeLocal[1])||1,0],upLocal=[l.side==='L'?1:-1,0,0];
 const start=rotate(released.footQ,local),forward=rotate(q.footQ,local);
 const startUp=rotate(released.footQ,upLocal),up=rotate(q.footQ,upLocal);
 // Measure pitch in the shoe's forward/up plane, independently of heading.
 // Both components vary continuously through vertical, unlike asin or a
 // horizontal-heading projection. Correct around its own lateral axis so
 // yaw differences cannot turn this toe-off limit into a sideways roll.
 const minimum=Math.atan2(start[1],startUp[1]),pitch=Math.atan2(forward[1],up[1]);
 if(pitch>=minimum)return q;
 const axis=unit(cross(forward,up));
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
// Compose yaw with the existing heel/toe roll instead of yawing about the ankle.
// One controller per stance: the accumulated rigid transform carries subsequent
// roll samples, including their material-pivot transfers, into the turned frame.
function createPinYaw(normal=[0,1,0],limitDegrees=45){
 let turn=[0,0,0,1],shift=[0,0,0],total=0;
 return (sample,p,l,clear=()=>true,dt=1/120)=>{
  const map=v=>add(rotate(turn,v),shift);
  let foot=map(sample.foot),point=map(sample.contact);
  let rotation={footQ:qm(turn,sample.rotation.footQ),toeQ:qm(turn,sample.rotation.toeQ)};
  const forward=rotate(rotation.footQ,[0,Math.sign(l.toeLocal[1])||1,0]);
  const up=rotate(rotation.footQ,[l.side==='L'?1:-1,0,0]);
  // The lateral axis retains a heading even when the toes point straight down.
  const heading=unit(cross(normal,cross(forward,up))),body=rotate(p.q[l.pelvis],[0,-1,0]);
  const desired=sub(body,mul(normal,dot(body,normal)));
  if(length(desired)<1e-5)return {...sample,foot,contact:point,rotation,yaw:total};
  const error=Math.atan2(dot(normal,cross(heading,unit(desired))),dot(heading,unit(desired)));
  const limit=limitDegrees*Math.PI/180,band=Math.min(10*Math.PI/180,limit*.4),start=limit-band;
  const excess=Math.max(0,Math.abs(error)-start);
  const correction=Math.sign(error)*(excess-band*(1-Math.exp(-excess/band)));
  let delta=clamp(correction,-600*Math.PI/180*dt,600*Math.PI/180*dt);
  if(Math.abs(delta)<1e-10&&Math.abs(total)<1e-10)return sample;
  let blocked=false;
  let pivot=point,pivotKind='roll';
  if(Math.abs(delta)>1e-10){
   // Near-flat shoes pivot at the sole centre; pitched shoes retain their
   // actual heel/toe point. This is a material transfer, never ankle rotation.
   const tilt=Math.acos(clamp(dot(up,normal),-1,1))*180/Math.PI;
   const flat=1-smooth((tilt-2)/6);
   if(flat>0){
    const shape=geometry(p,l,rotation),centre=mul([0,2,4,6].reduce((v,j)=>add(v,shape[j]),[0,0,0]),.25);
    let centrePoint=add(foot,centre);centrePoint=sub(centrePoint,mul(normal,dot(sub(centrePoint,point),normal)));
    pivot=add(point,mul(sub(centrePoint,point),flat));pivotKind=flat>.999?'centre':'transfer';
   }
   const candidate=a=>{const q=R.qexp(mul(normal,a));return {foot:add(pivot,rotate(q,sub(foot,pivot))),rotation:{footQ:qm(q,rotation.footQ),toeQ:qm(q,rotation.toeQ)}};};
   if(!clear(candidate(delta))){
    blocked=true;
    let lo=0,hi=1;for(let n=0;n<12;n++){const mid=(lo+hi)/2;if(clear(candidate(delta*mid)))lo=mid;else hi=mid;}delta*=lo;
   }
   if(Math.abs(delta)>1e-10){
    const q=R.qexp(mul(normal,delta)),next=candidate(delta);
    turn=qm(q,turn);shift=add(pivot,rotate(q,sub(shift,pivot)));total+=delta;
    foot=next.foot;rotation=next.rotation;point=pivot;
   }
  }
  const localPoint=rotate(qinv(rotation.footQ),sub(point,foot));
  return {...sample,foot,contact:point,rotation,localPoint,pivotKey:localPoint.map(v=>Math.round(v*1e6)).join(','),yaw:total,yawError:(error-delta)*180/Math.PI,pivotKind,blocked};
 };
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
 const descendingTerrain=terrain.rootHeight(terrain.end)<terrain.rootHeight(terrain.start)-.005;
 const {parents,names}=run,origin=run.poses[0].points[0];
 const source=Array.from({length:count},(_,i)=>moved(at(run,i/fps),[-origin[0],0,-origin[2]]));
 // Turning is already inferred from the NN root window; never spin its output.
 const raw=source;
 const base=raw.map(p=>moved(p,[0,terrain.rootHeight(p.points[0][2]),0]));
 const speed=(raw.at(-1).points[0][2]-raw[0].points[0][2])/run.duration;
 const facingAngle=(run.directionMeta?.facingDegrees??0)*Math.PI/180,travelHeading=R.qexp([0,-facingAngle,0]);
 const forwardTravel=i=>clamp(Math.cos(facingAngle+commandYaw(settings,i/fps,speed)*Math.PI/180),0,1);
 const legs=raw.map(p=>['L','R'].map(side=>stableLeg(p,names,side)));
 const weights=raw.map((p,i)=>influence(p,legs[i],terrain,settings)),plans=[];
 // Root arrival on the exit must not dissolve a still-planted trailing foot.
 // Finish through the existing complete-shoe fade beyond the final riser.
 const exitIndex=settings.terrain==='stairs'?base.findIndex((p,i)=>p.points[0][2]>=terrain.end&&weights[i]===0):-1;

 for(let side=0;side<2;side++){
  const offsets=raw.map((p,i)=>geometry(p,legs[i][side])),flags=[];let stance=false;
  for(let i=0;i<count;i++){
   const l=legs[i][side],lo=Math.max(0,i-1),hi=Math.min(count-1,i+1);
   // Measure stance from the actual turning NN, before terrain correction.
   const v=mul(sub(source[hi].points[l.foot],source[lo].points[l.foot]),fps/Math.max(1,hi-lo));
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
   let previousExtra=0,acquired=false;
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
    // Find the smallest supported roll that relieves extension. Travel may be
    // backward or lateral; the anatomical toe is not always the useful pivot.
    if(length(sub(chosen.foot,hip))>goal+1e-7){
     const feasible=[];let closest=chosen;
     for(const end of [Math.max(natural,roll.pitch+70),Math.min(natural,roll.pitch-55)]){
      let before=roll.sample(natural);
      for(let n=1;n<=7;n++){
       const next=roll.sample(natural+(end-natural)*n/7);
       if(!next.valid)break;
       if(length(sub(next.foot,hip))<length(sub(closest.foot,hip)))closest=next;
       if(length(sub(next.foot,hip))<=goal){
        let a=before,b=next;
        for(let k=0;k<12;k++){const mid=roll.sample((a.angle+b.angle)/2);if(length(sub(mid.foot,hip))>goal)a=mid;else b=mid;}
        feasible.push(b);break;
       }
       before=next;
      }
     }
     feasible.sort((a,b)=>Math.abs(a.angle-natural)-Math.abs(b.angle-natural));chosen=feasible[0]||closest;
    }
    const extra=previousExtra+clamp(chosen.angle-natural-previousExtra,-540/fps,540/fps);
    chosen=roll.sample(natural+extra);previousExtra=extra;
    // A lower tread can arrive in the NN's stance interval before the actual
    // leg can reach it. Continue the swing until contact is reachable instead
    // of pulling the pelvis down by an entire step to manufacture that plant.
    const lowerLanding=descendingTerrain&&hit.height<terrain.rootHeight(raw[i].points[0][2])-.005;
    const loweredHip=add(hip,[0,-Math.min(.02,settings.pelvis/100),0]);
    if(!acquired&&lowerLanding&&(!chosen.valid||length(sub(chosen.foot,loweredHip))>current.reach*.995))continue;
    acquired=true;
    // On descent the ramp lowers the hip while an old upper tread stays high.
    // Do not spend the whole leg reach horizontally to retain that contact:
    // it must also leave room for the source gait's downward leg posture.
    const supportHip=loweredHip.slice();
    if(descendingTerrain)supportHip[1]=Math.max(supportHip[1],chosen.foot[1]+raw[i].points[l.hip][1]-raw[i].points[l.foot][1]-.02);
    if(descendingTerrain&&weights[i]>0&&chosen.foot[2]<hip[2]-.15&&length(sub(chosen.foot,supportHip))>current.reach*.995)break;
    // Also release when the rolling contact exceeds physical leg reach.
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
   if(next>=count||!targets[next])continue;
   // A strafe can meet a higher neighbouring tile before its next landing.
   // Look at the complete departing shoe, not only the next contact height,
   // so the retained roll finishes while there is still time to lift smoothly.
   const nonforward=settings.rootYawSpeed!==0||(run.direction&&run.direction!=='forward'),l=legs[end][side],offset=sub(targets[end],raw[end].points[l.foot]);
   let approachingObstacle=false;
   if(nonforward)for(let j=end+1;j<=Math.min(next,end+Math.round(fps*.12));j++){
    const point=add(raw[j].points[l.foot],offset),shape=geometry(raw[j],legs[j][side],rotations[end]);
    if(terrain.floorFor(point,shape)>targets[end][1]+.015){approachingObstacle=true;break;}
   }
   if(targets[next][1]<=targets[end][1]+.08&&!approachingObstacle)continue;
   const current=contacts[end],surface=terrain.tiles.find(t=>t.id===current.surface);
   const nextSurface=contacts[next]?terrain.tiles.find(t=>t.id===contacts[next].surface):terrain.hit(targets[next][0],targets[next][2]);
   if(!surface||!nextSurface||(nextSurface.y<=surface.y+.005&&!approachingObstacle))continue;
   let start=end;while(start>0&&contacts[start-1]?.stanceId===current.stanceId)start--;
   const lead=Math.min(Math.round(fps*.05),Math.max(0,end-start-Math.round(fps*.12)));
   if(!lead)continue;
   const release=end-lead,rollStart=Math.max(start,release-Math.round(fps*.20)),roll=stanceRolls.get(current.stanceId);
   if(!roll)continue;
   const angles=contacts.slice(rollStart,end+1).map(c=>c.angle),retimed=[];
   // A return to the NN gait needs less toe-down than another retained plant:
   // excessive pitch makes the toe demand a sharp vertical riser-clearance lift.
   const limit=contacts[next]?.valid?45:35;
   // Earlier departure must use the reach required at that earlier frame.
   // Compressing the late-stance reach roll here over-rotated backward feet.
   const early=clamp(contacts[release].angle,roll.pitch-limit,roll.pitch+limit);
   const toeOff=Math.max(angles[0],Math.min(angles.at(-1),roll.pitch+limit));
   const terminal=early+(toeOff-early)*forwardTravel(release);
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
  // Apply before planning the adjacent swings, so landing and departure inherit
  // the real turned contact, and pelvis/reach solve against its rotated ankle.
  let yawStance=null,yawContact=null;
  for(let i=0;i<count;i++){
   const c=contacts[i];if(!c){yawStance=null;continue;}
   if(c.stanceId!==yawStance){yawStance=c.stanceId;yawContact=createPinYaw([0,1,0],settings.footYawLimit);}
   const l=legs[i][side],sample={foot:targets[i],contact:c.point,rotation:rotations[i],localPoint:c.localPoint,pivotKey:c.pivotKey};
   const turned=yawContact(sample,base[i],l,r=>{
    const shape=geometry(raw[i],l,r.rotation);
    // A planted turn must leave room for departure, not just numerical clearance.
    // Ending 6mm from a riser forced an 8cm lift in25ms as the shoe advanced.
    // Reserve 4cm so a blocked turn releases while a smooth lift still fits.
    return [[0,0],[.04,0],[-.04,0],[0,.04],[0,-.04]].every(([x,z])=>terrain.floorFor(add(r.foot,[x,0,z]),shape)<=r.foot[1]+1e-6);
   });
   if(turned.blocked&&Math.abs(turned.yawError)>settings.footYawLimit){
    // A foot trapped against a riser cannot satisfy a tighter twist limit by
    // spinning through it. End this contact and let the normal swing clear it.
    const id=c.stanceId;for(let j=i;j<count&&contacts[j]?.stanceId===id;j++){
     states[j]='SWING';contacts[j]=null;targets[j]=undefined;limits[j]=undefined;
     rotations[j]={footQ:legs[j][side].footQ,toeQ:legs[j][side].toeQ};offsets[j]=geometry(raw[j],legs[j][side]);
    }
    yawStance=null;continue;
   }
   targets[i]=turned.foot;rotations[i]=turned.rotation;offsets[i]=geometry(raw[i],l,turned.rotation);
   const tile=terrain.tiles.find(t=>t.id===c.surface);
   contacts[i]={...c,point:turned.contact,local:sub(turned.contact,[0,tile.y,tile.z0]),localPoint:turned.localPoint,pivotKey:turned.pivotKey,yaw:turned.yaw,yawError:turned.yawError,pivotKind:turned.pivotKind};
   limits[i]=softReach(length(sub(turned.foot,base[i].points[l.hip])),l.reach*.995,weights[i]);
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
     // During a turn, waiting for course-forward swing progress can hold an
     // obsolete heading until the last landing frames. Release that heading
     // over the swing while the separate pitch cap preserves toe-off.
     const turning=Math.abs(commandYaw(settings,b/fps,speed)-commandYaw(settings,a/fps,speed))>1e-6;
     const blend=Math.max(rotationRelease,arrive,turning?smooth((i-a)/(fps*.18)):0);
     const yaw=(commandYaw(settings,i/fps,speed)-commandYaw(settings,a/fps,speed))*Math.PI/180;
     const held=yaw?{footQ:qm(R.qexp([0,yaw,0]),rotations[a].footQ),toeQ:qm(R.qexp([0,yaw,0]),rotations[a].toeQ)}:rotations[a];
     rotations[i]={footQ:qslerp(held.footQ,qslerp(legs[i][side].footQ,sourceRotation.footQ,arrive),blend),toeQ:qslerp(held.toeQ,qslerp(legs[i][side].toeQ,sourceRotation.toeQ,arrive),blend)};
    }
    // Aim directly at the actual landing orientation, rather than replaying
    // the source foot's moving airborne rotation plus a contact delta.
    if(contacts[b]){
     const settle=smooth(1-(b-i)/Math.min(fps*.22,(b-a)*.5));
     rotations[i]={footQ:qslerp(rotations[i].footQ,rotations[b].footQ,settle),toeQ:qslerp(rotations[i].toeQ,rotations[b].toeQ,settle)};
     if(run.direction==='forward'||!run.direction)rotations[i]=landingRotation(rotations[i],legs[i][side],b-i,fps);
    }
    if(contacts[a]){
     const held=releaseRotation(rotations[i],legs[i][side],rotations[a]);
     // A heel-side landing can be above the preceding toe-off pitch. Retire
     // that old contact's cap during the same preparation that aims the shoe
     // at its next material contact, rather than dropping it on contact.
     const lowerContact=descendingTerrain&&contacts[b]&&contacts[b].point[1]<contacts[a].point[1]-.005;
     const landing=(lowerContact||(run.direction&&run.direction!=='forward'))&&(contacts[b]||states[b]==='NN')?smooth(1-(b-i)/Math.min(fps*.22,(b-a)*.5)):0;
     rotations[i]={footQ:qslerp(held.footQ,rotations[i].footQ,landing),toeQ:qslerp(held.toeQ,rotations[i].toeQ,landing)};
    }
    offsets[i]=geometry(raw[i],legs[i][side],rotations[i]);
    if(Math.abs(contacts[a]?.yaw||0)>1e-6&&i-a<fps*.15){
     // A yawing toe can finish right beside a riser. Do not rotate its upper
     // corners through that riser at release and pay for it with an instant
     // vertical lift. Retain only the blocked part of rotation until it clears.
     const startFoot=targets[a],ceiling=Math.max(p[1],startFoot[1]+raw[i].points[l.foot][1]-raw[a].points[l.foot][1]+2*(i-a)/fps);
     if(terrain.floorFor(startFoot,offsets[i])>ceiling){
      const desired=rotations[i],at=u=>({footQ:qslerp(rotations[a].footQ,desired.footQ,u),toeQ:qslerp(rotations[a].toeQ,desired.toeQ,u)});
      let lo=0,hi=1;for(let n=0;n<14;n++){const mid=(lo+hi)/2;if(terrain.floorFor(startFoot,geometry(raw[i],legs[i][side],at(mid)))<=ceiling)lo=mid;else hi=mid;}
      rotations[i]=at(lo);offsets[i]=geometry(raw[i],legs[i][side],rotations[i]);
     }
    }
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

 const planned=[],metrics={maxPenetration:0,maxReachError:0,maxPelvis:0,maxFlatDeviation:0,pins:[0,0]},pelvisGoals=[],pelvisBounds=[];
 // A departing foot may need to finish its recovery after the terrain fade.
 // Keep that ownership per leg; the other leg and root remain pure NN there.
 const recoveryWeights=[new Float64Array(count),new Float64Array(count)];
 const footWeight=(i,side)=>Math.max(weights[i],recoveryWeights[side][i]);
 for(let i=0;i<count;i++){
  const w=weights[i];
  if(w===0){
   pelvisGoals.push(0);
   pelvisBounds.push([0,0]);
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
  pelvisBounds.push(low<=high?[low*w,high*w]:[goal*w,goal*w]);
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
  planned[i].pelvisOffset=clamp(below+above,-settings.pelvis/100,settings.pelvis/100)*w;
 }
 // Round the approach/recovery corners on descents, within the planted legs'
 // actual reach interval. A brief lower-tread contact must not produce a sharp
 // down/up body bob; feet keep their material contacts throughout the curve.
 if(descendingTerrain){
  const fixed=new Map();for(let i=0;i<count;i++)if(weights[i]===0)fixed.set(i,0);
  const curve=clearanceCurve(planned.map(p=>p.pelvisOffset),pelvisBounds.map(b=>b[0]),fixed,(fps*.08)**4,pelvisBounds.map(b=>b[1]));
  for(let i=0;i<count;i++)planned[i].pelvisOffset=curve[i];
 }
 const nextPlants=descendingTerrain?plans.map(plan=>{
  const next=new Int32Array(count);let at=count;
  for(let i=count-1;i>=0;i--){if(plan.states[i]==='PIN'&&plan.contacts[i]?.valid)at=i;next[i]=at;}
  return next;
 }):null;
 for(let i=0;i<count;i++){
  const w=weights[i];if(w===0)continue;
  const pelvisOffset=planned[i].pelvisOffset,targets=planned[i].targets,planted=[],reaches=[];
  for(let side=0;side<2;side++){
   const l=legs[i][side],plan=plans[side],wanted=targets[side];
   const hip=add(base[i].points[l.hip],[0,pelvisOffset,0]);
   planted[side]=plan.states[i]==='PIN'&&plan.contacts[i]?.valid&&w>.999&&length(sub(wanted,hip))<l.reach*.995;
   // Bring swing reach into the landing's reach before contact. Otherwise the
   // soft knee limit holds the ankle back until PIN suddenly permits a longer
   // leg, producing a position kick on a newly reachable lower tread.
   const nextPlant=nextPlants?.[side][i]??count;
   const landing=nextPlant<count?smooth(1-(nextPlant-i)/(fps*.12)):0;
   reaches[side]=Math.max(l.reach*(1-.06*w),softReach(length(sub(wanted,hip)),l.reach,w*(1-landing)));
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
  // Keep departure travel even when yaw needs a bounded height envelope.
  // Skipping this entire path left released feet following the NN's remaining
  // stance: they lifted over the riser while staying almost fixed horizontally.
  const turned=Math.abs(plan.contacts[a]?.yaw||0)>1e-6||Math.abs(plan.contacts[b]?.yaw||0)>1e-6;
  const path=[];let arc=0;
  for(let i=a+1;i<b;i++){
   const u=(i-a)/(b-a),e=smooth(u),bump=4*u*(1-u);
   // Smooth shoulders clear the first/last riser without a tall mid-swing dome.
   const h=bump<=.5?bump:.5+.15*(1-Math.exp(-(bump-.5)/.15));
   const p=planned[i].targets[side].slice();
   p[2]=from[2]+(to[2]-from[2])*e;
   if(!turned)p[1]=from[1]+(to[1]-from[1])*e;
   const need=terrain.floorFor(p,plan.offsets[i])+settings.clearance/100*Math.sin(Math.PI*u)-p[1];
   arc=Math.max(arc,need/h);path.push({i,p,h});
  }
  for(const {i,p,h} of path){
   if(weights[i]===0||planned[i].planted[side])continue;
   // Turned shoes can meet an obstacle very close to departure. A global arc
   // amplifies that local obstacle; the later whole-shoe clearance fit handles it.
   if(!turned)p[1]+=arc*h;
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
 function fitSwingHeights(){
 // Fit clearance to the actual shoe path. Entry swings prepare their first
 // higher landing; retained-contact swings also shed the global arc's surplus
 // height as the foot comes forward. On descent, use the moving ramp carrier
 // rather than carrying the old tread height until the next detected NN plant.
 // Preserve horizontal motion and fixed contacts; fit departure smoothly.
 for(let side=0;side<2;side++)for(const span of plans[side].swings){
  const a=Math.max(0,span.start-1),b=Math.min(count-1,span.end+1,exitIndex>a?exitIndex:count-1),plan=plans[side];
  const from=planned[a].targets[side],to=b===exitIndex?base[b].points[legs[b][side].foot]:planned[b].targets[side];

  const descending=terrain.rootHeight(raw[b].points[0][2])<terrain.rootHeight(raw[a].points[0][2])-.005;
  if((!descending&&to[1]<=from[1]+.005)||to[2]<=from[2]+.05||b-a<5||!weights.slice(a,b+1).some(w=>w>0))continue;
  const lo=Math.max(0,a-1),hi=Math.min(count-1,b+1),reference=[],floor=[],fixed=new Map();
  for(let i=lo;i<=hi;i++){
   const p=planned[i].targets[side],u=clamp((i-a)/(b-a),0,1);
   const required=terrain.floorFor(p,plan.offsets[i])+settings.clearance/100*Math.sin(Math.PI*u);
   const gaitHeight=base[i].points[legs[i][side].foot][1];
   reference.push(descending?Math.max(required,Math.min(p[1],gaitHeight)):plan.contacts[a]?Math.max(gaitHeight,required):p[1]);
   floor.push(required);
   if(i<=a||i>=b||weights[i]===0||planned[i].planted[side])fixed.set(i-lo,i===b?to[1]:p[1]);
  }
  const heights=clearanceCurve(reference,floor,fixed,(fps*.075)**4);
  for(let i=a+1;i<b;i++){
   if(weights[i]===0||planned[i].planted[side])continue;
   const p=planned[i].targets[side].slice();
   const l=legs[i][side],hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]);
   // On ascent, retain toe-off height while the shoe trails the hip. Descent
   // must shed the stale tread offset throughout the clearance-safe swing.
   const release=descending?1:plan.contacts[a]?smooth((p[2]-hip[2]+.15)/.30):1;
   p[1]=descending||plan.contacts[a]?p[1]+Math.min(0,heights[i-lo]-p[1])*release:heights[i-lo];
   planned[i].targets[side]=reachable(p,hip,planned[i].reaches[side],plan.offsets[i],terrain);
  }
 }
 }
 if(!descendingTerrain)fitSwingHeights();
 // A reach-released foot must not wait for the NN's remaining stance.
 // Author and smooth recovery in the moving, rotating pelvis frame. World
 // forward motion alone can still drag backwards relative to the character.
 // Rejoin the source with positive relative progress; convert shoe collision
 // bounds into that same frame so terrain and smoothing share the criterion.
 for(let side=0;side<2;side++)for(const span of plans[side].swings){
  const a=Math.max(0,span.start-1),plan=plans[side];
  let b=Math.min(count-1,span.end+1,exitIndex>a?exitIndex:count-1);
  const from=planned[a].targets[side],endpoint=planned[b].targets[side];
  if(!plan.contacts[a]||!planned[a].planted[side]||planned[b].planted[side]||(!descendingTerrain&&endpoint[1]<=from[1]+.005)||endpoint[2]<=from[2]+.05||b-a<5)continue;
  const prev=Math.max(0,a-4);
  const rootSpeed=(base[a].points[0][2]-base[prev].points[0][2])*fps/Math.max(1,a-prev);
  const pelvis=legs[a][side].pelvis;
  const origin=i=>add(base[i].points[pelvis],[0,planned[i].pelvisOffset,0]);
  // Author recovery along travel in the root frame. Anatomical pelvis-forward
  // reverses during backward gait and is perpendicular during a strafe.
  const axis=i=>rotate(settings.rootYawSpeed?R.qexp([0,-facingAngle-commandYaw(settings,i/fps,speed)*Math.PI/180,0]):travelHeading,rotate(base[i].q[pelvis],[0,-1,0]));
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
  // If the spatial exit still catches the NN folding backwards, there is no
  // positive-progress bridge to it. Find a later forward-moving source pose
  // within THIS swing, with compatible endpoint velocity and no backtracking.
  // Do not force the foot to wait behind the pelvis until that source catches up.
  if(b===exitIndex&&localAt(b)<=start){
   let join=-1;
   for(let j=b+1;j<=Math.min(span.end,count-2);j++){
    const average=(sourceLocal(j)-start)*fps/(j-a),end=(sourceLocal(j+1)-sourceLocal(j-1))*fps/2;
    if(average<=.1||end<=.1)continue;
    const initial=Math.min(rootSpeed*.25,average*.5),qa=3*(initial+end-2*average),qb=6*average-4*initial-2*end;
    const u=qa>0?clamp(-qb/(2*qa),0,1):0;
    if(Math.min(initial,end,qa*u*u+qb*u+initial)>=Math.min(.25,initial*.5)){join=j;break;}
   }
   if(join<0)continue;
   b=join;
   for(let i=a+1;i<b;i++){
    recoveryWeights[side][i]=1-smooth((i-a)/(b-a));
    planned[i].reaches??=legs[i].map(l=>l.reach);
   }
  }
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
  // Carry contact velocity briefly into departure before gaining relative
  // travel. Instant positive pelvis-local speed would snap the released foot.
  const incoming=(localAt(a)-localAt(Math.max(0,a-1)))*fps,carryTime=Math.min(.06,seconds*.25);
  const carryAt=u=>descendingTerrain&&u*seconds<carryTime?(incoming-v0)*u*seconds*(1-u*seconds/carryTime)**2:0;
  const forwardAt=u=>start+distance*smooth(u)+seconds*(v0*u*(1-u)**2-v1*u*u*(1-u))+carryAt(u);
  const lo=a,hi=Math.min(count-1,b+1),reference=[],bounds=[],upper=[],fixed=new Map();
  for(let i=lo;i<=hi;i++){
   const p=planned[i].targets[side],u=clamp((i-a)/(b-a),0,1),wanted=worldAt(i,forwardAt(u));
   upper.push(-localAt(i)-carryAt(u));
   if(i<=a||i>=b){reference.push(-localAt(i));bounds.push(-localAt(i));fixed.set(i-lo,-localAt(i));continue;}
   // Recovery may advance the descending swing, but must not introduce a
   // later wait/backtrack merely to follow a slower cubic reference.
   let limit=descendingTerrain?Math.max(p[2]+carryAt(u)/axis(i)[2],wanted):wanted;
   if(terrain.floorFor([p[0],p[1],limit],plan.offsets[i])>p[1]-1e-5){
    let low=from[2],high=limit;
    for(let n=0;n<20;n++){const mid=(low+high)/2;if(terrain.floorFor([p[0],p[1],mid],plan.offsets[i])<=p[1]-1e-5)low=mid;else high=mid;}
    limit=low-1e-5;
   }
   reference.push(-Math.max(descendingTerrain?localAt(i)+carryAt(u):-Infinity,forwardAt(u)));bounds.push(-(localAt(i)+(limit-p[2])*axis(i)[2]));
   // A real shoe obstacle takes precedence if it leaves no forward corridor.
   upper[i-lo]=Math.max(upper[i-lo],bounds[i-lo]);
  }
  const forward=clearanceCurve(reference,bounds,fixed,(fps*.065)**4,descendingTerrain?upper:null);
  for(let i=a+1;i<b;i++){
   if(footWeight(i,side)===0||planned[i].planted[side])continue;
   const l=legs[i][side],hip=add(base[i].points[l.hip],[0,planned[i].pelvisOffset,0]),p=planned[i].targets[side].slice();
   p[2]=worldAt(i,-forward[i-lo]);
   planned[i].targets[side]=reachable(p,hip,planned[i].reaches[side],plan.offsets[i],terrain);
  }
 }
 // Descent height must see the recovered horizontal path; otherwise a shoe
 // that has cleared the old tread still carries that tread's stale height.
 if(descendingTerrain)fitSwingHeights();
 // One final constrained trajectory fit, after all reach/clearance/recovery
 // edits. Smoothing only intermediate passes lets later clamps reintroduce
 // velocity kicks. Retain actual material pins and pure NN frames exactly.
 // Fit all three position axes, with a small horizontal corridor and analytic
 // leg-reach bounds. Height uses the complete shoe/riser obstacle, not a lagging
 // low-pass filter that could drive a foot through terrain.
 for(let side=0;side<2;side++){
  const original=planned.map(p=>p.targets[side].slice());
  for(let a=0;a<count;){
   if(footWeight(a,side)===0||planned[a].planted[side]){a++;continue;}
   let b=a;while(b+1<count&&footWeight(b+1,side)>0&&!planned[b+1].planted[side])b++;
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
     }else{
      lower=Math.max(lower,original[i][axis]-.025);upper=Math.min(upper,original[i][axis]+.025);
      // Smoothing a recovered step must not spend extra vertical clearance
      // merely to cross a riser a few samples sooner. Keep the available
      // forward corridor at this height, then fit height continuously.
      if(run.direction&&run.direction!=='forward'){
       // Lateral smoothing can cross an adjacent tile edge even when forward
       // travel is clear. Keep both horizontal axes inside the existing shoe
       // corridor instead of manufacturing a new vertical obstacle at release.
       const anchor=clamp(original[i][axis],lower,upper),point=p.slice();point[axis]=anchor;
       const floorBudget=Math.max(original[i][1],terrain.floorFor(point,plans[side].offsets[i]));
       const clear=value=>{point[axis]=value;return terrain.floorFor(point,plans[side].offsets[i])<=floorBudget+1e-7;};
       const bound=edge=>{if(clear(edge))return edge;let lo=anchor,hi=edge;for(let n=0;n<18;n++){const mid=(lo+hi)/2;if(clear(mid))lo=mid;else hi=mid;}return lo;};
       lower=bound(lower);upper=bound(upper);
      }
      if(axis===2&&recoveryWeights[side][i]>0){
       const clear=z=>terrain.floorFor([p[0],p[1],z],plans[side].offsets[i])<=p[1]+1e-7;
       if(!clear(upper)&&clear(lower)){
        let lo=lower,hi=upper;
        for(let n=0;n<18;n++){const mid=(lo+hi)/2;if(clear(mid))lo=mid;else hi=mid;}
        upper=lo;
       }
      }
     }
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
    for(let i=a;i<=b;i++)planned[i].targets[side][axis]=clamp(original[i][axis]+(curve[i-lo]-original[i][axis])*footWeight(i,side),floor[i-lo],ceiling[i-lo]);
   }
   a=b+1;
  }
 }
 // Keep the root on its navigation ramp and the completed shoe paths intact.
 // Retiming just the pelvis height around real weight transfers gives stairs
 // a load/pull-up/continue rhythm instead of constant ramp ascent. The existing
 // NN body bob remains underneath this terrain-only correction. Ascent loads
 // by bending; descent can first hold the body over the higher support before
 // lowering onto the next tread, using only the legs' soft extension headroom.
 const pelvisTransfers=new Float64Array(count);
 if(settings.enabled&&settings.pelvis>0&&['stairs','down'].includes(settings.terrain)&&settings.height>0){
  const knots=[];
  for(let i=1;i<count;i++)if(planned[i].planted.some((pin,side)=>pin&&!planned[i-1].planted[side])){
   if(!knots.length||i-knots.at(-1)>.12*fps)knots.push(i);
  }
  const end=base.findIndex(p=>p.points[0][2]>=terrain.end);
  if(end>=0&&knots.length&&end>knots.at(-1))knots.push(end);
  const reference=new Array(count).fill(0),lower=[],upper=[],fixed=new Map();
  for(let k=1;k<knots.length;k++){
   const a=knots[k-1],b=knots[k],y0=base[a].points[0][1],y1=base[b].points[0][1];
   for(let i=a;i<=b;i++){
    const u=(i-a)/(b-a),eased=u*u*u*(10+u*(-15+6*u));
    reference[i]=(y0+(y1-y0)*eased-base[i].points[0][1])*weights[i]*(settings.stepAccent/100);
   }
  }
  for(let i=0;i<count;i++){
   const offset=planned[i].pelvisOffset,limit=settings.pelvis/100;
   let lo=Math.max(-.10,-limit-offset),hi=Math.min(.10,limit-offset);
   for(let side=0;side<2;side++){
    const l=legs[i][side],hip=add(base[i].points[l.hip],[0,offset,0]),target=planned[i].targets[side];
    // Neither accent may pull a foot off its accepted path. Unlike an upward
    // push, a descent also needs the positive half of the weight-transfer arc;
    // forbidding all extension retained only its crouching half.
    const radius=Math.max(length(sub(target,hip)),descendingTerrain?softReach(l.reach,l.reach,weights[i]):0);
    const vertical=Math.sqrt(Math.max(0,radius*radius-(target[0]-hip[0])**2-(target[2]-hip[2])**2));
    lo=Math.max(lo,target[1]-hip[1]-vertical);hi=Math.min(hi,target[1]-hip[1]+vertical);
   }
   lower.push(Math.min(0,lo));upper.push(Math.max(0,hi));
   if(!weights[i]||!knots.length||i<=knots[0]||i>=knots.at(-1))fixed.set(i,0);
  }
  const curve=clearanceCurve(reference,lower,fixed,(fps*.08)**4,upper);
  for(let i=0;i<count;i++){pelvisTransfers[i]=curve[i];planned[i].pelvisOffset+=curve[i];}
 }
 // Preserve the NN ankle articulation in flight, then hand orientation back
 // to the world-space contact plan. Never apply swing articulation to a retained contact.
 // Evaluate the complete shoe before accepting an orientation: ankle position
 // alone cannot tell whether a pitched toe would cross a stair tread.
 const swingRotations=[[],[]];
 for(let side=0;side<2;side++){
  const candidates=[],limits=new Float64Array(count);
  const nextContact=new Int32Array(count),nextRelease=new Int32Array(count);let next=count,free=count;
  for(let i=count-1;i>=0;i--){if(planned[i].planted[side])next=i;else free=i;nextContact[i]=next;nextRelease[i]=free;}
  let released=null,levelExit=false,levelOffset=null,releasedAt=-1;
  for(let i=0;i<count;i++){
   const l=legs[i][side],plan=plans[side],original=plan.rotations[i];
   if(planned[i].planted[side]){
    releasedAt=i;
    // On the final tread the NN is already rolling off onto the same level.
    // Its subsequent ankle rotation is normal gait, not unfinished stair push.
    // The full-shoe clearance test below still bounds every free rotation.
    const contact=plan.contacts[i];levelExit=['stairs','down'].includes(settings.terrain)&&
     Math.abs(contact.point[1]-terrain.rootHeight(terrain.end))<.005;
    released=levelExit?null:original;
    if(levelExit&&!planned[i+1]?.planted[side]){
     const p=moved(base[i],[0,planned[i].pelvisOffset,0]);
     const solved=solve(p,l,planned[i].targets[side],parents,original);
     const delta=qm(solved.q[l.knee],qinv(l.kneeQ));
     levelOffset={at:i,footQ:qm(original.footQ,qinv(qm(delta,l.footQ))),toeQ:qm(original.toeQ,qinv(qm(delta,l.toeQ)))};
    }
    if(!levelExit)levelOffset=null;
   }
   const rotationWeight=footWeight(i,side);
   if(rotationWeight===0)released=null;
   // A final swing returning to gait has no next terrain plant to own its
   // rotation. Retire the toe-off cap in gait time, before the spatial IK fade
   // can squeeze a whole running ankle recovery into two frames.
   const cycle=run.periodSeconds||1;
   const gaitReturn=!levelExit&&releasedAt>=0&&nextContact[i]===count?
    smooth(((i-releasedAt)/fps-cycle*.2)/(cycle*.2)):0;
   if(rotationWeight===0)limits[i]=gaitReturn;
   // A level departure already matches gait rotation at the toe pin. Do not
   // fade from the held stair orientation again at release or at the NN exit.
   if(levelExit&&nextRelease[i]-i<=Math.ceil(.12*fps))limits[i]=1;
   swingRotations[side][i]=original;
   if(rotationWeight===0||planned[i].planted[side])continue;
   const p=moved(base[i],[0,planned[i].pelvisOffset,0]);
   const solved=solve(p,l,planned[i].targets[side],parents,original);
   const delta=qm(solved.q[l.knee],qinv(l.kneeQ));
   let natural={footQ:qm(delta,l.footQ),toeQ:qm(delta,l.toeQ)};
   if(levelOffset){
    // Carry the release orientation offset onto the moving gait, rather than
    // freezing the shoe while the source toe-off runs ahead of it.
    const u=smooth((i-levelOffset.at)/(fps*.12)),identity=[0,0,0,1];
    natural={footQ:qm(qslerp(levelOffset.footQ,identity,u),natural.footQ),toeQ:qm(qslerp(levelOffset.toeQ,identity,u),natural.toeQ)};
   }
   if(nextContact[i]<count&&(run.direction==='forward'||!run.direction))natural=landingRotation(natural,l,nextContact[i]-i,fps);
   const held=releaseRotation(natural,l,released);
   const lowerContact=descendingTerrain&&nextContact[i]<count&&releasedAt>=0&&plan.contacts[nextContact[i]]?.point[1]<plan.contacts[releasedAt]?.point[1]-.005;
   const contactReturn=(lowerContact||(run.direction&&run.direction!=='forward'))&&nextContact[i]<count?smooth(1-(nextContact[i]-i)/(fps*.22)):0;
   const releaseReturn=Math.max(gaitReturn,contactReturn);
   natural={footQ:qslerp(held.footQ,natural.footQ,releaseReturn),toeQ:qslerp(held.toeQ,natural.toeQ,releaseReturn)};
   candidates[i]=natural;
   const rotationAt=u=>({footQ:qslerp(original.footQ,natural.footQ,u),toeQ:qslerp(original.toeQ,natural.toeQ,u)});
   const clear=u=>terrain.floorFor(planned[i].targets[side],geometry(base[i],l,rotationAt(u)))<=planned[i].targets[side][1]+1e-7;
   let limit=1;
   for(let n=1;n<=16;n++)if(!clear(n/16)){
    let lo=(n-1)/16,hi=n/16;
    for(let k=0;k<9;k++){const mid=(lo+hi)/2;if(clear(mid))lo=mid;else hi=mid;}
    limit=lo;break;
   }
   limits[i]=limit*(levelExit?1:rotationWeight+(1-rotationWeight)*gaitReturn);
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
   if(settings.rootYawSpeed||(run.direction&&run.direction!=='forward')){
    // The footprint changes while rotating. A lower blend fraction is not
    // automatically clearer: a shoe edge can briefly cross a tread corner
    // between two clear orientations. Validate the actual anticipated blend.
    const l=legs[i][side],target=planned[i].targets[side];
    const clear=u=>terrain.floorFor(target,geometry(base[i],l,{footQ:qslerp(original.footQ,natural.footQ,u),toeQ:qslerp(original.toeQ,natural.toeQ,u)}))<=target[1]+1e-7;
    if(!clear(amount)&&clear(0)){
     let lo=0,hi=amount;
     for(let n=0;n<16;n++){const mid=(lo+hi)/2;if(clear(mid))lo=mid;else hi=mid;}
     amount=lo;
    }
   }
   swingRotations[side][i]={footQ:qslerp(original.footQ,natural.footQ,amount),toeQ:qslerp(original.toeQ,natural.toeQ,amount)};
  }
 }
 const frames=[];
 for(let i=0;i<count;i++){
  const w=Math.max(weights[i],recoveryWeights[0][i],recoveryWeights[1][i]),{pelvisOffset,targets,planted}=planned[i];
  if(w===0){frames.push({pose:base[i],raw:base[i],feet:legs[i].map(l=>({side:l.side,state:'NN',target:base[i].points[l.foot],contact:null,error:0,penetration:0})),pelvisOffset:0,root:base[i].points[0],influence:0});continue;}
  let pose=moved(base[i],[0,pelvisOffset,0]);pose.points[0]=base[i].points[0];const feet=[];
  for(let side=0;side<2;side++){
   const l=legs[i][side],plan=plans[side],rotation=swingRotations[side][i];let target=targets[side];
   if(footWeight(i,side)===0){feet.push({side:l.side,state:'NN',target,contact:null,error:0,penetration:0});continue;}
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
  frames.push({pose,raw:base[i],feet,pelvisOffset,pelvisTransfer:pelvisTransfers[i],root:base[i].points[0],influence:w});
 }
 return {frames,terrain,settings,metrics,speed,duration:run.duration,fps,sample:t=>frames[clamp(Math.round(t*fps),0,count-1)]};
}
const api={defaults,sanitize,commandYaw,rootHeading,decode,travelAt,at,prepare,geometry,stableLeg,solve,yawPose,createPinYaw};
if(typeof module!=='undefined')module.exports=api;else root.FootIK=api;
})(globalThis);
