// Independent lab math oracle; no writes to live settings or assets.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),lab=path.join(root,'Labs/SwordHolsterLab'),out=path.join(root,'Saved/Diagnostics/SwordPort20261012');
const H=require(path.join(lab,'holster.js')),B=require(path.join(lab,'bodyreach.js')),P=require(path.join(lab,'elbowpole.js')),R=require(path.join(lab,'recovery.js')),FK=require(path.join(lab,'armfk.js'));
const data=require(path.join(lab,'data/motions.json')),setup=require(path.join(lab,'data/unreal-setup.json'));
const saved=JSON.parse(fs.readFileSync(process.argv[2]?path.resolve(process.argv[2]):path.join(lab,'state.json'),'utf8')),p=structuredClone(saved.parameters);
const runtime=JSON.parse(fs.readFileSync(path.join(root,'Content/locomotion/SwordHolsterProfile.json'),'utf8'));
if(require('node:crypto').createHash('sha256').update(JSON.stringify(saved.parameters)).digest('hex')!==runtime.sourceHash)throw Error('Lab state and exported native profile differ; select the matching saved state or intentionally sync the profile first.');
if(saved.controls?.bypassCurves)for(const key of ['drawCurve','drawSlideCurve','sheatheCurve','sheatheSlideCurve'])p[key]=require(path.join(lab,'retime.js')).linear();
const arm=['upperarm_r','lowerarm_r','hand_r'].map(n=>data.names.indexOf(n)),top=data.names.indexOf('spine_05');
const reference=H.motion(data,'idle',0),body=[],pole=[],inertia=[],motions=[];
for(const motion of ['idle','walk','run'])for(const sheathe of [false,true]){
 const action=sheathe?'sheathe':'draw',v={...p,...p[action+'Body'],motion,sheathe,holsterRotationStabilization:0};
 const entry=H.motion(data,motion,v.startTick/60),ctx=B.make(data,reference,entry,v.pelvisRotationCompensation);
 for(const compensation of [0,.96,1])for(const insertion of [0,.37,1]){
  const c=B.make(data,reference,entry,compensation),base=H.motion(data,motion,v.startTick/60+.317),target=B.target(c,v.bodyTargets,insertion);
  body.push({sheathe,compensation,insertion,entry,base,target,expected:B.apply(c,base,target)});
 }
 // Pole transport uses the same input poses on both sides; includes sword transfer.
 const frames=[];let basis=null,angle=0,swordDown=null,reachSpeed=0;const ticks=30;
 for(let tick=0;tick<=80;tick++){
  const base=H.motion(data,motion,v.startTick/60+tick/60),insertion=sheathe?Math.max(0,(tick-ticks)/50):1-Math.max(0,(tick-ticks)/50);
  const target=B.target(ctx,v.bodyTargets,tick<=ticks?(sheathe?0:1):insertion),pose=B.apply(ctx,base,B.blend(ctx.entryBody,target,Math.min(1,tick/ticks)));
  let ref=top;const swordQ=R.qm(pose[arm[2]].q,setup.grip.q);
  const previousAngle=angle;if(tick>0)angle=P.advance(angle,P.target(v.bodyTargets,insertion),tick<=ticks?reachSpeed:v.maxElbowPoleAngularSpeed,1/60);
  const budget=Math.max(0,v.maxElbowPoleAngularSpeed/60-Math.abs(angle-previousAngle));
  if(tick>ticks){if(!swordDown){basis=P.frame(pose,arm,top,basis,budget);const q=R.qm(R.qinv(swordQ),pose[top].q);basis={d:R.rotate(q,basis.d),zero:R.rotate(q,basis.zero)};swordDown=basis.zero;}ref={q:swordQ,down:swordDown};}
  basis=P.frame(pose,arm,ref,basis,budget);
  if(tick===0){angle=P.measure(pose,arm,ref,basis);reachSpeed=Math.min(v.maxElbowPoleAngularSpeed,Math.abs(P.wrap(P.target(v.bodyTargets,sheathe?0:1)-angle))*60/ticks);}
  frames.push({pose,angle,expected:P.apply(pose,arm,ref,angle,basis)});
 }
 pole.push({sheathe,frames});
 const model=H.prepare(data,setup,v),off={...model,entryInertia:null},start=v.startTick/60,dt=1e-4;
 const before=H.motion(data,motion,start-dt),first=H.sampleBody(off,start).pose,next=H.sampleBody(off,start+dt).pose;
 const samples=[];for(let tick=1;tick<Math.min(model.entryInertia.duration*60,model.plan.endTick-v.startTick);tick++)samples.push({tick,pose:H.sampleBody(off,start+tick/60).pose,expected:H.sampleBody(model,start+tick/60).pose});
 inertia.push({sheathe,before,first,next,reachTicks:model.plan.endTick-v.startTick,samples});
 motions.push({motion,sheathe,entry,reachTicks:model.plan.reachEndTick-v.startTick,slideStart:model.plan.endTick-v.startTick,slideTicks:model.plan.slideEnd-model.plan.endTick,
  frames:Array.from({length:360},(_,tick)=>{const time=start+tick/60,base=H.motion(data,motion,time),holster=H.compose(setup.holster,base[ctx.pelvis]),full=H.seatedSword(setup,holster),f=H.sample(model,time),pole=model.poleGuides.keys[Math.min(tick*4,model.poleGuides.keys.length-1)];return {base,full,pose:f.pose,phase:f.phase,insertion:f.insertion,pole:{angle:pole.angle,zero:pole.basis.zero,direction:pole.basis.d}};})});
}
const straight=require(path.join(lab,'data/straight-arm-regression.json')).cases.map(c=>{const pose=structuredClone(c.input);H.solve(pose,[1,2,3],c.goal);return {...c,expected:P.apply(pose,[1,2,3],4,c.angle,P.frame(pose,[1,2,3],4,c.basis))};});
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'authored-oracle.json'),JSON.stringify({names:data.names,parents:data.parents,setup:{grip:setup.grip,assetScale:setup.assetScale,baseBladeLocal:setup.baseBladeLocal,tip:H.bladeTip(setup),bladeLength:setup.bladeLength},body,pole,inertia,motions,straight}));
console.log({body:body.length,pole:pole.length,inertia:inertia.length,motions:motions.map(m=>({motion:m.motion,sheathe:m.sheathe,reach:m.reachTicks,slideStart:m.slideStart,slide:m.slideTicks}))});
