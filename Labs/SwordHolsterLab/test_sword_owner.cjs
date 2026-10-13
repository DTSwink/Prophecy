const assert=require('node:assert/strict'),H=require('./holster'),R=require('./recovery'),Tip=require('./tipalign');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./state.json').parameters;
const distance=(a,b)=>R.length(R.sub(a,b));let cases=0,maxError=0;
for(const noCheat of [false,true]){
 const o={...saved,...saved.sheatheBody,sheathe:true,noCheat,motion:'run',duration:8,shrinkPercent:20};
 const baseline=H.prepare(data,setup,o),begin=Tip.begin,solve=H.solve;let captured=false,perturbed;
 // Adversarial solver result: preserve the arm lengths, but translate the
 // entire solved arm away after capture. Sword ownership must not depend on it.
 Tip.begin=(...a)=>{captured=true;return begin(...a);};
 H.solve=(pose,arm,goal)=>{const result=solve(pose,arm,goal);if(captured)for(const j of arm)pose[j]={...pose[j],p:R.add(pose[j].p,[100,0,0])};return result;};
 try{perturbed=H.prepare(data,setup,o);}finally{Tip.begin=begin;H.solve=solve;}
 assert.equal(perturbed.plan.attachTick,baseline.plan.attachTick);
 assert.equal(perturbed.plan.endTick,baseline.tipAlign.tick+baseline.tipAlign.ticks);
 assert.equal(perturbed.plan.slideEnd,baseline.plan.slideEnd);
 for(let tick=baseline.tipAlign.tick;tick<=baseline.plan.slideEnd;tick++){
  const a=baseline.frames[tick],b=perturbed.frames[tick];
  maxError=Math.max(maxError,distance(a.sword.p,b.sword.p));
  assert(distance(a.sword.p,b.sword.p)<1e-8&&H.angle(a.sword.q,b.sword.q)<1e-5,'arm solver must not reposition the sword');
 }
 assert(perturbed.frames.some(f=>f.attached&&f.handError>50),'expose the failed hand tracking');cases++;
}
console.log(JSON.stringify({cases,maxSwordPositionErrorCm:maxError}));
