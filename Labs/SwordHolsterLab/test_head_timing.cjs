const {assertHeadBudget}=require('./head-test-helpers.cjs');
const assert=require('node:assert/strict'),L=require('./headlook.js'),H=require('./holster.js');
const ctx=L.make({names:['spine_05','neck_01','neck_02','head'],parents:[-1,0,1,2]});
const pose=Array.from({length:4},()=>({p:[0,0,0],q:[0,0,0,1]}));
function run(alpha,exponent=1,speed=90,arrival=180){
 let state={},frames=[];
 for(let tick=0;tick<=400;tick++){
  const f=L.step(ctx,pose,pose,[1,0,0],state,{tick,startTick:0,lookOutTick:Infinity,maxLookIn:speed,maxLookOut:90,lookInExponent:exponent,lookInSpeedAlpha:alpha,handArrivalTick:arrival});
  state=f.state;frames.push(f);assert(f.info.angularStep<=speed/60+1e-5,'speed limit');
 }
 return frames;
}
assert.equal(H.sanitize({}).headLookInSpeedAlpha,1);
assert.equal(H.sanitize({headLookInSpeedAlpha:-2}).headLookInSpeedAlpha,0);
assert.equal(H.sanitize({headLookInSpeedAlpha:4}).headLookInSpeedAlpha,1);
for(const exponent of [1,2])for(const alpha of [0,.5,1]){
 const frames=run(alpha,exponent),duration=60*exponent+(180-60*exponent)*(1-alpha);
 assert(frames[duration].info.remainingDegrees<1e-5,'arrives at selected time');
 assert(frames[duration-1].info.remainingDegrees>1e-4,'does not finish early');
 assert(Math.abs(L.angle(frames[0].state.q,frames[duration/2].state.q)-45)<1e-5,'exponent profile spans the selected duration');
}
const slow=run(0,2,30,60);
assert(slow[60].info.remainingDegrees>10,'cannot bypass speed limit to reach hand deadline');
assert(slow[360].info.remainingDegrees<1e-5,'slow turn completes under shaped speed limit');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
for(const motion of ['idle','walk'])for(const sheathe of [false,true]){
 const base=H.prepare(data,setup,{motion,sheathe,maxHeadLookInVelocity:1000,headLookInExponent:2});
 assert(base.plan.arrives);
 for(const alpha of [0,.5,1]){
  const m=H.retime(base,{...base.o,headLookInSpeedAlpha:alpha});
  assert.equal(m.sourceFrames,base.sourceFrames,'head timing does not replan arms');
  if(alpha===1)assert.deepEqual(m.frames,base.frames,'maximum setting preserves previous behavior');
  assert(m.frames[m.plan.endTick].headLook.remainingDegrees<.001,'moving target reached on hand arrival');
  for(const f of m.frames)if(f.tick>m.o.startTick)assertHeadBudget(m,f.tick);
 }
}
console.log('PASS: hand-timed/max/intermediate arrival, sigmoid shape, angular cap precedence, moving D/S targets and unchanged default.');
