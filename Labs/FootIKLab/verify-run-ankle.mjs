import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),{load}=require('./test-bank.cjs');
const before=JSON.parse(fs.readFileSync(new URL('data/run-ankle-before.json',import.meta.url))),run=load(before.settings.gait,before.settings.phase),model=K.prepare(run,before.settings),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
const foot=run.names.indexOf('foot_l'),calf=run.names.indexOf('calf_l');
const relative=(q,c)=>R.qm(R.qinv(c),q);
const error=(f,q=f.pose.q[foot],c=f.pose.q[calf])=>angle(relative(q,c),relative(f.raw.q[foot],f.raw.q[calf]));
const reported=model.sample(81/60),old=before.rows[162].feet[0];
const beforeError=error(reported,old.q,old.kneeQ),afterError=error(reported);
check('Run81 releases the obsolete toe-off angle into NN ankle articulation',beforeError>90&&afterError<5);
const range=model.frames.slice(150,171),oldSteps=range.map((_,j)=>angle(before.rows[j+150].feet[0].q,before.rows[j+149].feet[0].q)),steps=range.map((f,j)=>angle(f.pose.q[foot],model.frames[j+149].pose.q[foot]));
check('Run75-85 angular peak is below 12 degrees per 120Hz sample and less than half the old snap',Math.max(...steps)<12&&Math.max(...steps)<Math.max(...oldSteps)*.5);
check('Run81-85 stays aligned instead of snapping back through a held pose',model.frames.slice(162,171).every(f=>error(f)<1));
// The later run-travel request deliberately changes the left airborne path
// and lets it finish past the old spatial NN exit. Preserve the untouched
// leg/pelvis and actual support timing; verify that new path separately.
check('Right path and pelvis rhythm remain unchanged',model.frames.every((f,i)=>Math.abs(f.pelvisOffset-before.rows[i].pelvis)<1e-9&&R.length(R.sub(f.pose.points[run.names.indexOf('foot_r')],before.rows[i].feet[1].p))<1e-8));
check('All support and release times remain unchanged',model.frames.every((f,i)=>f.feet.every((l,k)=>['PIN','ROLL'].includes(l.state)===['PIN','ROLL'].includes(before.rows[i].feet[k].state))));
check('Every material plant keeps its authored rotation',model.frames.every((f,i)=>f.feet.every((l,k)=>!l.contact||angle(f.pose.q[run.names.indexOf('foot_'+['l','r'][k])],before.rows[i].feet[k].q)<1e-5)));
check('Whole shoes stay clear and legs stay within reach',model.metrics.maxPenetration<1e-5&&model.metrics.maxReachError<1e-5);
check('Reverse seeking preserves the corrected pose',Array.from({length:21},(_,j)=>85-j/2).every(n=>{const a=model.sample(n/60),b=model.frames[Math.round(n*2)];return angle(a.pose.q[foot],b.pose.q[foot])<1e-5;}));
const result={passed:true,checks,frame81:{beforeAnkleErrorDeg:beforeError,afterAnkleErrorDeg:afterError},peakHalfFrameRotation:{before:Math.max(...oldSteps),after:Math.max(...steps)},metrics:model.metrics};
fs.writeFileSync(new URL('run-ankle-verification.json',import.meta.url),JSON.stringify(result,null,2));
console.log(JSON.stringify(result));
