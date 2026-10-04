const fs=require('fs'),assert=require('assert/strict'),R=require('./recovery.js');
const manifest=JSON.parse(fs.readFileSync(__dirname+'/data/manifest.json'));
let cases=0;
for(const clip of manifest.clips){
 const v=clip.variants[0],b=fs.readFileSync(__dirname+'/'+v.file),m=R.prepare(v,b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),clip,manifest.names,manifest.parents);
 for(const yaw of [0,-179,179])for(const spring of [false,true]){
  const base={duration:.35,spineTurn:yaw,inertia:.7,springReturn:spring,worldInertia:true},opt={...base,angleTimeSeconds:3},timing=R.returnTiming(m,opt);
  const endpoint=R.sample(m,m.attackSeconds,opt),local=R.localize(endpoint.points,endpoint.q,m.parents),angle=R.length(R.qlog(R.qm(R.qinv(m.idle.q[m.spine]),local.q[m.spine])))*180/Math.PI;
  assert(Math.abs(timing.angle-angle)<1e-9);assert(Math.abs(timing.duration-(.35+3*angle/90))<1e-10);
  for(const t of [m.attackSeconds-.01,m.attackSeconds,m.attackSeconds+.13])assert.deepEqual(R.sample(m,t,base),R.sample(m,t,{...base,angleTimeSeconds:0}));
  assert.strictEqual(R.sample(m,m.attackSeconds+timing.duration,opt),m.idlePose);
  const actual=R.sample(m,m.attackSeconds+timing.duration*.41,opt),expected=R.sample(m,m.attackSeconds+timing.duration*.41,{...base,duration:timing.duration});assert.deepEqual(actual,expected);
  assert(actual.points.flat().every(Number.isFinite));assert(Math.abs(R.returnTiming(m,{...opt,duration:1.35}).addedSeconds-timing.addedSeconds)<1e-12);assert(Math.abs(R.returnTiming(m,{...opt,duration:1.35}).duration-timing.duration-1)<1e-12);cases++;
 }
 // A common world rotation must not affect a parent-local angle.
 const last=m.locals.at(-1),original=last.q[m.spine];last.q[m.spine]=R.qm(m.idle.q[m.spine],R.qexp([Math.PI/2,0,0]));
 assert(Math.abs(R.returnTiming(m,{duration:3,angleTimeSeconds:4}).duration-7)<1e-9);
 assert.notStrictEqual(R.sample(m,m.attackSeconds+6,{duration:3,angleTimeSeconds:4,inertia:.5}),m.idlePose);
 assert.strictEqual(R.sample(m,m.attackSeconds+7,{duration:3,angleTimeSeconds:4,inertia:.5}),m.idlePose);
 last.q[m.spine]=m.idle.q[m.spine];assert.equal(R.returnTiming(m,{duration:1,angleTimeSeconds:4}).duration,1);last.q[m.spine]=original;
}
console.log('PASS: '+cases+' angle/yaw/method cases: endpoint angle, zero parity, duration-only equivalence, idle endpoint and durations beyond 5s.');
