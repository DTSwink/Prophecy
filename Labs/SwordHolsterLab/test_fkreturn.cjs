const assert=require('node:assert/strict'),H=require('./holster.js'),F=require('./fkreturn.js'),R=require('./recovery.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const dist=(a,b)=>R.length(R.sub(a,b)),reports=[];
for(const motion of ['idle','walk'])for(const sheathe of [false,true])for(const worldInertia of [false,true])for(const springReturn of [false,true]){
 const action=sheathe?'sheathe':'draw',m=H.prepare(data,setup,{motion,sheathe,[action+'Return']:{...F.defaults(),worldInertia,springReturn,duration:.65,inertia:.6}}),ret=m.fkReturn,start=ret.start,end=start+ret.timing.duration;
 assert.equal(start,m.plan.slideEnd/60,'starts exactly when sliding finishes');
 assert(m.completionTick/60>=end&&m.playbackDuration<8,'clamp waits for return');
 const entry=H.sampleBody(m,start),source=m.sourceFrames[m.plan.slideEnd];
 assert.deepEqual(entry.pose,source.pose,'entry pose exact');
 for(const t of [start+1e-6,start+.2,end,end+.1]){
  const f=H.sampleBody(m,t),base=H.motion(data,motion,t);
  for(let j=0;j<data.names.length;j++){
   assert(f.pose[j].p.every(Number.isFinite)&&f.pose[j].q.every(Number.isFinite),'finite');
   if(!ret.model.upper[j])assert.deepEqual(f.pose[j],base[j],'lower body remains moving baseline');
   if(t>=end)assert.deepEqual(f.pose[j],base[j],'exact moving base destination');
  }
  if(t<start+.001)for(let j=0;j<data.names.length;j++)assert(dist(f.pose[j].p,source.pose[j].p)<.01,'no entry position snap');
  if(!sheathe)assert.deepEqual(f.sword,H.compose(H.scaledGrip(setup,f.scale),f.pose[m.arm[2]]),'draw sword follows returning hand');
 }
 const curved=H.retime(m,{...m.o,[action+'Curve']:[[.2,.03],[.4,.1],[.6,.9],[.8,.97]],[action+'SlideCurve']:[[.2,.02],[.4,.1],[.6,.9],[.8,.98]]});
 assert.equal(curved.fkReturn.start,start);assert.equal(curved.fkReturn.timing.duration,ret.timing.duration,'curves do not retime return duration');
 assert.equal(H.recordedTime(curved,start+.3),start+.3,'return playback clock is unmodulated');
 if(sheathe){
  const p=m.plan,clav=m.sourceFrames[p.endTick].body.applied.slice(1);let maxError=0;
  for(let i=p.endTick;i<=p.slideEnd;i++){
   const f=m.sourceFrames[i],u=(i-p.endTick)/(p.slideEnd-p.endTick);
   for(let k=0;k<2;k++)assert(Math.abs(f.body.applied[k+1]-clav[k]*(1-u))<1e-10,'clavicle releases with insertion');
   maxError=Math.max(maxError,f.handError);
  }
  assert.deepEqual(m.sourceFrames[p.slideEnd].body.applied.slice(1),[0,0]);assert(maxError<1,'arm still follows sliding sword');
 }
 reports.push({motion,sheathe,worldInertia,springReturn,end:m.completionTick});
}
const off=H.prepare(data,setup,{sheatheReturn:{...F.defaults(),enabled:false}});assert.equal(off.fkReturn,null);
assert.notEqual(H.sanitize({}).drawReturn.boneInertia,H.sanitize({}).sheatheReturn.boneInertia);
console.log(JSON.stringify({passed:true,cases:reports},null,2));
