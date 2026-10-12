const assert=require('node:assert/strict'),H=require('./holster.js'),P=require('./sequence.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const qerror=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),distance=(a,b)=>R.length(R.sub(a,b));
let cases=0,maxRotationError=0,maxPositionError=0,maxSwordError=0;
assert.equal(H.sanitize({}).holsterRotationStabilization,0);
assert.equal(H.sanitize({holsterRotationStabilization:9}).holsterRotationStabilization,1);
assert.equal(H.sanitize({holsterRotationStabilization:-1}).holsterRotationStabilization,0);
for(const motion of ['idle','walk','run'])for(const alpha of [0,.5,1]){
 const o={...saved,motion,sequenceMode:true,duration:12,holsterRotationStabilization:alpha};
 const m=P.prepare(data,setup,o);assert(m.sequence.second,'both actions are planned');
 if(alpha===0){
  const changed={...o,holsterRotationStabilization:.5};
  assert.deepEqual(P.retime(m,changed).frames,P.prepare(data,setup,changed).frames,'retime during an outstanding slider edit replans the changed path');
 }
 for(const part of [m.sequence.first,m.sequence.second]){
  const reference=H.compose(part.holsterLocal,H.motion(data,motion,0,o.gazeYaw)[part.pelvis]);
  const times=[...part.sourceFrames.map(f=>f.tick/60).filter(t=>t<=part.playbackDuration)];
  // Reverse-order fractional scrubbing checks that stabilization has no state or curved clock.
  for(let t=part.playbackDuration;t>=0;t-=.037)times.push(t);
  for(const t of times){
   const f=H.sample(part,t),base=H.motion(data,motion,part.motionOffset+t,o.gazeYaw),attached=H.compose(part.holsterLocal,base[part.pelvis]);
   const expected=R.qslerp(attached.q,reference.q,alpha),q=qerror(f.holster.q,expected),p=distance(f.holster.p,attached.p);
   maxRotationError=Math.max(maxRotationError,q);maxPositionError=Math.max(maxPositionError,p);
   assert(q<1e-7&&p<1e-7,JSON.stringify({motion,alpha,sheathe:part.o.sheathe,t,q,p}));
   if(f.phase==='Holstered'||f.phase==='Reach'&&!part.o.sheathe){
    const full=H.seatedSword(setup,f.holster),seat=H.seatHandAtScale(setup,full,1-o.shrinkPercent/100);
    const sword=H.compose(H.scaledGrip(setup,1-o.shrinkPercent/100),seat);
    maxSwordError=Math.max(maxSwordError,distance(f.sword.p,sword.p));
    // Fractional source poses retain the existing sub-millimetre interpolation error.
    assert(distance(f.sword.p,sword.p)<.01&&qerror(f.sword.q,sword.q)<1e-7,JSON.stringify({motion,alpha,sheathe:part.o.sheathe,t,phase:f.phase,p:distance(f.sword.p,sword.p),q:qerror(f.sword.q,sword.q)}));
   }
  }
 }
 const end=H.sample(m.sequence.first,m.sequence.offset),start=H.sample(m.sequence.second,0);
 for(const key of ['holster','sword'])assert(distance(end[key].p,start[key].p)<1e-7&&qerror(end[key].q,start[key].q)<1e-7,'no re-anchor at S to D');
 cases++;
}
console.log(JSON.stringify({passed:true,cases,maxRotationError,maxPositionError,maxSwordError}));
