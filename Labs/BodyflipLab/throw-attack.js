/* Approved throw composition with Bodyflip upper-body attachment. */
(function(root){'use strict';
const node=typeof module!=='undefined',S=node?require('./throw-source.js'):root.BodyflipThrowSource,{R,C,V,A}=S,B=node?require('./core.js'):root.BodyflipCore;
const Entry=node?require('./attack-entry.js'):root.BodyflipAttackEntry;
let data=null,assets=null,saved=null,rig=null;const cache=new Map();
const accepts=id=>id==='big-throw'||id==='small-throw',labels={'big-throw':'Big throw','small-throw':'Small throw'};
function load(value){if(value.schema!=='bodyflip-throws-v1')throw Error('Invalid throw package');data=value;assets=data.assets;saved=C.sanitize(data.settings);rig=A.rig(data.names,data.parents);cache.clear();return api;}
function held(pose,hand,o){const bind=assets[o.kind].bind||{},grip=o.grip||{},base=R.qm(pose.q[hand],bind.rotation||[0,0,0,1]),origin=R.add(pose.points[hand],R.rotate(pose.q[hand],bind.position||[0,0,0]));return {p:R.add(origin,R.rotate(base,grip.position||[0,0,0])),q:R.qm(base,grip.rotation?V.rotation(grip.rotation):[0,0,0,1]),phase:'held'};}
const sim={reference:o=>data.seeds[o.key],held:o=>held(o.pose||o.sample(o.release),o.hand,o)};
function build(id,amount,override={}){
 const clip=C.decode(data.clips.find(c=>c.id===id),data.parents),end=clip.duration*60,release=(saved.releases[id]??clip.duration*.5)*60;
 const controls={...V.config(saved.vanilla[id],end,release),...override};
 const kind=saved.throwObjects[id]==='sword'&&saved.imperialSpear?'spear':saved.throwObjects[id];
 const grip=saved.grips[id][kind],scale=saved.weaponScales[id][kind],target=override.target||saved.target;
 const raw=f=>C.sample(clip,f/60,data.parents);
 const keys=(pose,f)=>V.pose(V.pose(pose,data.parents,rig.elbow,controls.forearmKeys,f,true),data.parents,rig.hand,controls.keys,f);
 const preset=f=>keys(raw(f),f),options={key:id,kind,release:release/60,referenceRelease:release/60,sample:t=>preset(t*60),hand:rig.hand,duration:clip.duration,target,radius:saved.radius,controls,grip,scale};
 const seed=structuredClone(sim.reference(options));
 const fullPlan=A.prepare({rig,initial:raw(0),armedPose:raw(controls.armed),releasePose:preset(release),velocity:seed.v,...(kind!=='bomb'?{aimAxis:seed.axis,aimPoint:seed.p,aimBone:rig.hand}:{}),target,half:controls.halfAttack,aim:controls.aimAtTarget,armed:controls.armed});
 const full=f=>fullPlan.apply(raw(f),f),curve=A.chargeCurve(raw,controls.armed,release,end,rig);
 const speed=A.chargeSpeed(curve,amount,controls.slowdownBlend).multiplier,trigger=controls.armed*amount,releaseFrame=trigger+(release-controls.armed)/speed,finish=trigger+(curve.peak-controls.armed)/speed;
 const body=A.prepareBody({sample:full,rig,amount,trigger,returnFrame:release,end});
 let carry,partialPlan;
 const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(10+x*(-15+6*x));};
 function motion(f,useCarry=true){
  f=Math.max(0,Math.min(end,f));if(amount===1)return raw(f);const source=full(f);if(f<=trigger)return source;
  const entry=(f-trigger)*speed/Math.max(1e-9,Math.min(4,release-controls.armed));
  let pose=A.partialPose({source,charged:full(trigger),action:full(A.chargeFrame(curve,amount,(f-trigger)*speed)),rig,amount,recover:smooth((f-finish)/Math.max(1e-9,end-finish)),entry,ending:full(end),anchor:f>finish?full(finish):source,body,frame:f,anchorFrame:Math.min(f,finish)});
  if(useCarry&&amount>0){
   carry||={entry:A.prepareCarry({incoming:full,outgoing:f=>motion(f,false),rig,frame:trigger,duration:Math.min(4,release-controls.armed)/speed}),exit:A.prepareCarry({incoming:f=>motion(f,false),outgoing:f=>motion(f,false),rig,frame:finish,duration:Math.min(8,end-finish)})};
   if(entry<1)pose=A.carryPose(pose,carry.entry,f);else if(f>finish&&f<finish+8)pose=A.carryPose(pose,carry.exit,f);
  }return pose;
 }
 if(amount!==1&&controls.aimAtTarget){const rp=keys(motion(releaseFrame),releaseFrame),held=sim.held({...options,pose:rp});partialPlan=A.prepare({rig,initial:raw(0),releasePose:rp,velocity:R.rotate(fullPlan.rotation,seed.v),...(kind!=='bomb'?{aimAxis:R.rotate(held.q,assets[kind].longAxis),aimPoint:held.p,aimBone:rig.hand}:{}),target,half:controls.halfAttack,aim:true,armed:releaseFrame-trigger});}
 const sample=f=>{let pose=motion(f);if(amount===1)pose=fullPlan.apply(pose,f);else if(partialPlan&&f>trigger)pose=partialPlan.apply(pose,f-trigger);return keys(pose,Math.min(f,end));};
 const turn=partialPlan?R.qm(partialPlan.rotation,fullPlan.rotation):fullPlan.rotation;
 const held=sim.held({...options,pose:sample(releaseFrame)}),axis=R.rotate(held.q,assets[kind].longAxis||R.rotate(R.qinv(seed.q),seed.axis));
 return {clip,controls,kind,grip,scale,target,curve,seed,release,releaseFrame,finish,trigger,speed,sample,launch:{...held,v:R.mul(R.rotate(turn,seed.v),amount),omega:R.mul(axis,seed.twist*Math.PI/3),axis,twist:seed.twist}};
}

function model(id,amount=1){if(!data)throw Error('Throw data is not loaded');if(!accepts(id))throw Error('Unknown throw '+id);amount=id==='big-throw'?1:Math.max(0,Math.min(1,amount));const key=id+':'+amount;let m=cache.get(key);if(!m){m=build(id,amount);cache.set(key,m);if(cache.size>16)cache.delete(cache.keys().next().value);}return m;}
function create(event,segment,catalog,names,parents,settings,reference){
 const e=B.sanitizeJump(event);if(!accepts(e.attack))return null;
 const m=model(e.attack,(e.throwCharge??100)/100),base=segment.sample,start=segment.airStart+e.attackDelay;
 const map=names.map(n=>data.names.indexOf(n));if(map.some(i=>i<0))throw Error('Throw bone mapping incomplete');
 for(let i=1;i<names.length;i++)if(data.names[data.parents[map[i]]]!==names[parents[i]])throw Error('Throw skeleton parent mismatch '+names[i]);
 const remap=p=>({points:map.map(i=>p.points[i]),q:map.map(i=>p.q[i]),axes:map.map(i=>p.q[i]).map(R.toAxes)}),source0=R.localize(remap(m.sample(0)).points,remap(m.sample(0)).q,parents),spine=names.indexOf('spine_01'),pelvis=parents[spine],hand=names.indexOf(data.names[rig.hand]);
 const indices=names.map((_,i)=>i).filter(i=>{for(let j=i;j>=0;j=parents[j])if(j===spine)return true;return false;});
 function targetAt(f){const source=remap(m.sample(f)),local=R.localize(source.points,source.q,parents);local.q[spine]=R.qm(R.qm(R.qinv(source0.q[pelvis]),local.q[pelvis]),local.q[spine]);return local;}
 const initial=base(start).pose,from=R.localize(initial.points,initial.q,parents),arming=settings.kickToArmed?Entry.plan({from,targetAt,armed:m.trigger,fps:60,indices,names,minimum:e.attackIn}):null;
 const duration=arming?.duration??Math.min(Math.max(0,e.attackIn),Math.max(0,m.releaseFrame/60));
 const shift=arming?duration-m.trigger/60:0,end=start+m.clip.duration+shift,releaseTime=start+m.releaseFrame/60+shift,armedTime=start+m.trigger/60+shift,returnEnd=end+e.attackOut;
 const sourceFrame=age=>Math.min(m.clip.duration*60,arming?m.trigger+Math.max(0,age-duration)*60:age*60);
 function target(time){const local=targetAt(sourceFrame(time-start)),frame=base(time),out=R.localize(frame.pose.points,frame.pose.q,parents);for(const i of indices)out.q[i]=local.q[i];return R.fk(out,parents);}
 const entry=arming?Entry.direct({base,start,duration,armed:m.trigger,fps:60,parents,indices,targetAt}):B.transition(t=>base(start+t).pose,t=>target(start+t),duration,parents,indices,true);
 const poseAt=time=>time<start+duration?(arming?entry(time):entry(time-start)):target(time);
 let returning=null;
 function sample(time,...args){const frame=base(time,...args);if(time<start||time>=returnEnd)return frame;const pose=time<end?poseAt(time):(returning||=(B.transition(t=>poseAt(end+t),t=>base(end+t).pose,e.attackOut,parents,indices,true)))(time-end);return {...frame,pose,attack:{name:e.attack,phase:time>=end?'RETURN':time<releaseTime?'ARM':'ATTACK',start,end,armedTime,sourceFrame:sourceFrame(time-start),releaseTime,throw:true}};}
 const releaseSource=remap(m.sample(m.releaseFrame)),scale=Array.isArray(m.scale)?m.scale:[m.scale,m.scale,m.scale];
 function heldAt(pose){return {...held(pose,hand,m),kind:m.kind,scale};}
 function launchAt(pose,carrierVelocity=[0,0,0],carrierOmega=[0,0,0]){const attachment=heldAt(pose),turn=R.qm(pose.q[hand],R.qinv(releaseSource.q[hand])),v=R.add(R.mul(R.rotate(turn,m.launch.v),e.throwSpeed??1),carrierVelocity);return {...attachment,v,omega:R.add(R.rotate(turn,m.launch.omega),carrierOmega),axis:R.rotate(turn,m.launch.axis),comOffset:m.seed.comOffset,kind:m.kind,scale,mass:assets[m.kind].mass,aero:m.controls.aero,releaseTime,id:event.id+':'+e.attack};}
 function transportVelocity(poseAt,h=1/240){
  const point=p=>{const attachment=heldAt(p);return R.add(attachment.p,R.rotate(attachment.q,m.seed.comOffset));};
  const p=poseAt(releaseTime),turn=R.qm(p.q[hand],R.qinv(releaseSource.q[hand]));
  const actual=R.mul(R.sub(point(poseAt(releaseTime+h)),point(poseAt(releaseTime-h))),1/(2*h));
  const authored=R.mul(R.sub(point(remap(m.sample(m.releaseFrame+h*60))),point(remap(m.sample(m.releaseFrame-h*60)))),1/(2*h));
  return R.sub(actual,R.rotate(turn,authored));
 }
 function transportAngularVelocity(poseAt,h=1/240){
  const angular=(a,b)=>R.mul(R.qlog(R.qm(heldAt(b).q,R.qinv(heldAt(a).q))),1/(2*h)),p=poseAt(releaseTime),turn=R.qm(p.q[hand],R.qinv(releaseSource.q[hand]));
  const actual=angular(poseAt(releaseTime-h),poseAt(releaseTime+h)),authored=angular(remap(m.sample(m.releaseFrame-h*60)),remap(m.sample(m.releaseFrame+h*60)));
  return R.sub(actual,R.rotate(turn,authored));
 }
 return {sample,base,model:m,isThrow:true,kind:m.kind,hand,handBone:names[hand],indices,start,end,returnEnd,releaseTime,hitTime:releaseTime,armedTime,duration,arming,match:0,score:0,sourceFrame,heldAt,launchAt,transportVelocity,transportAngularVelocity,releaseSource};
}
const api={load,model,create,accepts,labels,get data(){return data;},get assets(){return assets;}};if(node)module.exports=api;else root.BodyflipThrowAttack=api;
})(globalThis);
