/* Bodyflip adapter only. All contact, shoe, roll and knee rules remain FootIKLab's. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const F=typeof module!=='undefined'?require('../FootIKLab/surface.js'):root.SharedFootIK?.surface;
const {add,sub,mul,length,unit,rotate,qm,qinv,qslerp}=R;
const up=[0,1,0],identity=[0,0,0,1],fps=120,dt=1/fps;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
function track(source,{start=0,surfaces,names,parents,gait='walk'}){
 if(!F||F.apiVersion!==1)throw Error('Shared Foot IK is unavailable. Restart Bodyflip Lab to load its current server.');
 const indices=names.flatMap((name,i)=>i===0||/^(thigh|calf|foot|ball)_/.test(name)?[i]:[]),settings=F.settings({gait}),frames=[];
 const terrain={surfaces,pick:p=>{let best;for(const surface of surfaces){const point=surface.closest(p),distance=length(sub(p,point));if(!best||distance<best.distance)best={surface,point,distance};}return best;}};
 let solver=null,entry=0,lastNormal=null,stance=[false,false],building=false,exit=null,landing=null;
 const legs=p=>['L','R'].map(side=>F.stableLeg(p,names,side));
 function intent(t,frame,active){
  const a=source(Math.max(start,t-dt)),span=dt;
  return legs(frame.pose).map((l,side)=>{
   const v=mul(sub(frame.pose.points[l.foot],a.pose.points[l.foot]),1/span),speed=Math.max(.1,Math.hypot(frame.velocity?.[0]||0,frame.velocity?.[2]||frame.speed||0));
   const {stance:on,clearance:low}=F.gaitIntent(frame.pose,l,v,speed,active[side]);
   const vertical=v[1]-(frame.root[1]-a.root[1])/span;
   return {on,until:on?0:vertical<-.01?Math.max(0,low-.035)/-vertical:Infinity};
  });
 }
 function ensure(time){
  if(building)return;building=true;try{
  const count=Math.ceil(Math.max(0,time-start)*fps-1e-8);
  while(frames.length<=count){
   const t=start+frames.length*dt,frame=source(t),surface=surfaces.find(s=>s.id===frame.capsule?.surfaceId);
   const epoch=frame.capsule?.landingTime??null;if(epoch!==landing){solver=null;exit=null;lastNormal=null;stance=[false,false];landing=epoch;}
   const active=['IDLE','WALK','RUN'].includes(frame.phase)&&frame.capsule?.grounded&&surface&&surface.normal[1]<.99999;
   if(!active){
    if(solver&&['IDLE','WALK','RUN'].includes(frame.phase)&&frame.capsule?.grounded)exit={time:t,frame:frames.at(-1)};
    solver=null;lastNormal=null;stance=[false,false];
    const w=exit&&['IDLE','WALK','RUN'].includes(frame.phase)&&frame.capsule?.grounded?1-smooth((t-exit.time)/.12):0;
    frames.push(w>0&&exit.frame?{...exit.frame,pelvisOffset:mul(exit.frame.pelvisOffset,w),offsets:exit.frame.offsets.map(q=>qslerp(identity,q,w)),feet:[]}:null);continue;
   }
   exit=null;
   if(!solver){solver=F.createFeet({names,parents,terrain,settings});entry=Math.max(t,landing??start);lastNormal=surface.normal;}
   // The upright capsule owns the root. Compensate its rounded-bottom
   // clearance in the mesh pelvis, with Foot IK's body tilt and NN articulation.
   lastNormal=unit(add(mul(lastNormal,.8),mul(surface.normal,.2)));
   const surfaceQ=R.fromTo(up,lastNormal),raw=frame.pose,sourceLegs=legs(raw),base=surface.project(frame.root);
   const bodyQ=F.bodyRotation(lastNormal,settings.upright);
   const transform=(rotation,origin)=>{const q=raw.q.map(q=>qm(rotation,q));return {points:raw.points.map(p=>add(origin,rotate(rotation,sub(p,frame.root)))),q,axes:q.map(R.toAxes)};};
   const baseline=transform(bodyQ,base),terrainPose=transform(surfaceQ,base);baseline.points[0]=frame.root;
   const contacts=intent(t,frame,stance);stance=contacts.map(c=>c.on);const untilPlant=contacts.map(c=>c.until);
   const solved=solver.step({baseline,terrainPose,source:raw,sourceLegs,stance,untilPlant,time:t,normal:lastNormal,surfaceQ,height:baseline.points[names.indexOf('pelvis')][1]-frame.root[1],velocity:frame.velocity||[0,0,frame.speed||0]});
   const a=R.localize(raw.points,raw.q,parents),b=R.localize(solved.pose.points,solved.pose.q,parents),weight=entry===start?1:smooth((t-entry)/.12);
   frames.push({landing,pelvisOffset:mul(sub(b.p[names.indexOf('pelvis')],a.p[names.indexOf('pelvis')]),weight),offsets:indices.map(i=>qslerp(identity,qm(b.q[i],qinv(a.q[i])),weight)),feet:solved.feet,surfaceId:surface.id});
  }
  }finally{building=false;}
 }
 function sample(time,rawOverride){
  const raw=source(time,rawOverride);ensure(time);
  const f=Math.max(0,(time-start)*fps),i=Math.min(frames.length-1,Math.floor(f+1e-8)),oldA=frames[i],oldB=frames[Math.min(i+1,frames.length-1)],epoch=raw.capsule?.landingTime??null,a=oldA?.landing===epoch?oldA:null,b=(oldB?.landing===epoch?oldB:null)||a,u=clamp(f-i,0,1);
  // Jumps/falls belong to the existing planner. Do not modify their pins or
  // blend a grounded correction into the first authored support frame.
  if(!['IDLE','WALK','RUN'].includes(raw.phase)||!raw.capsule?.grounded||(!a&&!b))return raw;
  const local=R.localize(raw.pose.points,raw.pose.q,parents);
  const pelvis=names.indexOf('pelvis'),pa=a?.pelvisOffset||[0,0,0],pb=b?.pelvisOffset||[0,0,0];local.p[pelvis]=add(local.p[pelvis],add(pa,mul(sub(pb,pa),u)));
  indices.forEach((j,k)=>{local.q[j]=qm(qslerp(a?.offsets[k]||identity,b?.offsets[k]||identity,u),local.q[j]);});
  return {...raw,pose:R.fk(local,parents),footIK:{shared:true,surfaceId:a?.surfaceId||b?.surfaceId,feet:(u<.5?a:b)?.feet||[]}};
 }
 return {sample,prepare:ensure};
}
const api={track,available:!!F&&F.apiVersion===1};if(typeof module!=='undefined')module.exports=api;else root.BodyflipFootIK=api;
})(globalThis);
