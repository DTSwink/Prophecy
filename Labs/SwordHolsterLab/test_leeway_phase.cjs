const assert=require('node:assert/strict'),H=require('./holster'),R=require('./recovery'),P=require('./sequence');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
let cases=0,arrivals=0,maxTransferError=0;
for(const noCheat of [false,true])for(const motion of ['idle','walk','run'])for(const holsterRotationStabilization of [0,1]){
 const o={...saved,...saved.sheatheBody,sheathe:true,noCheat,motion,leewayPhase:false,holsterRotationStabilization,duration:10};
 const m=H.prepare(data,setup,o);assert(!m.tipAlign);assert(!m.frames.some(f=>f.phase==='Align tip'));
 const admissible=f=>{const full=H.seatedSword(setup,f.holster);return R.length(R.sub(H.point(f.sword,m.tip),H.point(full,setup.baseBladeLocal)))<=2+1e-8&&H.angle(f.sword.q,full.q)<=o.sheatheRotationTolerance+1e-5;};
 for(const f of m.frames){if(f.tick<o.startTick)continue;if(!f.attached){assert(!admissible(f),'no missed arrival');const held=H.compose(H.scaledGrip(setup,f.scale),f.pose[m.arm[2]]);assert(R.length(R.sub(held.p,f.sword.p))<1e-8);}}
 if(m.plan.arrives){
  arrivals++;assert.equal(m.plan.attachTick,m.plan.endTick);const f=m.frames[m.plan.attachTick];assert(admissible(f));assert.equal(f.phase,'Slide');
  const held=H.compose(H.scaledGrip(setup,f.scale),f.pose[m.arm[2]]),e=R.length(R.sub(held.p,f.sword.p));maxTransferError=Math.max(maxTransferError,e);assert(e<1e-8);assert(H.angle(held.q,f.sword.q)<1e-5);assert(m.completionTick!==null,'return completes');
 }
 cases++;
}
for(const noCheat of [false,true]){const o={...saved,...saved.drawBody,sheathe:false,noCheat,motion:'run',duration:10};assert.deepEqual(H.prepare(data,setup,{...o,leewayPhase:false}).frames,H.prepare(data,setup,{...o,leewayPhase:true}).frames,'drawing unchanged');}
assert.equal(H.sanitize({}).leewayPhase,true);
console.log({cases,arrivals,blocked:cases-arrivals,maxTransferErrorCm:maxTransferError,drawingUnchanged:true});
