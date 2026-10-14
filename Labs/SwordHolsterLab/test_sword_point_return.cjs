const assert=require('node:assert/strict'),H=require('./holster'),F=require('./fkreturn'),R=require('./recovery');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json'),state=require('./state.json');
const hand=data.names.indexOf('hand_r'),root=data.names.indexOf('root'),I=[0,0,0,1],RAD=Math.PI/180;
let shapeCases=0,cases=0;
// Speed budget stays signed and symmetric; exponent 1 is constant speed.
for(const exponent of [1,1.5,3,8])for(const speed of [30,-30]){
 let q=I,steps=[];
 for(let i=1;i<=60;i++){
  const budget=speed*RAD*(F.swordPointProgress(i/60,exponent)-F.swordPointProgress((i-1)/60,exponent));
  const last=q;q=R.unit(R.qm(q,R.qexp([budget,0,0])));steps.push(H.angle(last,q)*60);
  assert(steps.at(-1)<=Math.abs(speed)+1e-6);
 }
 assert(Math.sign(R.rotate(q,[0,0,1])[1])===-Math.sign(speed));
 assert(Math.abs(H.angle(q,I)-Math.abs(speed)/exponent)<1e-6);
 if(exponent===1)assert(steps.every(x=>Math.abs(x-30)<1e-6));
 else {assert(steps[0]<steps[30]);assert(Math.abs(steps[0]-steps.at(-1))<1e-5);}
 shapeCases++;
}
for(const noCheat of [false,true])for(const motion of ['idle','walk'])for(const springReturn of [false,true]){
 const p={...state.parameters,...state.parameters.drawBody,sheathe:false,noCheat,motion,duration:12,drawReturn:{...state.parameters.drawReturn,springReturn,swordPointSpeed:0}};
 const off=H.prepare(data,setup,p),on=H.retime(off,{...off.o,drawReturn:{...off.o.drawReturn,swordPointSpeed:180,swordPointExponent:1.5,swordPointCutoff:.5}});
 assert(on.swordPoint);assert.equal(on.completionTick,off.completionTick);let changed=0;
 for(let i=0;i<off.frames.length;i++){
  const a=off.frames[i],b=on.frames[i];
  for(let j=0;j<data.names.length;j++){
   assert.deepEqual(a.pose[j].p,b.pose[j].p,'positions unchanged');
   if(j!==hand)assert.deepEqual(a.pose[j],b.pose[j],'other bones untouched');
   assert(b.pose[j].q.every(Number.isFinite));
  }
  if(i<=off.plan.slideEnd)assert.deepEqual(a.pose,b.pose,'grip/reach unchanged');
  else {assert.deepEqual(b.sword,H.compose(H.scaledGrip(setup,b.scale),b.pose[hand]));if(H.angle(a.pose[hand].q,b.pose[hand].q)>.01)changed++;}
  if(i>=on.swordPoint.finish+1e-6)assert(H.angle(a.pose[hand].q,b.pose[hand].q)<1e-5,'existing return destination');
 }
 assert(changed>0);
 const end=on.swordPoint.end/60,eps=1e-6;
 assert(H.angle(H.sample(on,end-eps).pose[hand].q,H.sample(on,end+eps).pose[hand].q)<.01,'no snap at cutoff');
 for(const t of [end-.075,end+.075,end-.075]){
  const f=H.sample(on,t);assert(H.angle(f.sword.q,H.compose(H.scaledGrip(setup,f.scale),f.pose[hand]).q)<1e-5,'fractional sword follows hand');
 }
 const again=H.retime(on,{...on.o,drawReturn:{...on.o.drawReturn,swordPointSpeed:0}});assert.deepEqual(again.frames,off.frames,'disable restores exact old path');
 cases++;
}
const s=H.prepare(data,setup,{sheathe:true}),s1=H.retime(s,{...s.o,drawReturn:{...s.o.drawReturn,swordPointSpeed:180}});assert.deepEqual(s.frames,s1.frames,'S unchanged');
console.log(JSON.stringify({passed:true,shapeCases,cases}));
// Root turns carry the authored motion, future changes cannot affect its prefix,
// and increasing the exponent does not shift the cutoff or return endpoint.
function fixture(turn=0){
 const profile={...F.defaults(),swordPointSpeed:90,swordPointExponent:1.5,swordPointCutoff:.5,inertia:0};
 const frames=Array.from({length:121},(_,tick)=>{
  const rootQ=R.qexp([0,0,turn*tick/60]),pose=[0,1,2].map(j=>({p:[j,0,0],q:rootQ,s:[1,1,1]}));
  return {tick,pose,holster:{p:[0,0,0],q:rootQ,s:[1,1,1]},scale:1};
 });
 return {o:{sheathe:false,drawReturn:profile},names:['root','spine_05','hand_r'],parents:[-1,0,1],plan:{slideEnd:0},fkReturn:{timing:{duration:2}},setup,frames};
}
const a=fixture(),b=fixture(.7),future=fixture();
for(let i=50;i<future.frames.length;i++)future.frames[i].pose[1].q=R.qexp([0,0,2]);
for(const m of [a,b,future])F.prepareSwordPoint(m,H.compose,H.scaledGrip);
for(let i=0;i<a.frames.length;i++){
 assert(H.angle(b.frames[i].pose[2].q,R.qm(R.qexp([0,0,.7*i/60]),a.frames[i].pose[2].q))<1e-5,'root-local equivariance');
 if(i<50)assert.deepEqual(a.frames[i],future.frames[i],'no future input');
}
assert.equal(a.swordPoint.end,60);assert.equal(a.swordPoint.finish,120);
console.log('PASS root turns, current-only inputs and fixed window timing');

// Hand-local X is the only axis: moving spine/holster cannot steer it.
for(const speed of [90,-90,1000,-1000]){
 const still=fixture(),moved=fixture();
 for(const m of [still,moved])m.o.drawReturn.swordPointSpeed=speed;
 for(const f of moved.frames){f.holster.q=R.qexp([f.tick*.05,.2,1]);f.pose[1].q=R.qexp([0,0,f.tick*.015]);}
 for(const m of [still,moved])F.prepareSwordPoint(m,H.compose,H.scaledGrip);
 assert.deepEqual(still.swordPoint.keys,moved.swordPoint.keys,'no target chasing');
 for(let i=0;i<=still.swordPoint.end;i++){
  const theta=speed*RAD*F.swordPointProgress(i/60,1.5);
  assert(H.angle(still.frames[i].pose[2].q,R.qexp([theta,0,0]))<1e-5,'exact signed local-X rotation, including full turns');
 }
}
const tilted=fixture();const entryQ=R.qexp([.3,-.5,.9]);for(const f of tilted.frames)f.pose[2].q=entryQ;
F.prepareSwordPoint(tilted,H.compose,H.scaledGrip);
for(let i=0;i<=60;i++){
 const theta=90*RAD*F.swordPointProgress(i/60,1.5);
 assert(H.angle(tilted.frames[i].pose[2].q,R.qm(entryQ,R.qexp([theta,0,0])))<1e-5,'axis belongs to the rotated hand');
}
console.log('PASS signed hand-local X, full turns and independence from spine/holster motion');
