const assert=require('node:assert/strict'),L=require('./headlook.js'),H=require('./holster.js');
// A stationary, coincident neck fixture isolates velocity shaping from gait
// and the moving head origin. Real skeleton/clock coverage lives in the other tests.
const ctx=L.make({names:['spine_05','neck_01','neck_02','head'],parents:[-1,0,1,2]});
const pose=Array.from({length:4},()=>({p:[0,0,0],q:[0,0,0,1]}));
function run(inside,outside,outTick=601){
 let state={},frames=[];
 for(let tick=0;tick<=outTick+500;tick++){
  const f=L.step(ctx,pose,pose,[1,0,0],state,{tick,startTick:0,lookOutTick:outTick,maxLookIn:90,maxLookOut:90,lookInExponent:inside,lookOutExponent:outside});
  state=f.state;frames.push(f);
  assert(f.info.angularStep<=1.500001,'angular cap, including phase switch');
  assert(state.q.every(Number.isFinite),'finite head rotation');
 }
 return frames;
}
assert.equal(H.defaults.headLookInExponent,1);assert.equal(H.defaults.headLookOutExponent,1);
assert.equal(H.sanitize({headLookInExponent:0,headLookOutExponent:99}).headLookInExponent,1);
assert.equal(H.sanitize({headLookInExponent:0,headLookOutExponent:99}).headLookOutExponent,8);
const linear=run(1,1);
assert(Math.abs(linear[1].info.angularStep-1.5)<1e-6,'default preserves max-rate start');
assert(L.angle(linear[60].state.q,linear[600].state.q)<1e-5,'default arrival at 90 degrees / 90 degrees per second');
for(const exponent of [1.5,2,4,8]){
 const frames=run(exponent,exponent),ticks=60*exponent;
 for(const start of [0,600]){
  const steps=frames.slice(start+1,start+ticks+1).map(f=>f.info.angularStep),peak=Math.max(...steps);
  assert(steps[0]<peak*.35&&steps.at(-1)<peak*.35,'slow start and end in both directions');
  assert(Math.abs(L.angle(frames[start].state.q,frames[start+ticks/2].state.q)-45)<1e-5,'half the turn at half time');
  assert(peak>1.4&&peak<=1.500001,'middle uses available speed');
 }
 assert(frames.at(-1).info.done,'forward return completes');
 const inwardOnly=run(exponent,1),outwardOnly=run(1,exponent);
 for(let t=0;t<601;t++)assert.deepEqual(outwardOnly[t].state.q,linear[t].state.q,'out exponent cannot change look-in');
 for(let t=601;t<=661;t++)assert(L.angle(inwardOnly[t].state.q,linear[t].state.q)<1e-5,'in exponent cannot change settled look-out');
}
assert(run(4,3,21).at(-1).info.done,'interrupted look-in returns from actual orientation');
console.log('PASS: separate exponents, sigmoid in/out, exact linear default, speed limits, interrupted look-in and completed return.');
