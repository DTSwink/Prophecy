const assert=require('node:assert/strict'),L=require('./headlook.js'),R=require('./recovery.js'),data=require('./data/head-handoff-regression.json');
const ctx=L.make(data);let peak=0,endError=0;const reports=[];
for(const c of data.cases){
 const start=c.frames.find(f=>f.active),lookOut=c.frames.find(f=>f.phase===2&&f.slide>=.5).tick;
 const oldExit=c.frames.find(f=>f.tick>lookOut&&!f.active).tick;
 const referenceQ=R.qm(R.qexp(R.mul(start.delta,-1)),start.q);
 let state={q:start.q,referenceQ,worldDelta:start.delta,baseDelta:start.delta,parentCorrection:[0,0,0],correction:[0,0,0]},previous=null,finished=false;
 const frames=c.frames.filter(f=>f.tick>=start.tick);
 const last=frames.at(-1);for(let k=1;k<=240;k++)frames.push({...last,tick:last.tick+k,pose:last.base});
 for(const f of frames){
  if(f.tick<lookOut){
   state.q=f.q;state.worldDelta=f.delta;
   state.baseDelta=L.correctionLog(R.qm(f.base[ctx.head].q,R.qinv(referenceQ)),state.baseDelta);
   state.parentCorrection=L.correctionLog(R.qm(f.pose[ctx.anchor].q,R.qinv(f.base[ctx.anchor].q)),state.parentCorrection);
   continue;
  }
  const pose=f.tick>=oldExit?f.base:f.pose;
  const base=f.base.map((b,j)=>j===ctx.head?{...b,q:referenceQ}:b);
  const speed=100+200*Math.min(1,Math.abs(f.gaze[0]));
  const out=L.step(ctx,pose,base,[0,0,0],state,{tick:f.tick,startTick:start.tick,lookOutTick:lookOut,maxLookIn:170,maxLookOut:speed,lookOutExponent:2,lookOutQ:f.base[ctx.head].q,neckBase:f.base,gazeNeckBase:f.base,maxDownAngle:45});
  state=out.state;
  assert(out.info.angularStep<=speed/60+.001,'head keeps profile speed');
  if(previous)for(const j of ctx.chain)peak=Math.max(peak,L.angle(out.pose[j].q,previous[j].q));
  previous=out.pose;
  if(out.info.done&&f.tick>=oldExit){
   for(const j of ctx.chain){const error=L.angle(out.pose[j].q,f.base[j].q);endError=Math.max(endError,error);assert(error<.001,'whole neck returns to current NN');}
   reports.push({name:c.name,oldExit,newExit:f.tick});finished=true;break;
  }
 }
 assert(finished,'recorded moving NN return finishes');
}
assert(peak<8,'no replacement neck discontinuity');
console.log(JSON.stringify({passed:true,agents:data.cases.length,peak,endError,reports}));
