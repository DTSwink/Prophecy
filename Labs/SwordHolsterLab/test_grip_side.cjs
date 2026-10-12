const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js');
const setup=require('./data/unreal-setup.json'),data=require('./data/motions.json');
const original=JSON.stringify(setup),distance=(a,b)=>R.length(R.sub(a,b));
// A half roll reverses transverse hand axes without reversing the blade/thumb
// direction or relocating the authored entrance. No scale is applied twice.
for(const spin of [[0,0,0,1],R.qexp([.3,-.7,1.1])]){
 const holster={...setup.holster,q:R.qm(spin,setup.holster.q)};
 const old=H.compose(setup.seated,holster),seat=H.seatedSword(setup,holster);
 assert(Math.abs(H.angle(old.q,seat.q)-180)<1e-5);
 assert(distance(R.rotate(old.q,[0,0,1]),R.rotate(seat.q,[0,0,1]))<1e-10);
 assert(distance(H.point(old,setup.baseBladeLocal),H.point(seat,setup.baseBladeLocal))<1e-10);
 assert.deepEqual(seat.s,old.s);
 for(const scale of [1,.85,.65,.3]){
  const before=H.seatHandAtScale(setup,old,scale),after=H.seatHandAtScale(setup,seat,scale);
  assert(Math.abs(H.angle(before.q,after.q)-180)<1e-5);
  const blade=H.compose(H.scaledGrip(setup,scale),after);
  assert(H.angle(blade.q,seat.q)<1e-5);
  assert(distance(H.point(blade,setup.baseBladeLocal),H.point(old,setup.baseBladeLocal))<1e-8);
 }
}
let cases=0,maxGrip=0;
for(const motion of ['idle','walk'])for(const sheathe of [false,true])for(const gazeYaw of [-24,0,162]){
 const m=H.prepare(data,setup,{motion,sheathe,gazeYaw,duration:12,maxReachSpeed:230,maxReachRotationSpeed:600,slidingSpeed:150,shrinkPercent:15,maxSpineClavicleAngularSpeed:1000});
 assert(m.completionTick!==null,`${motion} S=${sheathe} gaze=${gazeYaw} completes`);
 const end=m.frames[m.completionTick],expected=sheathe?H.compose(H.scaledGrip(setup,end.scale),H.seatHandAtScale(setup,H.seatedSword(setup,end.holster),end.scale)):H.compose(H.scaledGrip(setup,end.scale),end.pose[m.arm[2]]);
 assert(distance(end.sword.p,expected.p)<1e-8);assert(H.angle(end.sword.q,expected.q)<1e-5,'end parenting and ordinary held grip');
 for(const f of m.frames.filter(f=>f.phase==='Slide'))maxGrip=Math.max(maxGrip,f.handError);
 ++cases;
}
assert(maxGrip<1,'new grip retains slide accuracy');
const saved=require('./data/grip-side-regression.json');let currentMaxGrip=0;
for(const motion of ['idle','walk'])for(const sheathe of [true,false]){
 const m=H.prepare(data,setup,{...saved,motion,sheathe});assert(m.completionTick!==null);
 for(let t=m.plan.endTick/60;t<m.plan.slideEnd/60;t+=.002){
  const f=H.sample(m,t);currentMaxGrip=Math.max(currentMaxGrip,f.handError);
  assert(f.handError<.1,'saved curved setup retains fractional grip accuracy');
 }
}
assert.equal(JSON.stringify(setup),original,'exported reference remains unchanged');
console.log(JSON.stringify({passed:true,cases,currentCases:4,maxGrip,currentMaxGrip}));
