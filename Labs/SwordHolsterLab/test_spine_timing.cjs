const assert=require('node:assert/strict'),H=require('./holster.js'),B=require('./bodyreach.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
let cases=0;
for(const motion of ['idle','walk'])for(const sheathe of [true,false])for(const maxSpineClavicleAngularSpeed of [10,90]){
 const m=H.prepare(data,setup,{motion,sheathe,maxSpineClavicleAngularSpeed,duration:30}),end=m.plan.endTick,start=m.o.startTick;
 assert(m.plan.arrives,'speed-limited body extends the reach plan');
 const first=m.sourceFrames[start].body,last=m.sourceFrames[end].body,target=B.target(m.bodyContext,m.o.bodyTargets,sheathe?0:1);
 assert(B.remaining(first.entry,first.applied)<1e-5,'no entry rotation snap');
 assert(B.remaining(last.applied,target)<1e-5,'all three bones reach authored endpoint with hand');
 const mid=m.sourceFrames[Math.floor((start+end)/2)].body;
 for(let k=0;k<12;k+=4){
  const total=H.angle(first.applied.slice(k,k+4),target.slice(k,k+4));
  if(total>1){const ratio=H.angle(first.applied.slice(k,k+4),mid.applied.slice(k,k+4))/total;assert(ratio>.45&&ratio<.55,'turn spread across hand reach');}
 }
 for(let tick=start+1;tick<=end;tick++)assert(B.remaining(m.sourceFrames[tick-1].body.applied,m.sourceFrames[tick].body.applied)<=maxSpineClavicleAngularSpeed/60+1e-5,'per-bone angular cap');
 cases++;
}
console.log(JSON.stringify({passed:true,cases,description:'All three authored bones arrive with hand; slow caps extend reach.'}));
