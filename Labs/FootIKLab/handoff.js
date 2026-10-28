/* Causal 30Hz NN continuation from terrain-corrected current/previous poses. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const K=typeof module!=='undefined'?require('./footik.js'):root.FootIK;
const {add,sub,mul,length,unit,rotate,qm,qinv,qlog,qexp}=R;
function requestFor(model,run){
 if(!model.settings.enabled||model.settings.terrain==='flat'||model.settings.height===0)return null;
 const level=model.terrain.rootHeight(model.terrain.end),margin=.005;
 // Current contact geometry only: no search for a future cached gait match.
 const index=model.frames.findIndex((f,i)=>i>=4&&i%2===0&&i<model.frames.length-8&&
  f.root[2]>=model.terrain.end&&f.feet.every(x=>!x.contact)&&
  ['L','R'].every(side=>{
   const l=S.leg(f.pose,run.names,side),p=f.pose.points[l.foot];
   return S.footPoints(f.pose,l.foot,l.toe,side).every(o=>p[1]+o[1]>=level+margin);
  }));
 if(index<0)return null;
 const time=index/model.fps,frames=Math.ceil((model.duration-time)*30)+1;
 // Keep BOTH corrected poses in their actual world orientation. Their own
 // previous/current carrier yaws accompany the eight future root commands.
 const seed=i=>{const p=model.frames[i].pose;return {points:p.points,axes:p.axes};};
 const current=model.frames[index].root,previous=model.frames[index-4].root;
 const command=mul(sub(current,previous),30);command[1]=0;
 const roots=Array.from({length:frames+9},(_,i)=>i===0?previous:add(current,mul(command,(i-1)/30)));
 const rootYawDegrees=roots.map((_,i)=>K.commandYaw(model.settings,time+(i-1)/30,model.speed));
 return {index,time,request:{...(run.nnRootWindow?{policy:'run'}:{}),rootYawDegrees,gait:model.settings.gait,direction:run.direction||'forward',drawn:false,names:run.names,frames,roots,seeds:[seed(index-4),seed(index)]}};
}
function apply(model,run,plan,data){
 if(JSON.stringify(data.names)!==JSON.stringify(run.names.slice(1))||data.fps!==30||data.inferences!==plan.request.frames-1)
  throw Error('Invalid terrain NN continuation');
 const continuation=K.decode(data,run.parents),at=t=>K.at(continuation,t),dt=1/model.fps,blend=.10;
 const start=model.frames[plan.index].pose,previous=model.frames[plan.index-1].pose;
 const a=R.localize(start.points,start.q,run.parents),p=R.localize(previous.points,previous.q,run.parents);
 const b=R.localize(at(0).points,at(0).q,run.parents),n=R.localize(at(dt).points,at(dt).q,run.parents);
 const velocity=a.q.map((q,j)=>sub(mul(qlog(qm(q,qinv(p.q[j]))),1/dt),mul(qlog(qm(n.q[j],qinv(b.q[j]))),1/dt)));
 const speed=a.p.map((v,j)=>mul(sub(sub(v,p.p[j]),sub(n.p[j],b.p[j])),1/dt));
 const frames=model.frames.slice();let maxPenetration=0;
 for(let i=plan.index;i<frames.length;i++){
  const elapsed=(i-plan.index)/model.fps,raw=at(elapsed);let pose=raw;
  if(i===plan.index)pose=start;
  else if(elapsed<blend){
   // Carry the incoming render velocity briefly into the NEW NN output.
   // No old cached-gait target participates in this transition.
   const local=R.localize(raw.points,raw.q,run.parents),carry=elapsed*(1-elapsed/blend)**2;
   for(let j=1;j<run.names.length;j++){
    local.q[j]=unit(qm(qexp(mul(velocity[j],carry)),local.q[j]));
    const corrected=add(local.p[j],mul(speed[j],carry));
    local.p[j]=j===1?corrected:mul(unit(corrected),length(local.p[j]));
   }
   pose=R.fk(local,run.parents);
  }
  const feet=['L','R'].map(side=>{
   const l=S.leg(pose,run.names,side),target=pose.points[l.foot],floor=model.terrain.floorFor(target,S.footPoints(pose,l.foot,l.toe,side));
   const penetration=Math.max(0,floor-target[1]);maxPenetration=Math.max(maxPenetration,penetration);
   return {side,state:'NN',target,contact:null,error:0,penetration,soleGap:target[1]-floor};
  });
  frames[i]={pose,raw,feet,root:raw.points[0],pelvisOffset:0,pelvisTransfer:0,influence:0,nn:true};
 }
 const handoff={frame:plan.index/2,time:plan.time,policyHz:30,historySeconds:1/30,inferences:data.inferences,cache:data.cache,seconds:data.seconds,blendSeconds:blend,maxPenetration};
 return {...model,frames,handoff,sample:t=>frames[Math.max(0,Math.min(frames.length-1,Math.round(t*model.fps)))]};
}
async function prepare(run,settings,resume,cancelled=()=>false){
 const model=K.prepare(run,settings),plan=requestFor(model,run);
 if(!plan)return model;
 const response=await resume(plan.request);
 if(cancelled())return null;
 return apply(model,run,plan,response);
}
const api={requestFor,apply,prepare};if(typeof module!=='undefined')module.exports=api;else root.FootHandoff=api;
})(globalThis);
