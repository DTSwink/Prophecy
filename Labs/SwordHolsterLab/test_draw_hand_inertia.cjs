const assert=require('node:assert/strict'),H=require('./holster.js'),F=require('./fkreturn.js'),R=require('./recovery.js'),T=require('./retime.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),saved=require('./data/draw-hand-inertia-regression.json');
const angle=(a,b)=>R.length(R.qlog(R.qm(b,R.qinv(a)))),rate=(a,b,dt)=>R.mul(R.qlog(R.qm(b,R.qinv(a))),1/dt);
let maxJump=0,maxOldJump=0,maxHandStep=0,cases=0,worstRatio=0;
const reports=[];
for(const motion of ['idle','walk','run'])for(const startFraction of [.7,1])for(const curved of [false,true])for(const worldInertia of [false,true])for(const springReturn of [false,true]){
 const curve=curved?[[.2,.03],[.4,.2],[.6,.82],[.8,.96]]:T.linear();
 const o={...saved.parameters,...saved.parameters.drawBody,motion,sheathe:false,drawCurve:curve,drawSlideCurve:curve,drawReturn:{...F.defaults(),startFraction,worldInertia,springReturn}};
 const m=H.prepare(data,setup,o),old=H.retime(m,{...m.o,drawReturn:{...m.o.drawReturn,boneInertia:{...m.o.drawReturn.boneInertia,hand:0}}});
 assert(m.plan.arrives);const t=m.plan.slideEnd/60,h=m.arm[2],dt=1e-5,get=(m,t)=>H.sampleBody(m,t).pose[h].q;
 const incoming=rate(get(m,t-dt),get(m,t),dt),outgoing=rate(get(m,t),get(m,t+dt),dt),oldOut=rate(get(old,t),get(old,t+dt),dt);
 const jump=R.length(R.sub(outgoing,incoming))*180/Math.PI,oldJump=R.length(R.sub(oldOut,incoming))*180/Math.PI;
 maxJump=Math.max(maxJump,jump);maxOldJump=Math.max(maxOldJump,oldJump);worstRatio=Math.max(worstRatio,jump/oldJump);
 assert(jump<oldJump,'hand rotation jump is reduced '+JSON.stringify({motion,startFraction,curved,worldInertia,springReturn,jump,oldJump}));
 assert(angle(get(m,t),get(old,t))<1e-9,'release pose unchanged');
 const ret=m.armReturn||m.fkReturn,end=ret.start+ret.timing.duration;
 for(const at of [t-.1,t,t+1/60,t+.2,end,end+.1]){
  const f=H.sampleBody(m,at),prior=H.sampleBody(old,at),base=H.motion(data,motion,at,m.o.gazeYaw);
  for(let j=0;j<data.names.length;j++){
   let handChild=false;for(let k=j;k>=0;k=data.parents[k])if(k===h)handChild=true;
   if(!handChild){
    // Coupled correction may rotate shoulder and move elbow when hand-offset
    // inertia changes the wrist path. The shoulder anchor and other bones stay put.
    if(j===m.arm[0])assert.deepEqual(f.pose[j].p,prior.pose[j].p,'shoulder position remains unchanged');
    else if(j===m.arm[1])assert(Math.abs(R.length(R.sub(f.pose[j].p,f.pose[m.arm[0]].p))-R.length(R.sub(prior.pose[j].p,prior.pose[m.arm[0]].p)))<1e-8,'upper arm length');
    else assert.deepEqual(f.pose[j],prior.pose[j],'hand inertia leaves unrelated bones unchanged');
   }
   assert(f.pose[j].q.every(Number.isFinite));
  }
  assert(Math.abs(R.length(R.sub(f.pose[h].p,f.pose[m.parents[h]].p))-R.length(R.sub(prior.pose[h].p,prior.pose[m.parents[h]].p)))<1e-8,'hand offset inertia preserves forearm length');
  if(at<=t)assert.deepEqual(f.pose,prior.pose,'no changes before release');
  if(at>=end)assert.deepEqual(f.pose[h],base[h],'exact moving animation endpoint');
  if(at>t)assert.deepEqual(f.sword,H.compose(H.scaledGrip(setup,f.scale),f.pose[h]),'sword follows hand');
 }
 const step=angle(get(m,t),get(m,t+1/60))*180/Math.PI;maxHandStep=Math.max(maxHandStep,step);
 reports.push({motion,startFraction,curved,worldInertia,springReturn,jump,oldJump,step});cases++;
}
// Captured user setup: the wrist stays quiet instead of inheriting a first-tick turn.
const currentOptions={...saved.parameters,...saved.parameters.drawBody,sheathe:false,...(saved.controls.bypassCurves?{drawCurve:T.linear(),drawSlideCurve:T.linear()}:{})};
const current=H.prepare(data,setup,currentOptions),legacy=H.retime(current,{...current.o,drawReturn:{...current.o.drawReturn,boneInertia:{...current.o.drawReturn.boneInertia,hand:0}}});
const release=current.plan.slideEnd/60,hand=current.arm[2];
const firstStep=m=>angle(H.sampleBody(m,release).pose[hand].q,H.sampleBody(m,release+1/60).pose[hand].q)*180/Math.PI;
const currentFirstStep=firstStep(current),legacyFirstStep=firstStep(legacy);
assert(currentFirstStep<legacyFirstStep*.1,'captured first-tick hand turn reduced by at least 90%');
// Sheathing retains the previous hand behavior even with the new saved weight.
const s=H.prepare(data,setup,{...saved.parameters,sheathe:true});
assert(!s.fkReturn.model.inertial[s.arm[2]]);if(s.armReturn)assert(!s.armReturn.model.inertial[s.arm[2]]);
assert.equal(F.sanitize({}).boneInertia.hand,1);
require('fs').mkdirSync('Saved/Diagnostics/SwordDrawHandInertia20261012',{recursive:true});
require('fs').writeFileSync('Saved/Diagnostics/SwordDrawHandInertia20261012/verification.json',JSON.stringify({cases,maxJump,maxOldJump,worstRatio,maxHandStep,currentFirstStep,legacyFirstStep,reports},null,2));
console.log(JSON.stringify({passed:true,cases,maxJump,maxOldJump,worstRatio,maxHandStep,currentFirstStep,legacyFirstStep}));

