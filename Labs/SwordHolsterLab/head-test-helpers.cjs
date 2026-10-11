const assert=require('node:assert/strict'),H=require('./holster.js');

function assertHeadBudget(model,tick){
 const f=model.frames[tick],before=model.frames[tick-1],head=model.headContext.head;
 const step=H.angle(before.pose[head].q,f.pose[head].q),cap=f.headLook.speedLimit/60;
 assert(step<=cap+.001,`head budget at ${tick}: ${step} > ${cap}`);
}
module.exports={assertHeadBudget};
