'use strict';
const fs=require('fs'),path=require('path'),z=require('zlib'),vm=require('vm'),assert=require('assert/strict'),{createRequire}=require('module');
const local=createRequire(__filename),K=require('./footik.js'),R=require('./recovery.js'),C=require('./surface-coupling.js');
const folder=path.resolve(__dirname,'../../Saved/FootIKSlideAudit20261029');
const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(folder,'final-current.fixture.json.gz'))));
const settings=JSON.parse(fs.readFileSync(path.join(folder,'drift-state-before.json'))).settings;
const run=K.decode(fixture.request.source,require('./data/rig.json').parents);
const source=fs.readFileSync(path.join(__dirname,'surface.js'),'utf8');
const before={module:{exports:{}},require:local,console};
vm.runInNewContext(source.replace('velocity=sub(velocity,mul(plane.normal,outward));','/* Previous behaviour: retain outward velocity. */'),before);
const bridge={module:{exports:{}},require:name=>name==='./surface.js'?before.module.exports:local(name),console};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'surface-coupling.js'),'utf8'),bridge);
async function solve(api){const s=api.createSession(run,settings,async(_,i)=>fixture.response.steps[i]);try{await s.extend(settings.trimOut);return s.model.frames;}finally{s.close();}}
(async()=>{
 const old=await solve(bridge.module.exports),frames=await solve(C),first=frames.findIndex(f=>f.slide),normal=[0,0,-1];
 let oldDrift=0,newDrift=0;
 for(let i=0;i<frames.length;i++){
  const a=old[i],b=frames[i];
  assert(Math.abs(a.root[0]-b.root[0])<1e-10&&Math.abs(a.root[1]-b.root[1])<1e-10,'Tangential inertia and gravity preserved');
  if(i<first)assert.deepEqual(JSON.parse(JSON.stringify(a)),JSON.parse(JSON.stringify(b)),'Pre-slide prefix unchanged');
  if(b.slide){
   oldDrift=Math.max(oldDrift,Math.abs(R.dot(R.sub(a.root,old[first].root),normal)));
   newDrift=Math.max(newDrift,Math.abs(R.dot(R.sub(b.root,frames[first].root),normal)));
   assert(R.length(b.surface.drive)<1e-10&&R.length(b.surface.supportForce)<1e-10,'No slide thrust or attraction');
  }
 }
 assert(oldDrift>.001,'Reproduced outward drift');assert(newDrift<1e-10,'Root remains at its entry wall distance');
 const report={passed:true,entry:first/2,oldDriftM:oldDrift,newDriftM:newDrift};
 fs.writeFileSync(path.join(folder,'root-drift-check.json'),JSON.stringify(report,null,2));console.log(report);
})().catch(e=>{console.error(e);process.exitCode=1;});
