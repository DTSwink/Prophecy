const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js'),F=require('./fkreturn.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const distance=(a,b)=>R.length(R.sub(a,b)),curve=[[.2,.02],[.4,.1],[.6,.9],[.8,.98]];
let cases=0,maxGripError=0,maxBoneError=0,boneCase=null;
assert.equal(F.defaults().startFraction,.9);
assert.equal(F.sanitize({startFraction:-1}).startFraction,0);
assert.equal(F.sanitize({startFraction:2}).startFraction,1);
for(const motion of ['idle','walk'])for(const sheathe of [false,true])for(const gazeYaw of [0,162,-162]){
 const action=sheathe?'sheathe':'draw',source=H.prepare(data,setup,{motion,sheathe,gazeYaw,duration:15});
 const saved=JSON.stringify(source.sourceFrames),without=H.retime(source,{...source.o,[action+'Return']:{enabled:false},[action+'SlideCurve']:curve});
 for(const startFraction of [0,.5,.9,1]){
  const m=H.retime(source,{...source.o,[action+'SlideCurve']:curve,[action+'Return']:{...source.o[action+'Return'],startFraction,worldInertia:cases%2===0,springReturn:cases%3===0}}),ret=m.fkReturn,release=m.plan.slideEnd/60;
  const progress=t=>(H.recordedTime(m,t)*60-m.plan.endTick)/(m.plan.slideEnd-m.plan.endTick);
  assert(progress(ret.start)>=startFraction-1e-8);
  if(ret.start>m.plan.endTick/60)assert(progress(ret.start-1/60)<startFraction+1e-8,'first eligible playback tick');
  if(ret.start<release){
   assert.equal(m.armReturn.start,release,'gripping arm starts at full slide');
   for(let t=ret.start;t<release-1e-6;t+=1/480){
    const f=H.sampleBody(m,t),sourceFrame=H.sampleBody(without,t);
    // The sword stays on the holster path; FK guides keep the hand with it.
    assert(distance(f.sword.p,sourceFrame.sword.p)<1e-8);
    maxGripError=Math.max(maxGripError,f.handError);assert(f.handError<.6,`grip error ${motion} ${sheathe} ${gazeYaw} ${startFraction} t=${t}: ${f.handError}`);
    for(let j=0;j<data.names.length;j++)if(m.gripBranch[j]&&data.parents[j]>=0){const p=data.parents[j];const error=Math.abs(distance(f.pose[j].p,f.pose[p].p)-distance(sourceFrame.pose[j].p,sourceFrame.pose[p].p));assert(error<1e-7,'source arm lengths preserved between guide samples');if(error>maxBoneError){maxBoneError=error;boneCase={motion,sheathe,gazeYaw,startFraction,t,bone:data.names[j]};}}
   }
   assert.equal(m.sourceFrames,source.sourceFrames);
  }
  for(const boundary of [ret.start,release]){
   const a=H.sampleBody(m,boundary-1e-7),b=H.sampleBody(m,boundary+1e-7);
   for(let j=0;j<data.names.length;j++){assert(distance(a.pose[j].p,b.pose[j].p)<.001,'no boundary position pop');assert(H.angle(a.pose[j].q,b.pose[j].q)<.01,'no boundary rotation pop');}
  }
  const end=Math.max(ret.start+ret.timing.duration+(ret.gripDelay||0),m.armReturn?release+m.armReturn.timing.duration:0),f=H.sampleBody(m,end+1e-5),base=H.motion(data,motion,end+1e-5,gazeYaw);
  assert(m.completionTick/60>=end-1e-8,'completion waits for both returns');
  for(let j=0;j<data.names.length;j++){assert(distance(f.pose[j].p,base[j].p)<1e-7);assert(H.angle(f.pose[j].q,base[j].q)<1e-5);}
  cases++;
 }
 assert.equal(JSON.stringify(source.sourceFrames),saved,'return never changes source plan');
}
console.log(JSON.stringify({passed:true,cases,maxGripError,maxBoneError,boneCase}));
