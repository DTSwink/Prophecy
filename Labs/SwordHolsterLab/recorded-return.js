/* Exact captured release inputs in the normal lab transport. Only the arm
 * return is regenerated; recorded torso/head/holster remain diagnostic inputs. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery'):root.Recovery,F=typeof module!=='undefined'?require('./fkreturn'):root.FKReturn;
const local=(pose,parents)=>R.localize(pose.map(t=>t.p),pose.map(t=>t.q),parents);
function prepare(H,data,setup,options){
 const capture=data.motions[options.motion].returnCapture,{names,parents}=data,o=H.sanitize({...options,sheathe:false,sequenceMode:false}),release=capture.release,frames=capture.frames;
 const last=frames[release],previous=frames[release-1],arm=['upperarm_r','lowerarm_r','hand_r'].map(n=>names.indexOf(n)),cl=names.indexOf('clavicle_r');
 const ret=F.prepare({names,parents,last:last.pose,previous:previous.pose,base:last.base,previousBase:previous.base,dt:1/60,profile:o.drawReturn,handInertia:true});ret.start=release/60;
 const branch=names.map((_,j)=>{for(let p=j;p>=0;p=parents[p])if(p===cl)return true;return false;});
 const transplant=(pose,donor)=>{const a=local(pose,parents),b=local(donor,parents),fk=R.fk({q:a.q.map((q,j)=>branch[j]?b.q[j]:q),p:a.p.map((v,j)=>branch[j]?b.p[j]:v)},parents);return pose.map((t,j)=>branch[j]?{...t,p:fk.points[j],q:fk.q[j]}:{...t});};
 const model={o,data,setup,names,parents,arm,bladeLength:setup.bladeLength,pelvis:names.indexOf('pelvis'),returnCapture:capture,armReturn:ret,fkReturn:ret,frames:[],sourceLocals:[],tickPlayback:true,plan:{endTick:0,slideEnd:release,arrives:true},retimeSegments:{slide:{start:0,end:release/60}},tip:H.bladeTip(setup),holsterPivot:[0,0,0]};
 const end=Math.max(frames.length-1,release+Math.ceil(ret.timing.duration*60));
 for(let tick=0;tick<=end;tick++){
  const record=frames[Math.min(tick,frames.length-1)],elapsed=(tick-release)/60;let pose=record.pose.map(t=>({...t}));
  if(tick>release&&o.drawReturn.enabled){pose=transplant(pose,F.sample(ret,record.base,elapsed));pose=F.applyArmIK(ret,record.base,elapsed,pose,H.solve);pose=F.applyHandRotation(ret,record.base,elapsed,pose);}
  const active=tick<=release||elapsed<ret.timing.duration,scale=record.scale,phase=tick<=release?record.phase:active?'FK return':'Held';
  const goal=pose[arm[2]],sword=phase==='Reach'||phase==='Holstered'?H.compose(capture.seatedSword,record.holster):H.compose(H.scaledGrip(setup,scale),goal);
  model.frames.push({tick,absoluteTick:capture.firstTick+tick,pose,holster:record.holster,sword,goal,scale,insertion:record.insertion,progress:1,phase,active,blocked:false,handError:0,metrics:{unreachable:0},headLook:{done:true},fkReturn:{active:tick>release&&active,elapsed:Math.max(0,elapsed),duration:ret.timing.duration},body:{remainingDegrees:0}});
  model.sourceLocals.push(local(pose,parents));
 }
 model.completionTick=end;model.playbackDuration=end/60;
 return o.drawReturn.enabled?F.prepareSwordPoint(model,H.compose,H.scaledGrip):model;
}
function sample(H,model,t){
 const x=Math.max(0,Math.min(model.frames.length-1,t*60)),i=Math.floor(x),u=x-i,a=model.frames[i],b=model.frames[Math.min(i+1,model.frames.length-1)];if(u<1e-10)return a;
 const la=model.sourceLocals[i],lb=model.sourceLocals[Math.min(i+1,model.frames.length-1)],fk=R.fk({q:la.q.map((q,j)=>R.qslerp(q,lb.q[j],u)),p:la.p.map((p,j)=>R.offsetBlend(p,lb.p[j],u))},model.parents);
 const pose=a.pose.map((p,j)=>({...p,p:fk.points[j],q:fk.q[j]})),scale=a.scale+(b.scale-a.scale)*u;
 const holster={p:R.add(a.holster.p,R.mul(R.sub(b.holster.p,a.holster.p),u)),q:R.qslerp(a.holster.q,b.holster.q,u),s:[1,1,1]};
 const sword=a.phase==='Reach'||a.phase==='Holstered'?H.compose(model.returnCapture.seatedSword,holster):H.compose(H.scaledGrip(model.setup,scale),pose[model.arm[2]]);
 return {...a,pose,holster,scale,sword,insertion:a.insertion+(b.insertion-a.insertion)*u,absoluteTick:model.returnCapture.firstTick+x};
}
const api={prepare,sample};if(typeof module!=='undefined')module.exports=api;else root.RecordedReturn=api;
})(globalThis);
