/* Native host boundary. Shared algorithms remain in the lab modules above. */
(function(){'use strict';
const load=n=>BodyflipRequire('BodyflipLab/'+n+'.js'),R=load('recovery'),C=load('core'),F=load('flight'),A=load('attack-aim'),T=load('target-rig'),M=load('mass');
let data=null,settings=null,sequence=null,run=null,targetRig=null,rigProfileKey=null,aimPlans=new WeakMap(),releasesByTrack=new WeakMap(),catalog=null,time=0,idle=null;
const continuations=new Map();
let facingOriginal=null,facingSample=null,facingPrepared=-1;
let spaceHorizon=0;
function prepareFacing(end){
 if(!facingOriginal||end<=facingPrepared)return;
 const original=facingOriginal,yaw=R.qexp([0,settings.startYaw*Math.PI/180,0]),inverse=R.qinv(yaw),origin=original.poses[0].points[0],speed=(original.poses.at(-1).points[0][2]-origin[2])/((original.poses.length-1)/original.fps);
 const rootAt=t=>[0,origin[1],speed*t],count=Math.max(2,Math.ceil(end*30)+1),finish=(points,q)=>({points,q,axes:q.map(R.toAxes)}),translate=(p,delta)=>finish(p.points.map(v=>R.add(v,delta)),p.q);
 const source=t=>{const p=t<0?C.blend(original.poses[0],original.poses[1],t*original.fps,data.parents):F.at(original,t,data.parents);return translate(p,R.sub(rootAt(t),p.points[0]));};
 const transform=(p,q)=>finish(p.points.map(v=>R.rotate(q,v)),p.q.map(v=>R.qm(q,v)));
 const seeds=[-1/30,0].map(t=>{const p=source(t),facing=finish(p.points.map(v=>R.add(p.points[0],R.rotate(yaw,R.sub(v,p.points[0])))),p.q.map(q=>R.qm(yaw,q)));return transform(facing,inverse);});
 const predicted=resume({time:0,frames:count,seeds,roots:Array.from({length:Math.max(12,count+9)},(_,i)=>R.rotate(inverse,rootAt((i-1)/30)))});
 facingSample=t=>{const p=transform(predicted(Math.max(0,t)),yaw);return translate(p,R.sub(rootAt(t),p.points[0]));};facingPrepared=end;
}
const pose=p=>{if(!Object.prototype.hasOwnProperty.call(p,'axes'))Object.defineProperty(p,'axes',{configurable:true,enumerable:true,get(){const axes=this.q.map(R.toAxes);Object.defineProperty(this,'axes',{value:axes,writable:true,enumerable:true,configurable:true});return axes;},set(value){Object.defineProperty(this,'axes',{value,writable:true,enumerable:true,configurable:true});}});return p;};
function assets(value){data=value;if(data.schema!=='bodyflip-runtime-v1')throw Error('Bodyflip asset schema');data.reference=pose(data.reference);idle=load('idle').create(data.idleMeta,new Float32Array(data.idleValues).buffer,data);delete data.idleValues;data.jumps.forEach(c=>c.poses=c.poses.map(pose));data.attacks.forEach(c=>c.poses=c.poses.map(pose));catalog=new Map(data.attacks.map(c=>[c.meta.name,c]));load('throw-attack').load(data.throws);targetRig=null;rigProfileKey=null;return {names:data.names,parents:data.parents};}
function resume(request){
 const common={gait:settings.mode==='jump'?'run':'walk',drawn:settings.attack==='pike'||settings.attack.startsWith('slash'),names:data.names};
 const seeds=request.seeds.map(p=>({points:p.points,axes:p.axes})),key=JSON.stringify({...common,seeds});let stored=continuations.get(key);
 if(stored&&!stored.roots.slice(0,Math.min(stored.roots.length,request.roots.length)).every((p,i)=>p.every((v,k)=>Math.abs(v-request.roots[i][k])<1e-9)))stored=null;
 if(stored&&stored.clip.poses.length>=request.frames)return t=>F.at(stored.clip,Math.max(0,t-request.time),data.parents);
 let input={...common,frames:request.frames,roots:request.roots,seeds},append=null;
 if(stored?.continuation){const count=stored.clip.poses.length;append=stored;input={...common,frames:request.frames-count+1,roots:request.roots.slice(count-1),seeds:stored.clip.poses.slice(-2).map(p=>({points:p.points,axes:p.axes})),continuation:stored.continuation};while(input.roots.length<12)input.roots.push(request.roots.at(-1));}
 const result=JSON.parse(__bodyflipNN(JSON.stringify(input)));let clip=F.decodeNN(result);
 if(append){const old=append.clip;clip={...clip,poses:[...old.poses,...clip.poses.slice(1)],roots:[...old.roots,...clip.roots.slice(1)],duration:(old.poses.length+clip.poses.length-2)/clip.fps};}
 continuations.set(key,{clip,roots:request.roots,continuation:result.continuation});while(continuations.size>8)continuations.delete(continuations.keys().next().value);
 return t=>F.at(clip,Math.max(0,t-request.time),data.parents);
}
function initialize(options){
 if(!data)throw Error('Load Bodyflip authored assets first');settings=C.sanitize(options.settings||{});time=0;aimPlans=new WeakMap();releasesByTrack=new WeakMap();
 const profile=options.rigProfile||null,profileKey=JSON.stringify(profile);
 if(profileKey!==rigProfileKey){load('rig-profile').install(profile,data.names,data.parents);rigProfileKey=profileKey;targetRig=null;continuations.clear();}
 if(!targetRig){const f=R.rotate(data.reference.q[1],[0,-1,0]),base=R.qm(R.fromTo(R.unit([f[0],0,f[2]]),[0,0,1]),data.reference.q[1]),physicalReference=C.centerPose(data.reference,C.orientation(settings.flipAngle,settings.twistAngle,settings.axis,base),[0,1.5,0]);targetRig=T.create(data.names,data.parents,physicalReference);}
 const needed=new Set([settings.attack,...(settings.jumpEvents||[]).map(e=>e.attack)].filter(id=>id&&id!=='none'&&!load('throw-attack').accepts(id)));catalog=new Map([...catalog].filter(([id])=>needed.has(id)));for(const id of needed)if(!catalog.has(id)){const clip=JSON.parse(__bodyflipAttack(id));clip.poses=clip.poses.map(pose);catalog.set(id,clip);}
 if(options.run)run=options.run.poses[0].q?options.run:F.decodeNN(options.run);else if(settings.mode==='idle'||settings.mode==='spaceGym')run=idle.motion(settings.runPhase);else run=F.decodeNN(JSON.parse(__bodyflipNN(JSON.stringify({gait:settings.mode==='jump'?'run':'walk',drawn:settings.attack==='pike'||settings.attack.startsWith('slash'),phase:settings.runPhase,duration:5}))));
 run.names=data.names;run.poses=run.poses.map(pose);
 facingOriginal=null;facingSample=null;facingPrepared=-1;
 if(settings.startYaw&&['walk','jump'].includes(settings.mode)){facingOriginal=run;prepareFacing(Math.max(settings.trimOut,options.horizon||0));run={...run,facingSeeded:true,sample:t=>facingSample(t)};}
 // The live native agent enters from its held pose. Feed that transition into
 // support/attack planning itself, so predicted contacts see the same body.
 if(settings.nativeEntry){
  const original=run,entry=pose(settings.nativeEntry),origin=original.poses[0].points[0],yaw=R.qexp([0,settings.startYaw*Math.PI/180,0]);
  const seed=pose({points:entry.points.map(v=>R.add(v,origin)),q:entry.q});
  const incoming=t=>{let p=original.sample?original.sample(Math.max(0,t)):F.at(original,Math.max(0,t),data.parents);if(settings.startYaw&&!original.facingSeeded)p=pose({points:p.points.map(v=>R.add(p.points[0],R.rotate(yaw,R.sub(v,p.points[0])))),q:p.q.map(q=>R.qm(yaw,q))});return p;};
  const blended=C.transition(()=>seed,incoming,Math.max(1/60,settings.jumpBlend),data.parents,null,false,true);
  run={...original,facingSeeded:true,nativeEntry:true,sample:blended};
 }
 const horizon=settings.mode==='spaceGym'?Math.max(settings.trimOut,options.horizon||0):Math.max(1/60,options.horizon||1/60);spaceHorizon=horizon;
 sequence=F.sequence(run,data.jumps,settings,data.parents,data.reference,resume,catalog,{horizon,defer:true});sequence.prepareThrough?.(Math.max(1/60,options.horizon||1/60));return describe();
}
function describe(){const profile=load('rig-profile').current();return {time,preparedThrough:sequence?.preparedThrough||0,events:sequence?.events||[],landings:sequence?.landings||[],...(profile?{rigSchema:profile.source.schema}:{})};}
function project(p){return targetRig.project(p,sequence?.surfaces||[]);}
function aimed(t,p){
 if(sequence.sample(t).physicalAim)return project(p);
 if(!settings.aim)return project(p);const entries=(sequence.segments||[]).filter(s=>s.attack&&t>=s.attack.start);let rotation=[0,0,0,1],last=null;
 for(let i=0;i<entries.length;i++){const s=entries[i],track=s.attack;if(settings.undoRotation&&t>=track.returnEnd)continue;let plan=aimPlans.get(track);if(!plan){const sampleHit=x=>sequence.sample(x).pose,launchAt=track.launchAt?(p,transform=p=>p)=>track.launchAt(p,track.transportVelocity(x=>transform(sampleHit(x),x))):null;plan=A.create({clip:catalog.get(s.event.attack),track,names:data.names,parents:data.parents,reference:data.reference,sampleHit,launchAt,project});aimPlans.set(track,plan);}if(settings.undoRotation)return project(plan.apply(p,t,settings.target,settings.aimWeight));rotation=plan.rotation(Math.min(t,entries[i+1]?.attack.start??t),settings.target,settings.aimWeight,false,rotation);last=plan;}
 return project(last?last.applyRotation(p,rotation):p);
}
function prepare(end){const previous=sequence,through=sequence?.preparedThrough||0;prepareFacing(end);if(settings.mode==='spaceGym'&&end>spaceHorizon){spaceHorizon=end;sequence=F.sequence(run,data.jumps,settings,data.parents,data.reference,resume,catalog,{horizon:end});aimPlans=new WeakMap();}sequence.prepareThrough?.(end);if(sequence!==previous||(sequence?.preparedThrough||0)>through)releasesByTrack=new WeakMap();return describe();}
function releaseAt(track){
 let launch=releasesByTrack.get(track);
 if(!launch){const at=x=>aimed(x,sequence.sample(x).pose);launch=structuredClone(track.launchAt(at(track.releaseTime),track.transportVelocity(at),track.transportAngularVelocity(at)));releasesByTrack.set(track,launch);}
 // The launch is immutable; the caller owns its packet and the elapsed remainder.
 return structuredClone(launch);
}
function sample(t){time=Math.max(0,t);prepare(time);const frame=sequence.sample(time),p=aimed(time,frame.pose),releases=[],held=[];
 for(const s of sequence.segments||[]){const a=s.attack;if(!a?.isThrow)continue;if(time>=a.start&&time<a.releaseTime)held.push({...a.heldAt(p),id:s.event.id});if(time>=a.releaseTime)releases.push({...releaseAt(a),id:s.event.id,releaseRemainderSeconds:Math.max(0,time-a.releaseTime)});}
 return {time,pose:{points:p.points,q:p.q},...(settings.traceSource?{sourcePose:{points:frame.pose.points,q:frame.pose.q},supportState:frame.supportState??null}:{}),root:frame.root||p.points[0],phase:frame.phase,velocity:frame.velocity||[0,frame.vy||0,frame.speed||0],spin:frame.spin?{rotation:frame.spin.rotation,flipRate:frame.spin.flipRate,twistRate:frame.spin.twistRate}:null,grounded:!!frame.capsule?.grounded,heading:frame.capsule?.yaw??settings.startYaw*Math.PI/180,events:sequence.events,releases,held,zeroGravity:settings.mode==='spaceGym'};
}
function command(input){switch(input.op){case'assets':return assets(input.value);case'start':return initialize(input);case'sample':return sample(input.time);case'target':settings.target=input.target;aimPlans=new WeakMap();releasesByTrack=new WeakMap();if(sequence?.segments.some(s=>s.spin?.active))sequence=F.sequence(run,data.jumps,settings,data.parents,data.reference,resume,catalog,{horizon:Math.max(time,sequence.preparedThrough),defer:true});return describe();case'prepare':return prepare(input.time);case'state':return describe();default:throw Error('Unknown Bodyflip command '+input.op);}}
globalThis.BodyflipNative={command:json=>JSON.stringify(command(JSON.parse(json))),raw:command};
})();
