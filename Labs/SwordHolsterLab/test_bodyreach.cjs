const assert=require('node:assert/strict'),H=require('./holster.js'),B=require('./bodyreach.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const dist=(a,b)=>R.length(R.sub(a,b)),nearQ=(a,b,label)=>assert(R.length(R.qlog(R.qm(a,R.qinv(b))))<1e-7,label),nearV=(a,b,label)=>assert(dist(a,b)<1e-7,label);
const entry=H.motion(data,'run',70/60),ctx=B.make(data,H.motion(data,'idle',0),entry),profile=B.sanitize(saved.bodyTargets);
profile.clear.left=[12,-8,6];profile.seated.left=[-5,4,10];
const relative=(pose,j,anchor)=>R.qm(R.qinv(pose[anchor].q),pose[j].q),pelvisPoint=(pose,j)=>R.rotate(R.qinv(pose[ctx.pelvis].q),R.sub(pose[j].p,pose[ctx.pelvis].p));
const unchanged=JSON.stringify(profile);let poseCases=0;
for(const motion of ['idle','walk','run'])for(const gaze of [-170,0,170])for(const insertion of [0,.5,1]){
 const base=H.motion(data,motion,1.83,gaze),target=B.target(ctx,profile,insertion),pose=B.apply(ctx,base,target),reference=B.apply(ctx,entry.map((v,j)=>j===ctx.pelvis?base[j]:v),target);
 nearQ(pose[ctx.top].q,R.qm(ctx.entryPelvisQ,target.slice(0,4)),'spine target cancels current pelvis rotation');
 nearQ(relative(pose,ctx.clav,ctx.top),target.slice(4,8),'right clavicle target is absolute in spine05');
 for(const j of ctx.driven){nearQ(relative(pose,j,ctx.pelvis),relative(reference,j,ctx.pelvis),'driven rotations ignore future gait');nearV(pelvisPoint(pose,j),pelvisPoint(reference,j),'driven positions ignore future gait');}
 const left=data.names.indexOf('clavicle_l'),leftDelta=R.qm(target.slice(8,12),R.qinv(ctx.reference[2]));
 for(const name of ['clavicle_l','upperarm_l','lowerarm_l','hand_l']){
  const j=data.names.indexOf(name),p=data.parents[j];nearQ(relative(pose,j,p),j===left?R.qm(leftDelta,relative(base,j,p)):relative(base,j,p),'left local animation retained');
  nearV(R.rotate(R.qinv(pose[p].q),R.sub(pose[j].p,pose[p].p)),R.rotate(R.qinv(base[p].q),R.sub(base[j].p,base[p].p)),'left local offsets retained');
 }
 for(const j of ctx.affected){const p=data.parents[j];assert(Math.abs(dist(pose[j].p,pose[p].p)-dist((ctx.driven.has(j)?entry:base)[j].p,(ctx.driven.has(j)?entry:base)[p].p))<1e-7,'captured/live lengths retained');}
 for(let j=0;j<base.length;j++)if(!ctx.affected.includes(j))assert.deepEqual(pose[j],base[j],'pelvis/legs unchanged');
 const q=R.qexp([.3,-.7,1.1]),offset=[32,-4,11],moved=base.map(v=>({...v,p:R.add(offset,R.rotate(q,v.p)),q:R.qm(q,v.q)})),movedEntry=entry.map(v=>({...v,p:R.add(offset,R.rotate(q,v.p)),q:R.qm(q,v.q)})),out=B.apply(B.make(data,H.motion(data,'idle',0),movedEntry),moved,target);
 for(let j=0;j<pose.length;j++){nearV(out[j].p,R.add(offset,R.rotate(q,pose[j].p)),'rigid frame position invariance');nearQ(out[j].q,R.qm(q,pose[j].q),'rigid frame rotation invariance');}poseCases++;
}
const initial=B.apply(ctx,entry,ctx.entryBody);for(let j=0;j<entry.length;j++){nearV(initial[j].p,entry[j].p,'captured entry position');nearQ(initial[j].q,entry[j].q,'captured entry rotation');}
assert.equal(JSON.stringify(profile),unchanged);
let motionCases=0,maxGrip=0,maxEntryStep=0;
for(const motion of ['idle','walk','run'])for(const sheathe of [false,true]){
 const action=sheathe?'sheathe':'draw',m=H.prepare(data,setup,{...saved,motion,sheathe,duration:12,[action+'Return']:{enabled:false}});
 assert(m.plan.arrives&&m.completionTick!==null,'D/S completes');
 for(let tick=m.o.startTick+1;tick<=m.plan.endTick;tick++)assert(B.remaining(m.sourceFrames[tick-1].body.applied,m.sourceFrames[tick].body.applied)<=m.o.maxSpineClavicleAngularSpeed/60+1e-5,'reach cap');
 const at=m.o.startTick/60,a=H.sampleBody(m,at-1e-7),b=H.sampleBody(m,at+1e-7);
 for(const j of m.bodyContext.affected){maxEntryStep=Math.max(maxEntryStep,dist(a.pose[j].p,b.pose[j].p));assert(dist(a.pose[j].p,b.pose[j].p)<.001,'no entry snap');}
 for(let tick=m.plan.endTick;tick<m.plan.slideEnd;tick+=.37){const f=H.sampleBody(m,tick/60),target=B.target(m.bodyContext,m.o.bodyTargets,f.insertion);nearQ(f.pose[ctx.top].q,R.qm(m.bodyContext.entryPelvisQ,target.slice(0,4)),'fractional counterrotated spine target');maxGrip=Math.max(maxGrip,f.handError);assert(f.handError<.3,'slide grip');}
 for(const insertion of [0,1]){const f=H.previewBody(m,insertion);assert.deepEqual(f.pose,H.sample(m,f.previewTime).pose,'preview matches playback');}
 const early=H.retime(m,{...m.o,[action+'Return']:{...saved[action+'Return'],enabled:true,startFraction:.7}});assert(early.fkReturn.start<early.plan.slideEnd/60,'early return retained');assert.equal(early.armReturn.start,early.plan.slideEnd/60,'arm remains held until release');
 const t=(early.fkReturn.start+early.armReturn.start)/2,f=H.sampleBody(early,t);assert(f.fkReturn.gripping&&f.handError<.3,'early return retains grip');
 motionCases++;
}
console.log(JSON.stringify({passed:true,poseCases,motionCases,maxGrip,maxEntryStep}));
