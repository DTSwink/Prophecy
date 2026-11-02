'use strict';
// Compare the exact retained-history contract; no NN/inference, engine or worker.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const P=require('./live-stair-planner.cjs'),K=require('../../Labs/FootIKLab/footik.js'),T=require('../../Labs/FootIKLab/terrain.js');
const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const packaged=process.argv.includes('--packaged'),deltaFactory=packaged?require('./live-proof-runtime.cjs'):P;
const clone=structuredClone;
function crop(input,from,to){
 const source=clone(input.source);source.poses=source.poses.slice(from/4,to/4+1);source.roots=source.roots.slice(from/4,to/4+1);
 source.rootYawDegrees=source.rootYawDegrees?.slice(from/4,to/4+1)||source.roots.map(()=>0);
 source.duration=source.totalDuration=(to-from)/120;source.directionMeta={...source.directionMeta,totalDuration:source.duration};return source;
}
async function check(name){
 const input=JSON.parse(fs.readFileSync(path.join(folder,name+'.input.json'))),expected=JSON.parse(fs.readFileSync(path.join(folder,name+'.expected.json')));
 const run=K.decode(input.source,input.parents),terrain=T.create(input.settings),origin=run.poses[0].points[0];
 const pinned=name.includes('stairs'),first=pinned?expected.frames.findIndex((f,i)=>i>=200&&i%4===0&&f.feet.some(x=>x.contact)):144;
 assert(first>=0);const initial=crop(input,0,first+72),options={...input,source:initial,handoff:false};
 const full=P.create(options),delta=deltaFactory.create(options),actual=new Map();let checked=0,receiptChecks=0,fullSent=0,deltaSent=0;
 const observed=tick=>{if(!actual.has(tick)){const p=K.at(run,tick/120),raw={...clone(p),points:p.points.map(v=>[v[0]-origin[0],v[1]+terrain.rootHeight(p.points[0][2]-origin[2]),v[2]-origin[2]])};actual.set(tick,{...clone(expected.frames[tick]),raw,rootHeading:[0,0,1]});}return actual.get(tick);};
 const packet=(from,to)=>Array.from({length:to-from+1},(_,i)=>({tick:from+i,frame:clone(observed(from+i))}));
 await full.plan();await delta.plan();
 for(const p of [full,delta])p.accept(packet(0,first));
 let ack=first;
 for(let pass=0;pass<3;pass++){
  // Public ConsumeJoined can replace the last acknowledged tick. Preserve the
  // real contact and add an observable receipt without moving its material pin.
  const changed=observed(ack),foot=changed.feet.find(f=>f.contact)||changed.feet[0];
  if(foot.contact)foot.contact.hostReceipt='replacement-'+pass;else foot.hostReceipt='replacement-'+pass;
  const current=ack+4,source=crop(input,current-4,current+72),a=packet(Math.max(0,ack-120),current),b=packet(Math.max(0,ack-2),current);
  fullSent+=a.length;deltaSent+=b.length;
  const r1=await full.plan({source,sourceStartTick:current-4,acceptedFrames:a}),r2=await delta.plan({source,sourceStartTick:current-4,acceptedFrames:b});
  assert(r1.ready&&r2.ready);assert.deepEqual(r1.continuity,r2.continuity);assert.equal(full.status.baseTick,delta.status.baseTick);
  if(!packaged)assert.deepEqual(full.source,delta.source);
  for(let t=full.status.baseTick;t<=Math.round(full.status.generatedThrough*120);t++){assert.equal(JSON.stringify(delta.frame(t)),JSON.stringify(full.frame(t)),name+' frame '+t);checked++;}
  assert.deepEqual(delta.frame(ack).feet,full.frame(ack).feet);assert.equal((delta.frame(ack).feet.find(f=>f.contact)?.contact||delta.frame(ack).feet[0]).hostReceipt,'replacement-'+pass);receiptChecks++;
  if(pinned)assert(delta.frame(ack).feet.some(f=>f.contact),'Actual material pin remains present');
  ack=current;
 }
 full.cancel();delta.cancel();return {name,completeFramesCompared:checked,sameAcknowledgedTickReplacements:receiptChecks,fullSent,deltaSent,pinned};
}
(async()=>{const start=performance.now(),cpu=process.cpuUsage(),cases=[];for(const name of ['walk-flat','walk-stairs'])cases.push(await check(name));const used=process.cpuUsage(cpu),report={passed:true,packaged,cases,explicitCheckpointUnchanged:true,cpuMilliseconds:(used.user+used.system)/1000,wallMilliseconds:performance.now()-start};fs.writeFileSync(path.join(folder,packaged?'live-history-overlap-packaged.json':'live-history-overlap.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));})().catch(e=>{console.error(String(e));process.exitCode=1;});
