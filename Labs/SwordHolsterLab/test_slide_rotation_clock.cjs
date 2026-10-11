const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const H=require('./holster.js'),R=require('./recovery.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),fixture=require('./data/owl-regression.json');
const curves=[[[.2,.01],[.4,.05],[.6,.9],[.8,.99]],[[.2,.8],[.4,.9],[.6,.98],[.8,.99]],[[.2,0],[.4,0],[.6,.1],[.8,.7]]];
const dist=(a,b)=>R.length(R.sub(a,b));let cases=0,maxGripError=0,maxAngleError=0;
for(const motion of ['idle','walk'])for(const gazeYaw of [0,170])for(const alpha of [0,.25,1]){
 const original=H.prepare(data,setup,{...fixture,motion,gazeYaw,slideRotationCorrection:alpha,sheatheSlideCurve:[[.2,.2],[.4,.4],[.6,.6],[.8,.8]],sheatheReturn:{enabled:false}});
 assert.equal(original.slideGuides,null,'linear sliding keeps the original FK guides');
 for(const curve of curves){
  const m=H.retime(original,{...original.o,sheatheSlideCurve:curve,sheatheReturn:{...fixture.sheatheReturn,startFraction:[0,.9,1][cases%3]}}),p=m.plan;
  assert.equal(m.sourceFrames,original.sourceFrames,'reach/source planning is reused');
  assert(m.slideGuides,'fixture exercises separate-clock arm guides');
  const initial=H.angle(m.sheathEntry.q,[0,0,0,1]);
  for(let tick=p.endTick;tick<=p.slideEnd;tick+=.125){
   const t=tick/60,u=(tick-p.endTick)/(p.slideEnd-p.endTick),f=H.sampleBody(m,t),full=H.compose(setup.seated,f.holster);
   const expected=initial*(1-(alpha>0?Math.min(1,u/alpha):u>0?1:0));
   const error=Math.abs(H.angle(f.sword.q,full.q)-expected);maxAngleError=Math.max(maxAngleError,error);
   assert(error<.0001,'rotation depends only on elapsed slide time');
   const old=H.sampleBody(original,H.recordedTime(m,t));
   const localTip=v=>R.rotate(R.qinv(v.holster.q),R.sub(H.point(v.sword,m.tip),v.holster.p));
   assert(dist(localTip(f),localTip(old))<1e-7,'holster-local tip insertion keeps the curve');
   assert.equal(f.scale,old.scale,'residual shrink keeps the existing insertion clock');
   maxGripError=Math.max(maxGripError,f.handError);assert(f.handError<1,`FK grip ${motion} gaze=${gazeYaw} alpha=${alpha} curve=${cases%3} tick=${tick} return=${m.fkReturn.start*60}: ${f.handError}`);
   for(const j of m.arm.slice(1)){const parent=m.parents[j],base=H.motion(data,motion,t,gazeYaw);assert(Math.abs(dist(f.pose[j].p,f.pose[parent].p)-dist(base[j].p,base[parent].p))<1e-7,'bone lengths preserved');}
  }
  const cutoff=(p.endTick+(p.slideEnd-p.endTick)*alpha)/60;
  if(alpha>0){const f=H.sampleBody(m,cutoff);assert(H.angle(f.sword.q,H.compose(setup.seated,f.holster).q)<1e-5,'exact time cutoff, including fractional ticks');}
  for(const time of [p.endTick/60,p.slideEnd/60,m.fkReturn.start]){
   if(alpha===0&&time===p.endTick/60)continue; // explicit immediate correction
   const a=H.sampleBody(m,time-1e-7),b=H.sampleBody(m,time+1e-7);
   for(const j of m.arm){assert(dist(a.pose[j].p,b.pose[j].p)<.001,'no arm position pop at entry/return/release');assert(H.angle(a.pose[j].q,b.pose[j].q)<.01,'no arm rotation pop at entry/return/release');}
  }
  const headEdit=H.retime(m,{...m.o,headLookAtAlpha:.4});assert.equal(headEdit.slideGuides,m.slideGuides,'head edits reuse prepared slide guides');
  cases++;
 }
}
// Instrument the private planning solve; both actions prepare moving-holster guides,
// and neither ordinary nor fractional playback may run a solve.
const context={module:{exports:{}},require,solves:0};vm.createContext(context);
vm.runInContext(fs.readFileSync(require.resolve('./holster.js'),'utf8').replace('function solve(pose,idx,goal){','function solve(pose,idx,goal){solves++;'),context);
const instrumented=context.module.exports,m=instrumented.prepare(data,setup,{...fixture,sheatheSlideCurve:curves[0]}),count=context.solves;
for(let t=0;t<m.playbackDuration;t+=.007)instrumented.sample(m,t);
assert.equal(context.solves,count,'playback performs no IK');
const draw=H.prepare(data,setup,{...fixture,sheathe:false,drawSlideCurve:curves[0]});assert(draw.slideGuides,'drawing follows steady locomotion too');
const held=H.retime(m,{...m.o,sheatheReturn:{enabled:false}}),release=held.plan.slideEnd/60;
for(const j of held.arm){const a=H.sampleBody(held,release-1e-7).pose[j],b=H.sampleBody(held,release+1e-7).pose[j];assert(dist(a.p,b.p)<.001&&H.angle(a.q,b.q)<.01,'disabled return retains the final new arm pose');}
const truncated=H.prepare(data,setup,{...m.o,duration:(m.plan.endTick+5)/60,sheatheReturn:{enabled:false}});
for(let t=0;t<=truncated.playbackDuration;t+=.013)for(const p of H.sampleBody(truncated,t).pose)assert([...p.p,...p.q].every(Number.isFinite),'truncated slide remains finite');
console.log(JSON.stringify({passed:true,cases,maxGripError,maxAngleError,noPlaybackSolves:true}));
