const {assertHeadBudget}=require('./head-test-helpers.cjs');
const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
assert.equal(H.sanitize({}).sheatheHeadTargetAlpha,1,'old settings retain entrance target');
assert.equal(H.sanitize({sheatheHeadTargetAlpha:-2}).sheatheHeadTargetAlpha,0);
assert.equal(H.sanitize({sheatheHeadTargetAlpha:2}).sheatheHeadTargetAlpha,1);
let samples=0;
for(const motion of ['idle','walk'])for(const sheathe of [false,true]){
 const original=H.prepare(data,setup,{motion,sheathe});
 for(const alpha of [0,.5,1]){
  const m=H.retime(original,{...original.o,sheatheHeadTargetAlpha:alpha});
  assert.equal(m.sourceFrames,original.sourceFrames,'no arm replan');
  if(!sheathe||alpha===1)assert.deepEqual(m.frames,original.frames,'drawing and entrance default unchanged');
  for(const f of m.frames){
   const mouth=H.point(H.seatedSword(setup,f.holster),setup.baseBladeLocal),tip=H.point(f.sword,m.tip);
   const wanted=sheathe?R.add(R.mul(tip,1-alpha),R.mul(mouth,alpha)):mouth;
   assert(R.length(R.sub(wanted,f.headLook.target))<1e-8,'target follows actual scaled blade and moving entrance');
   if(f.tick>m.o.startTick)assertHeadBudget(m,f.tick);
   const body=H.sampleBody(m,f.tick/60);
   for(let j=0;j<f.pose.length;j++)if(!m.headContext.chain.includes(j))assert.deepEqual(f.pose[j],body.pose[j],'only neck/head change');
   samples++;
  }
 }
}
console.log(`PASS: sheathing tip/midpoint/entrance targets, unchanged draw/default, speed caps and arm preservation (${samples} frames).`);
