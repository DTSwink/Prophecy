/* FinalNoAim motion and manifest launch; shared Bodyflip spine steering/recovery. */
(function(root){'use strict';
const node=typeof module!=='undefined',S=node?require('./throw-source.js'):root.BodyflipThrowSource,{R,C,V,A}=S,B=node?require('./core.js'):root.BodyflipCore;
let data=null,assets=null,saved=null,rig=null,referenceData=null;const cache=new Map();
const accepts=id=>id==='big-throw'||id==='small-throw',labels={'big-throw':'Big throw','small-throw':'Small throw'};
function load(value){if(value.schema!=='bodyflip-throws-v1')throw Error('Invalid throw package');data=value;assets=data.assets;saved=C.sanitize(data.settings);rig=A.rig(data.names,data.parents);cache.clear();referenceData=null;return api;}
function held(pose,hand,o){const bind=assets[o.kind].bind||{},grip=o.grip||{},base=R.qm(pose.q[hand],bind.rotation||[0,0,0,1]),origin=R.add(pose.points[hand],R.rotate(pose.q[hand],bind.position||[0,0,0]));return {p:R.add(origin,R.rotate(base,grip.position||[0,0,0])),q:R.qm(base,grip.rotation?V.rotation(grip.rotation):[0,0,0,1]),phase:'held'};}
const sim={reference:o=>data.seeds[o.key],held:o=>held(o.pose||o.sample(o.release),o.hand,o)};
function build(id,amount,override={}){
 if(amount===1&&data.finalNoAim){
  const meta=data.finalNoAim.manifest.clips.find(c=>c.id===id),clip=C.decode(data.finalNoAim.clips.clips.find(c=>c.id===id),data.parents),sample=f=>C.sample(clip,f/60,data.parents),seed={...data.seeds[id],...meta.launch};
  return {finalNoAim:true,clip,controls:{...meta.physics,armed:meta.armedFrame,aimAtTarget:false},kind:meta.kind,grip:meta.grip,scale:meta.scale,target:saved.target,seed,release:meta.releaseFrame,releaseFrame:meta.releaseFrame,finish:meta.releaseFrame,trigger:meta.armedFrame,speed:1,sample,launch:meta.launch};
 }
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

function model(id,amount=1,aim=true){if(!data)throw Error('Throw data is not loaded');if(!accepts(id))throw Error('Unknown throw '+id);amount=id==='big-throw'?1:Math.max(0,Math.min(1,amount));const key=id+':'+amount+':'+aim;let m=cache.get(key);if(!m){m=build(id,amount,aim?{}:{aimAtTarget:false});cache.set(key,m);if(cache.size>16)cache.delete(cache.keys().next().value);}return m;}
function loadReference(value){if(value.schema!=='bodyflip-throw-reference-v1'||value.sourceHash!==data?.sourceHash)throw Error('Throw reference does not match imported source');referenceData=value;}
function referenceAt(id,time,names){
 const m=model(id,1),record=referenceData?.clips[id];if(!record)return null;
 const source=m.sample(time*60),map=names.map(n=>data.names.indexOf(n)),pose={points:map.map(i=>source.points[i]),q:map.map(i=>source.q[i]),axes:map.map(i=>source.axes[i])};
 let object;if(time<record.release)object=held(source,rig.hand,m);else {const f=Math.max(0,Math.min(record.frames.length-1,(time-record.release)*record.fps)),i=Math.min(record.frames.length-2,Math.floor(f)),u=f-i,a=record.frames[i],b=record.frames[i+1];object={...a,p:R.add(a.p,R.mul(R.sub(b.p,a.p),u)),q:R.qslerp(a.q,b.q,u)};}
 return {pose,object:{...object,kind:record.kind,scale:record.scale},scene:referenceData.scene,model:m};
}
function create(event,segment,catalog,names,parents,settings,reference){
 const e=B.sanitizeJump(event);if(!accepts(e.attack)||e.throwSpeed===0)return null;
 // The source contains grip/charge edits, but Bodyflip alone owns target aiming.
 const m=model(e.attack,(e.throwCharge??100)/100,false),J=node?require('./jump-attack.js'):root.BodyflipJumpAttack;
 const map=names.map(n=>data.names.indexOf(n));if(map.some(i=>i<0))throw Error('Throw bone mapping incomplete');
 for(let i=1;i<names.length;i++)if(data.names[data.parents[map[i]]]!==names[parents[i]])throw Error('Throw skeleton parent mismatch '+names[i]);
 const remap=p=>({points:map.map(i=>p.points[i]),q:map.map(i=>p.q[i]),axes:map.map(i=>p.q[i]).map(R.toAxes)}),hand=names.indexOf(data.names[rig.hand]);
 // Final exports retain 60 Hz timing. Physical speedScale is already in the manifest launch.
 const rate=e.throwSpeed;if(!(rate>0))return null;
 const fps=60*rate,poses=Array.from({length:Math.ceil(m.clip.duration*60)+1},(_,f)=>remap(m.sample(f)));
 // Big throw's long authored comeback is replaced by the shared Attack out.
 // This is a source-frame marker, not frame 50 of the scene or entry blend.
 const after=settings[e.attack==='big-throw'?'bigThrowReturnFrames':'smallThrowReturnFrames']??B.defaults[e.attack==='big-throw'?'bigThrowReturnFrames':'smallThrowReturnFrames'];
 const phases={armed:m.trigger,hit:m.releaseFrame,end:Math.min(poses.length-1,m.releaseFrame+after)};
 const clip={poses,meta:{name:e.attack,fps,phases},duration:(poses.length-1)/fps};
 // Use exactly the same entry, five-spine transfer, legal arms, soft-leg
 // compensation and recovery as the other upper-body attacks.
 const body=J.create(event,segment,null,names,parents,settings,reference,{clipOverride:clip});if(!body)return null;
 const releaseTime=body.hitTime,scale=Array.isArray(m.scale)?m.scale:[m.scale,m.scale,m.scale];
 function sample(time,...args){const frame=body.sample(time,...args);return frame.attack?{...frame,attack:{...frame.attack,releaseTime,throw:true}}:frame;}
 function heldAt(pose){return {...held(pose,hand,m),kind:m.kind,scale};}
 const center=pose=>{const p=heldAt(pose);return R.add(p.p,R.rotate(p.q,m.seed.comOffset));};
 // Full-charge throws transport the final manifest launch with the held frame,
 // adding carrier translation once. Partial charge retains its procedural derivative.
 function releaseVelocity(poseAt,h=1/(1000*rate),carrierPoseAt=t=>segment.sample(t).pose){
  if(m.finalNoAim){const turn=R.qm(heldAt(poseAt(releaseTime)).q,R.qinv(m.seed.q)),pelvis=names.indexOf('pelvis'),at=t=>carrierPoseAt(t).points[pelvis],carrier=R.mul(R.sub(at(releaseTime),at(releaseTime-h)),1/h);return R.add(R.mul(R.rotate(turn,m.seed.v),rate),carrier);}
  const p=center(poseAt(releaseTime)),a=center(poseAt(releaseTime-h)),b=center(poseAt(releaseTime-2*h));return R.mul(R.add(R.sub(R.mul(p,3),R.mul(a,4)),b),1/(2*h));}
 function releaseAngularVelocity(poseAt,h=1/(1000*rate)){const q=heldAt(poseAt(releaseTime)).q,delta=t=>R.qlog(R.qm(q,R.qinv(heldAt(poseAt(t)).q)));return R.mul(R.sub(R.mul(delta(releaseTime-h),4),delta(releaseTime-2*h)),1/(2*h));}
 // Throw Lab authors spear spin along its shaft; sideways hand swing is not tumbling.
 function projectileAngularVelocity(poseAt){if(m.finalNoAim)return R.mul(R.rotate(R.qm(heldAt(poseAt(releaseTime)).q,R.qinv(m.seed.q)),m.seed.omega),rate);if(m.kind!=='spear'||!Number.isFinite(m.controls.twist))return releaseAngularVelocity(poseAt);const axis=R.unit(R.rotate(heldAt(poseAt(releaseTime)).q,assets[m.kind].longAxis));return R.mul(axis,m.controls.twist*Math.PI/3*e.throwSpeed);}
 function launchAt(pose,velocity=null,omega=null){const attachment=heldAt(pose),at=t=>sample(t).pose;return {...attachment,v:velocity||releaseVelocity(at),omega:omega||projectileAngularVelocity(at),axis:R.rotate(attachment.q,assets[m.kind].longAxis||R.rotate(R.qinv(m.seed.q),m.seed.axis)),comOffset:m.seed.comOffset,mass:assets[m.kind].mass,aero:m.controls.aero,releaseTime,id:event.id+':'+e.attack};}
 // Retain the adapter method names until the native tooling is repackaged;
 // launchAt now consumes these as complete velocities, never additive impulses.
 const track={...body,sample,base:segment.sample,model:m,clip,isThrow:true,kind:m.kind,hand,handBone:names[hand],aimReferenceTime:segment.jumpStart,throwDirection:e.throwDirection?.slice()||null,releaseTime,heldAt,launchAt,releaseVelocity,releaseAngularVelocity,projectileAngularVelocity,transportVelocity:releaseVelocity,transportAngularVelocity:projectileAngularVelocity};
 return J.distanceReturn(track,t=>track.base(t).pose,clip,names,parents,settings,reference||clip.poses[0],false,track.base);
}

const api={load,model,create,accepts,labels,loadReference,referenceAt,get referenceReady(){return !!referenceData;},get data(){return data;},get assets(){return assets;}};if(node)module.exports=api;else root.BodyflipThrowAttack=api;
})(globalThis);
