const assert=require('node:assert/strict'),H=require('./holster'),F=require('./fkreturn'),R=require('./recovery');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const hand=data.names.indexOf('hand_r'),root=data.names.indexOf('root'),angle=H.angle,distance=(a,b)=>R.length(R.sub(a,b));
let cases=0,changed=0;
for(const noCheat of [false,true])for(const startFraction of [.9,1])for(const springReturn of [false,true])for(const worldInertia of [false,true]){
 const o={motion:'walk',sheathe:false,noCheat,duration:12,drawReturn:{...F.defaults(),duration:.65,startFraction,springReturn,worldInertia}};
 const fk=H.prepare(data,setup,o),abs=H.retime(fk,{...fk.o,drawReturn:{...fk.o.drawReturn,handRotationFKAlpha:0}}),half=H.retime(fk,{...fk.o,drawReturn:{...fk.o.drawReturn,handRotationFKAlpha:.5}});
 assert.equal(abs.completionTick,fk.completionTick);assert.equal(half.completionTick,fk.completionTick);
 const release=fk.plan.slideEnd;
 for(let i=0;i<fk.frames.length;i++){
  const a=fk.frames[i],b=abs.frames[i],c=half.frames[i];
  if(i<=release)assert.deepEqual(b.pose,a.pose,'reach/grip/slide unchanged');
  for(let j=0;j<data.names.length;j++){
   assert.deepEqual(b.pose[j].p,a.pose[j].p,'hand and all body positions remain FK');
   if(j!==hand)assert.deepEqual(b.pose[j],a.pose[j],'only released hand orientation changes');
  }
  assert(angle(c.pose[hand].q,R.qslerp(b.pose[hand].q,a.pose[hand].q,.5))<1e-5,'alpha interpolates the two rotations');
  if(i>release){assert.deepEqual(b.sword,H.compose(H.scaledGrip(setup,b.scale),b.pose[hand]),'sword follows authored hand');if(angle(a.pose[hand].q,b.pose[hand].q)>.01)changed++;}
 }
 const ret=abs.armReturn||abs.fkReturn;assert(ret.handRotation,'single root-frame return exists even with no early return');
 const base=H.motion(data,'walk',ret.start+.2),pose=H.sampleBody(fk,ret.start+.2).pose;
 const result=F.applyHandRotation(ret,base,.2,pose),altered=structuredClone(pose);
 altered[hand].q=R.qm(R.qexp([1.3,-.6,.9]),pose[hand].q);
 assert.deepEqual(F.applyHandRotation(ret,base,.2,altered)[hand].q,result[hand].q,'zero ignores arm-carried hand rotation');
 const turn=R.qexp([0,0,1.1]),turnedBase=base.map(t=>({...t,q:R.qm(turn,t.q),p:R.rotate(turn,t.p)}));
 const turned=F.applyHandRotation(ret,turnedBase,.2,pose);
 assert(angle(turned[hand].q,R.qm(turn,result[hand].q))<1e-5,'current character-root turn carries independent hand');
 assert(angle(F.applyHandRotation(ret,base,ret.timing.duration,pose)[hand].q,base[hand].q)<1e-5,'exact current base destination');
 cases++;
}
// Sheathing ignores this drawing-only control.
const s=H.prepare(data,setup,{sheathe:true}),s0=H.retime(s,{...s.o,sheatheReturn:{...s.o.sheatheReturn,handRotationFKAlpha:0}});
assert.deepEqual(s0.frames,s.frames);assert(changed>0);
console.log(JSON.stringify({passed:true,cases,changed}));
