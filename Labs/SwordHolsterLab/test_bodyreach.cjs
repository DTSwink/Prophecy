const assert=require('node:assert/strict'),H=require('./holster.js'),B=require('./bodyreach.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const dist=(a,b)=>R.length(R.sub(a,b)),nearQ=(a,b,label)=>assert(H.angle(a,b)<1e-5,label),nearV=(a,b,label)=>assert(dist(a,b)<1e-7,label);
const ctx=B.make(data,H.motion(data,'idle',0)),profile=B.sanitize();
profile.clear.left=[12,-8,6];profile.seated.left=[-5,4,10];
const frozen=JSON.stringify(profile);let poseCases=0;
for(const motion of ['idle','walk'])for(const gaze of [-170,0,170])for(const insertion of [0,.25,.5,.75,1]){
 const base=H.motion(data,motion,1.31,gaze),target=B.target(ctx,profile,insertion),pose=B.apply(ctx,base,target);
 for(let k=0;k<3;k++)nearQ(R.qm(R.qinv(pose[ctx.anchors[k]].q),pose[ctx.bones[k]].q),target.slice(k*4,k*4+4),'exact parent-relative authored target');
 const delta=R.qm(pose[ctx.top].q,R.qinv(base[ctx.top].q));
 for(const [k,j] of ctx.spine.entries())nearQ(pose[j].q,R.qm(R.qslerp([0,0,0,1],delta,(k+1)/5),base[j].q),'weighted addition preserves base spine movement');
 for(let j=0;j<data.names.length;j++){
  if(!ctx.affected.includes(j))assert.deepEqual(pose[j],base[j],'pelvis and lower body untouched');
  const p=data.parents[j];if(p>=0)assert(Math.abs(dist(pose[j].p,pose[p].p)-dist(base[j].p,base[p].p))<1e-7,'segment lengths');
 }
 const rotation=R.qexp([.3,-.5,1.2]),translation=[10,20,30];
 const moved=base.map(v=>({...v,p:R.add(translation,R.rotate(rotation,v.p)),q:R.qm(rotation,v.q)})),out=B.apply(ctx,moved,target);
 for(let j=0;j<pose.length;j++){nearV(out[j].p,R.add(translation,R.rotate(rotation,pose[j].p)),'rigid frame invariance');nearQ(out[j].q,R.qm(rotation,pose[j].q),'rotated frame invariance');}
 poseCases++;
}
assert.equal(JSON.stringify(profile),frozen,'sampling does not mutate saved targets');
const saved=H.sanitize({bodyTargets:profile}),restored=H.sanitize(JSON.parse(JSON.stringify(saved)));
assert.deepEqual(restored.bodyTargets,profile);restored.bodyTargets.clear.left[0]=99;assert.equal(saved.bodyTargets.clear.left[0],12,'independent saved profiles');
let motionCases=0,maxGrip=0;
for(const motion of ['idle','walk'])for(const sheathe of [false,true]){
 const action=sheathe?'sheathe':'draw',m=H.prepare(data,setup,{motion,sheathe,bodyTargets:profile,[action+'Return']:{enabled:false},duration:10});
 assert(m.plan.arrives&&m.completionTick!==null,'D/S completes');
 for(let tick=m.o.startTick+1;tick<=m.plan.endTick;tick++)assert(B.remaining(m.sourceFrames[tick-1].body.applied,m.sourceFrames[tick].body.applied)<=m.o.maxSpineClavicleAngularSpeed/60+1e-5,'reach turn respects cap');
 nearQ(m.sourceFrames[m.o.startTick].pose[ctx.top].q,H.motion(data,motion,m.o.startTick/60)[ctx.top].q,'no entry snap');
 for(let tick=m.plan.endTick;tick<=m.plan.slideEnd;tick+=.37){
  const f=H.sampleBody(m,tick/60),expected=B.target(ctx,profile,f.insertion);
  for(let k=0;k<3;k++)nearQ(R.qm(R.qinv(f.pose[ctx.anchors[k]].q),f.pose[ctx.bones[k]].q),expected.slice(k*4,k*4+4),'fractional insertion matches authored interpolation');
  maxGrip=Math.max(maxGrip,f.handError);assert(f.handError<1,'fractional sword grip');
 }
 for(const insertion of [0,1]){
  const f=H.previewBody(m,insertion),expected=B.target(ctx,profile,insertion);
  for(let k=0;k<3;k++)nearQ(R.qm(R.qinv(f.pose[ctx.anchors[k]].q),f.pose[ctx.bones[k]].q),expected.slice(k*4,k*4+4),'preview has exact authored rotations');
 }
 const early=H.retime(m,{...m.o,[action+'Return']:{enabled:true,startFraction:.5}});
 assert(early.fkReturn.start<early.plan.slideEnd/60,'early return retained');assert.equal(early.armReturn.start,early.plan.slideEnd/60,'arm waits until release');
 const t=(early.fkReturn.start+early.armReturn.start)/2,returning=H.sampleBody(early,t),authored=H.sampleBody(m,t);
 assert(H.angle(returning.pose[ctx.top].q,authored.pose[ctx.top].q)>.1,'spine returns before release');
 assert(H.angle(returning.pose[ctx.left].q,authored.pose[ctx.left].q)>.1,'left clavicle returns before release');
 assert(returning.fkReturn.gripping&&returning.handError<1,'right arm stays gripping');
 motionCases++;
}
console.log(JSON.stringify({passed:true,poseCases,motionCases,maxGrip}));
