import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),{load}=require('./test-bank.cjs');
const fixture=JSON.parse(fs.readFileSync(new URL('data/forward-clearance-before.json',import.meta.url))),run=load('walk',fixture.phase),model=K.prepare(run,fixture),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const gaps=fixture.samples.map(s=>({before:s.gap,after:model.frames[s.frame*2].feet[s.side].soleGap}));
const mean=(xs,key)=>xs.reduce((n,x)=>n+x[key],0)/xs.length;
check('Forward swing mean clearance reduced by at least one third',mean(gaps,'after')<mean(gaps,'before')*2/3);
// A shallower heel landing changes ankle height around the material pivot.
// Bound additional lift by the clearance budget, rather than requiring the
// former steep landing's identical ankle path.
// Selecting the sole's actual supporting tread can change the landing by one
// stair height. Do not mistake that height for extra airborne clearance.
check('Changed support stays within one tread plus the clearance budget',fixture.samples.every(s=>model.frames[s.frame*2].pose.points[run.names.indexOf('foot_'+(s.side?'r':'l'))][1]-s.ankleAfterClearance<=(fixture.height+fixture.clearance)/100));
const reported=model.sample(163/60).feet[1];
check('Reported163 forward sole clears the last tread without exceeding 7cm',reported.soleGap>=-1e-6&&reported.soleGap<.07);
check('165 forward sole stays within 6cm of tread',model.sample(165/60).feet[1].soleGap<.06);
check('Whole course rendered sole collision is preserved',model.metrics.maxPenetration<1e-5);
let maxAngle=0,maxStep=0;
for(let i=1;i<model.frames.length;i++)for(const side of ['l','r'])for(const bone of ['thigh_','calf_','foot_']){
 const j=run.names.indexOf(bone+side),p=model.frames[i].pose,prev=model.frames[i-1].pose;
 maxAngle=Math.max(maxAngle,2*Math.acos(Math.min(1,Math.abs(R.dot(p.q[j],prev.q[j]))))*180/Math.PI);
 maxStep=Math.max(maxStep,R.length(R.sub(p.points[j],prev.points[j])));
}
check('Saved phase49 retains whole-course angular motion bound',maxAngle<15);
check('Saved phase49 retains whole-course displacement bound',maxStep<.09);
const result={passed:true,checks,measured:{samples:gaps.length,meanGapBeforeCm:mean(gaps,'before')*100,meanGapAfterCm:mean(gaps,'after')*100,frame163GapCm:reported.soleGap*100,maxAngle,maxStep}};
fs.writeFileSync(new URL('clearance-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
