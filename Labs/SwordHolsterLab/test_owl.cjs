const {assertHeadBudget}=require('./head-test-helpers.cjs');
const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),fixture=require('./data/owl-regression.json');
const reports=[];
for(const motion of ['idle','walk'])for(const sheathe of [true,false])for(const gazeYaw of [170,-170,0]){
 const m=H.prepare(data,setup,{...fixture,motion,sheathe,gazeYaw}),ctx=m.headContext;
 let maxCorrection=0,maxNeckStep=0;
 assert(m.completionTick!==null,'unrestricted gaze return completes');
 for(let tick=0;tick<m.completionTick;tick+=.25){
  const f=H.sample(m,tick/60),next=H.sample(m,(tick+.25)/60);
  assert(f.pose[ctx.head].q.every(Number.isFinite),'finite fractional head rotation');
  if(tick>m.o.startTick)assert(H.angle(f.pose[ctx.head].q,next.pose[ctx.head].q)<=Math.max(m.o.maxHeadLookInVelocity,m.o.maxHeadLookInVelocityAtMaxGaze,m.o.maxHeadLookOutVelocity,m.o.maxHeadLookOutVelocityAtMaxGaze)/240+.001,'fractional speed cap');
  if(tick<=m.o.startTick)assert.deepEqual(f.pose,H.sampleBody(m,tick/60).pose,'pre-action pose remains exactly authored, including fractional playback');
 }
 for(let i=0;i<m.frames.length;i++){
  maxCorrection=Math.max(maxCorrection,R.length(m.headTrack[i].correction)*180/Math.PI);
  assert(R.length(m.headTrack[i].correction)<Math.PI,'fixture has no extra full-turn neck winding');
  const f=m.frames[i],body=H.sampleBody(m,i/60);
  for(let j=0;j<data.names.length;j++)if(!ctx.chain.includes(j))assert.deepEqual(f.pose[j],body.pose[j],'head authoring leaves body and arms untouched');
  if(i)for(const j of ctx.chain)maxNeckStep=Math.max(maxNeckStep,H.angle(f.pose[j].q,m.frames[i-1].pose[j].q));
  if(i>fixture.startTick)assertHeadBudget(m,i);
 }
 assert(maxNeckStep<5,'no neck flip');
 const last=m.frames.at(-1),target=H.motion(data,motion,m.playbackDuration,gazeYaw);
 for(const j of ctx.chain){
  assert(H.angle(last.pose[j].q,target[j].q)<.001,'full NN neck orientation restored at completion');
  assert(R.length(R.sub(last.pose[j].p,target[j].p))<.0001,'full NN neck/head position restored at completion');
 }
 reports.push({motion,sheathe,gazeYaw,completion:m.completionTick,maxCorrection,maxNeckStep});
}
console.log(JSON.stringify({passed:true,reports},null,2));
