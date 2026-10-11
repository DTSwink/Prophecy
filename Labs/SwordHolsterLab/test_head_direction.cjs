const assert=require('node:assert/strict'),L=require('./headlook.js'),R=require('./recovery.js');
const ctx=L.make({names:['spine_05','neck_01','neck_02','head'],parents:[-1,0,1,2]});
const rad=Math.PI/180,yaw=d=>R.qexp([0,0,d*rad]);
const base=Array.from({length:4},()=>({p:[0,0,0],q:[0,0,0,1]}));
const heading=q=>{const v=R.rotate(q,[0,1,0]);return Math.atan2(-v[0],v[1])/rad;};
const unwrap=(d,previous)=>d+360*Math.round((previous-d)/360);
assert(!('forwardOnly' in L),'head orientation limiter is removed');

// The intended route goes through forward: +170 -> -40 -> +170 (and its
// mirror). A fresh shortest arc would go through the back instead.
for(const sign of [-1,1])for(const exponent of [1,2,4]){
 const pose=base.map((p,j)=>({...p,q:yaw(sign*170*j/3)}));
 const target=R.rotate(yaw(-sign*40),[0,1,0]);
 let state={},previous=170,peak=0;
 for(let tick=0;tick<=1250;tick++){
  const gaze=yaw(sign*170),lookOutQ=tick%2?R.mul(gaze,-1):gaze;
  const f=L.step(ctx,pose,base,target,state,{tick,startTick:0,lookOutTick:651,maxLookIn:120,maxLookOut:120,lookInExponent:exponent,lookOutExponent:exponent,lookOutQ});
  state=f.state;
  const actual=unwrap(sign*heading(state.q),previous);
  assert(actual<=170+.001&&actual>=-40-.001,'no extra turn or wrong-side shortcut');
  if(tick>0)assert(tick<651?actual<=previous+.0001:actual>=previous-.0001,'chosen rotation sign retained through phase');
  assert(f.info.angularStep<=2.00001,'strict angular-speed cap');
  peak=Math.max(peak,f.info.angularStep);previous=actual;
  if(tick===650)assert(Math.abs(actual+40)<.001,'look-in reaches the full target');
 }
 assert(Math.abs(previous-170)<.001,'return restores original signed gaze');
 assert(peak>1.9,'test exercises the speed cap');
}

// An independently moving target crosses the quaternion antipode. Alternating
// q/-q is the same orientation and must not reverse either linear or shaped motion.
for(const exponent of [1,3]){
 let state={},previous=0;
 for(let tick=0;tick<=120;tick++){
  const degrees=tick<2?179.9:tick%2?180.1:179.9;
  const raw=yaw(degrees),lookOutQ=tick%2?R.mul(raw,-1):raw;
  const f=L.step(ctx,base,base,[0,1,0],state,{tick,startTick:0,lookOutTick:1,maxLookIn:30,maxLookOut:30,lookOutExponent:exponent,lookOutQ});
  state=f.state;const actual=unwrap(heading(state.q),previous);
  assert(actual>=previous-1e-5,'180-degree crossing cannot reverse the head');
  assert(f.info.angularStep<=.50001,'target crossing cannot bypass the speed cap');
  previous=actual;
 }
 const duration=exponent*179.9/30*60,u=120/duration;
 const shaped=179.9*Math.pow(u,exponent)/(Math.pow(u,exponent)+Math.pow(1-u,exponent));
 assert(Math.abs(previous-shaped)<1e-5,'antipode tracking retains the configured timing');
}

// The look-at strength interpolation must retain its sign too, before the
// main head profile receives it. A partial alpha used to amplify this flip.
{
 let state={},previous=0;
 for(let tick=0;tick<=250;tick++){
  const degrees=Math.min(185,175+tick*.05),target=R.rotate(yaw(degrees),[0,1,0]);
  const f=L.step(ctx,base,base,target,state,{tick,startTick:0,lookOutTick:Infinity,maxLookIn:600,maxLookOut:600,lookAtAlpha:.6});
  state=f.state;const actual=unwrap(heading(state.q),previous);
  assert(actual>=previous-1e-5,'partial look-at alpha cannot change sides at 180 degrees');
  assert(actual<=111.00001,'strength follows the selected continuous aim branch');
  previous=actual;
 }
 assert(Math.abs(previous-111)<1e-5);
}

// No torso-relative restriction: a requested 140-degree world target is exact,
// even with a stationary torso. The target can then change during look-out.
let state={};
for(let tick=0;tick<=600;tick++){
 const lookOutQ=yaw(tick<301?140:55);
 const f=L.step(ctx,base,base,[0,1,0],state,{tick,startTick:0,lookOutTick:1,maxLookIn:180,maxLookOut:180,lookOutQ});
 state=f.state;
 if(tick===300||tick===600)assert(L.angle(state.q,lookOutQ)<.001,'current world target is reached without clipping');
 assert(f.info.angularStep<=3.00001);
}
console.log('PASS: signed in/out routes, both gaze signs, linear/sigmoid motion, q/-q, antipode crossings, unrestricted targets and changing gaze.');
