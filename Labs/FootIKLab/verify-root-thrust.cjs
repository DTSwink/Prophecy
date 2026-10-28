/* Real current Run-policy Walk command; bounded 5-second CPU-only clips. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),F=require('./surface.js'),K=require('./footik.js');
const read=name=>JSON.parse(fs.readFileSync(path.join(__dirname,name),'utf8').replace(/^\uFEFF/,''));
(async()=>{
 const saved=read('snapshots/before-root-thrust-state.json'),s=saved.settings,rig=read('data/rig.json');
 const response=await fetch('http://127.0.0.1:8890/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'direction',policy:'run',duration:5,gait:s.gait,phase:s.phase,direction:s.direction,rootYawSpeed:s.rootYawSpeed,rootYawStart:s.rootYawStart,rootYawStop:s.rootYawStop})});
 assert(response.ok);const run=K.decode(await response.json(),rig.parents),results=[];
 for(const fullGravity of[0,45,100]){
  const model=F.prepare(run,{...s,fullGravity}),active=model.frames.filter(f=>f.surface.gravityActive);
  assert(active.length>0);let fallingIntervals=0;
  for(let i=0;i<model.frames.length-1;i++){
   const a=model.frames[i].surface,b=model.frames[i+1].surface;
   if(!a.gravityActive)continue;
   assert.deepEqual(a.gravity,[0,-9.81,0]);
   if(fullGravity===100){
    assert(Math.abs(a.drive[1])+Math.abs(a.supportForce[1])<1e-12);
    assert(Math.abs(a.acceleration[1]+9.81)<1e-12);
    if(Math.abs(a.collisionImpulse[1])<1e-9){assert(Math.abs((b.velocity[1]-a.velocity[1])*120+9.81)<1e-8);fallingIntervals++;}
   }
  }
  if(fullGravity===100)assert(fallingIntervals>30,'sustained gravity acceleration, not only isolated frames');
  assert(model.metrics.maxPenetration<1e-4&&model.metrics.maxReachError<1e-7&&model.metrics.maxContactDrift<1e-8);
  results.push({fullGravity,activeFrames:active.length,fallingIntervals,verticalAccelerationRange:[Math.min(...active.map(f=>f.surface.acceleration[1])),Math.max(...active.map(f=>f.surface.acceleration[1]))],metrics:model.metrics});
 }
 fs.writeFileSync(path.join(__dirname,'snapshots/root-thrust-verification.json'),JSON.stringify({passed:true,settings:s,results},null,2));
 console.log(JSON.stringify({passed:true,cases:results.map(({metrics,...r})=>r)}));
})().catch(e=>{console.error(e);process.exitCode=1;});
