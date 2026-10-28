const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),F=require('./surface.js'),K=require('./footik.js'),{load}=require('./test-bank.cjs');
const run=load('walk',.69),cases=[];
assert.equal(K.sanitize().deleteFloorFrame,-1);
assert.equal(K.sanitize({deleteFloorFrame:''}).deleteFloorFrame,-1);
assert.equal(K.sanitize({deleteFloorFrame:20.2}).deleteFloorFrame,20);
for(const approach of['toward','parallel']){
 const terrain=F.createTerrain({slopeAngle:90,approach,deleteFloorFrame:60});
 // Use the plane's own downhill direction for either orientation.
 const onPlane=terrain.slope.world(approach==='toward'?[0,0,-10]:[-10,0,0]);
 assert(onPlane[1]<-9.9);assert.equal(terrain.pick(onPlane).surface.id,'incline');
 if(approach==='toward'){
  assert.equal(terrain.surfacesAt(59/60).length,2);assert.equal(terrain.surfacesAt(1).length,1);
  assert.equal(terrain.surfacesAt(4).length,1);assert.equal(terrain.surfacesAt(0).length,2,'reverse seek restores geometry');
 }
}
for(const slopeAngle of[45,90]){
 const settings={gait:'walk',terrain:'incline',slopeAngle,inclineGravity:true,fullGravity:100,energyConservation:100},keep=F.prepare(run,{...settings,deleteFloorFrame:-1});
 for(const deleteFloorFrame of[0,20,120,300]){
  const m=F.prepare(run,{...settings,deleteFloorFrame}),cut=deleteFloorFrame*2;
  assert.deepEqual(m.frames.slice(0,cut),keep.frames.slice(0,cut),'exact prefix before deletion');
  if(cut>0){assert.deepEqual(m.frames[cut].surface.mass,keep.frames[cut].surface.mass);assert.deepEqual(m.frames[cut].surface.velocity,keep.frames[cut].surface.velocity,'deletion does not impart an impulse');}
  for(let i=cut;i<m.frames.length;i++){
   assert(m.frames[i].feet.every(f=>f.contact?.surface!=='entry'),'no deleted-floor pin');
   assert(m.frames[i].pose.points.flat().every(Number.isFinite));
  }
  if(deleteFloorFrame===0){assert.deepEqual(m.frames[0].surface.drive,[0,0,0]);assert.deepEqual(m.frames[0].surface.supportForce,[0,0,0]);}
  assert(m.metrics.maxPenetration<1e-4&&m.metrics.maxReachError<1e-7&&m.metrics.maxContactDrift<1e-8);
  if(slopeAngle===90&&deleteFloorFrame<120){
   assert(m.frames.at(-1).surface.mass[1]<-20,'root falls below the old floor');
   const local=m.terrain.slope.local(m.frames.at(-1).surface.mass);assert(local[2]>m.terrain.slope.bounds[2],'wall covers the full downward flight');
  }
  cases.push({slopeAngle,deleteFloorFrame,finalHeight:m.frames.at(-1).surface.mass[1],metrics:m.metrics});
 }
 const pinTick=keep.frames.findIndex((f,i)=>i>0&&i%2===0&&f.feet.some((foot,side)=>foot.contact?.surface==='entry'&&keep.frames[i-1].feet[side].contact?.surface==='entry'));
 assert(pinTick>0);const release=F.prepare(run,{...settings,deleteFloorFrame:pinTick/2});
 assert(release.events.some(e=>e.type==='release'&&e.reason==='surface-removed'&&e.frame===pinTick/2),'existing pin released on the exact deletion frame');
}
const a=K.prepare(run,{terrain:'stairs',deleteFloorFrame:-1}),b=K.prepare(run,{terrain:'stairs',deleteFloorFrame:0});
assert.equal(JSON.stringify(a.frames),JSON.stringify(b.frames),'other terrain modes unaffected');
fs.writeFileSync(path.join(__dirname,'snapshots/floor-delete-verification.json'),JSON.stringify({passed:true,cases},null,2));
console.log(JSON.stringify({passed:true,cases:cases.map(({metrics,...r})=>r)}));
