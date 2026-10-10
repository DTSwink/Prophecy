const assert=require('node:assert/strict'),H=require('./holster.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
const degrees=180/Math.PI;
for(const motion of ['idle','walk'])for(const sheathe of [true,false]){
 const m=H.prepare(data,setup,{motion,sheathe}),end=m.plan.endTick,start=m.o.startTick;
 const first=m.frames[start].body,mid=m.frames[Math.floor((start+end)/2)].body,last=m.frames[end].body;
 assert.equal(first.applied[0],0,'no spine entry snap');assert.equal(last.spineArrivalTick,end);
 assert.deepEqual(first.applied.slice(1),[0,0],'no clavicle entry snap');assert.equal(last.clavicleArrivalTick,end);
 assert(Math.hypot(last.applied[1]-last.desired[1],last.applied[2]-last.desired[2])<1e-9,'clavicle and hand arrive together');
 const clavicleRatio=Math.hypot(...mid.applied.slice(1))/Math.hypot(...last.applied.slice(1));
 assert(clavicleRatio>.35&&clavicleRatio<.65,'clavicle turn spread across reach');
 assert(m.frames.slice(start,end-1).every(f=>Math.hypot(f.body.applied[1]-f.body.desired[1],f.body.applied[2]-f.body.desired[2])>.001),'no early clavicle finish');
 for(let i=start+1;i<m.frames.length;i++)assert(Math.hypot(m.frames[i].body.applied[1]-m.frames[i-1].body.applied[1],m.frames[i].body.applied[2]-m.frames[i-1].body.applied[2])*degrees<=m.o.maxSpineClavicleAngularSpeed/60+1e-8,'clavicle speed cap');
 assert(Math.abs(last.applied[0]-last.desired[0])<1e-9,'spine and hand arrive together');
 const ratio=Math.abs(mid.applied[0]/last.applied[0]);assert(ratio>.35&&ratio<.65,'turn spread across reach');
 assert(m.frames.slice(start,end-1).every(f=>Math.abs(f.body.applied[0]-f.body.desired[0])>.001),'no early finish');
 for(let i=start+1;i<m.frames.length;i++)assert(Math.abs(m.frames[i].body.applied[0]-m.frames[i-1].body.applied[0])*degrees<=m.o.maxSpineClavicleAngularSpeed/60+1e-8,'speed cap');
}
const slow=H.prepare(data,setup,{sheathe:true,maxReachSpeed:10000,maxReachRotationSpeed:10000,maxSpineClavicleAngularSpeed:10});
const arrival=slow.frames[slow.plan.endTick].body;
assert(arrival.spineSpeedLimited);assert(Math.abs(arrival.applied[0]-arrival.desired[0])*degrees>1,'cap overrides simultaneous arrival');
 assert(arrival.clavicleSpeedLimited);assert(Math.hypot(arrival.applied[1]-arrival.desired[1],arrival.applied[2]-arrival.desired[2])*degrees>1,'clavicle cap overrides timing');
for(let i=slow.o.startTick+1;i<slow.frames.length;i++)assert(Math.abs(slow.frames[i].body.applied[0]-slow.frames[i-1].body.applied[0])*degrees<=10/60+1e-8);
for(let i=slow.o.startTick+1;i<=slow.plan.endTick;i++)assert(Math.hypot(slow.frames[i].body.applied[1]-slow.frames[i-1].body.applied[1],slow.frames[i].body.applied[2]-slow.frames[i-1].body.applied[2])*degrees<=10/60+1e-8);
console.log('PASS: idle/walk draw/sheath spine AND clavicle arrive with FK reach, no early finish; both angular-speed caps win when necessary.');
