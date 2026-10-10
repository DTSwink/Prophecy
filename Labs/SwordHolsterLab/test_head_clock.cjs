const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const curve=[[.2,.01],[.45,.05],[.65,.93],[.85,.99]],head=data.names.indexOf('head');
for(const sheathe of [false,true])for(const exponent of [1,3]){
 const a=sheathe?'sheathe':'draw',m=H.prepare(data,setup,{sheathe,motion:'walk',headLookInExponent:exponent,headLookOutExponent:exponent,maxHeadLookInVelocity:30,maxHeadLookOutVelocity:40,[a+'Curve']:curve,[a+'SlideCurve']:curve});
 let peakSourceRate=0;
 for(let i=m.o.startTick+1;i<m.frames.length;i++){
  const f=m.frames[i],previous=m.frames[i-1],cap=f.headLook.speedLimit/60;
  assert(H.angle(previous.pose[head].q,f.pose[head].q)<=cap+.001,'head rate independent of time warp');
  peakSourceRate=Math.max(peakSourceRate,(H.recordedTime(m,i/60)-H.recordedTime(m,(i-1)/60))*60);
 }
 assert(peakSourceRate>3,'test actually accelerates the source');
 const out=m.frames.find(f=>['Look out','Forward'].includes(f.headLook.mode)),threshold=sheathe?.5:.3;
 const progress=t=>(H.recordedTime(m,t)*60-m.plan.endTick)/(m.plan.slideEnd-m.plan.endTick);
 assert(progress(out.tick/60)>=threshold-1e-8&&progress((out.tick-1)/60)<threshold,'threshold follows actual slide progress');
 for(let t=(m.o.startTick+2)/60;t<m.playbackDuration-.01;t+=.031){
  const a=H.sample(m,t),b=H.sample(m,t+.001);
  assert(H.angle(a.pose[head].q,b.pose[head].q)<=40*.001+.001,'fractional head velocity');
 }
 const changed=H.retime(m,{...m.o,[a+'SlideCurve']:[[.2,.2],[.4,.4],[.6,.6],[.8,.8]]});
 assert.equal(changed.sourceFrames,m.sourceFrames,'curve edits reuse body/arm trajectory');
}
console.log('PASS: head angular limits on playback clock despite >3x reach/slide speed; fractional samples, slide threshold timing and curve-edit body reuse.');
