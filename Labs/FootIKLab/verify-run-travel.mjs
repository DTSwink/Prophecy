import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),{load}=require('./test-bank.cjs');
const before=JSON.parse(fs.readFileSync(new URL('data/run-travel-before.json',import.meta.url))),run=load(before.settings.gait,before.settings.phase),model=K.prepare(run,before.settings),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const left=run.names.indexOf('foot_l'),right=run.names.indexOf('foot_r'),pelvis=run.names.indexOf('pelvis');
const local=(i,old=false)=>{const p=model.frames[i].pose,point=old?before.rows[i].feet[0].p:p.points[left];return R.dot(R.sub(point,p.points[pelvis]),R.rotate(p.q[pelvis],[0,-1,0]));};
const localSpeed=(i,old=false)=>(local(i,old)-local(i-1,old))*120;
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
const window=Array.from({length:21},(_,n)=>140+n);
check('Fixture detects backward pelvis-local recovery through78',window.filter(i=>i<=156).every(i=>localSpeed(i,true)<0));
check('70-80 now advances in the moving pelvis frame',window.every(i=>localSpeed(i)>.05));
const progress=(local(160)-local(140))*100,oldProgress=(local(160,true)-local(140,true))*100;
check('70-80 forward progress exceeds15cm instead of retreating',progress>15&&oldProgress<0);
check('Foot begins travelling at departure without a world-space hold',Array.from({length:28},(_,n)=>133+n).every(i=>(model.frames[i].pose.points[left][2]-model.frames[i-1].pose.points[left][2])*120>1.8));
check('Grounded heel-toe and prior left path remain exact',model.frames.slice(0,133).every((f,i)=>R.length(R.sub(f.pose.points[left],before.rows[i].feet[0].p))<1e-8&&angle(f.pose.q[left],before.rows[i].feet[0].q)<1e-5));
check('Right leg and pelvis are unaffected',model.frames.every((f,i)=>R.length(R.sub(f.pose.points[right],before.rows[i].feet[1].p))<1e-8&&angle(f.pose.q[right],before.rows[i].feet[1].q)<1e-5&&Math.abs(f.pelvisOffset-before.rows[i].pelvis)<1e-9));
check('All material contacts and release times are retained',model.frames.every((f,i)=>f.feet.every((l,k)=>Boolean(l.contact)===Boolean(before.rows[i].feet[k].contact))));
const join=model.frames.findIndex((f,i)=>i>170&&f.feet[0].state==='NN');
check('Recovery finishes within the same source swing rather than snapping at terrain exit',join>170&&join<196);
const speed=(i,raw=false)=>R.mul(R.sub(model.frames[i][raw?'raw':'pose'].points[left],model.frames[i-1][raw?'raw':'pose'].points[left]),120);
// Match the outgoing source motion at the join. Its 30Hz key boundary can
// itself change speed; comparing with the preceding NN segment is misleading.
const joinDifference=R.length(R.sub(speed(join),speed(join+1,true)));
check('NN return matches position and velocity',R.length(R.sub(model.frames[join].pose.points[left],model.frames[join].raw.points[left]))<1e-8&&joinDifference<.5);
let maxAddedKick=0,maxFootStep=0;
for(let i=134;i<=join;i++){
 maxAddedKick=Math.max(maxAddedKick,R.length(R.sub(speed(i),speed(i-1)))-R.length(R.sub(speed(i,true),speed(i-1,true))));
 maxFootStep=Math.max(maxFootStep,angle(model.frames[i].pose.q[left],model.frames[i-1].pose.q[left]));
}
check('Continuous recovery avoids velocity or ankle snaps',maxAddedKick<1&&maxFootStep<12);
check('Whole shoe clearance and leg reach remain valid',model.metrics.maxPenetration<1e-5&&model.metrics.maxReachError<1e-5);
check('Reverse seek returns identical recovery poses',Array.from({length:30},(_,k)=>95-k).every(n=>R.length(R.sub(model.sample(n/60).pose.points[left],model.frames[n*2].pose.points[left]))<1e-9));
const result={passed:true,checks,progress70to80Cm:{before:oldProgress,after:progress},joinFrame:join/2,joinVelocityError:joinDifference,maxAddedKick,maxFootStep,metrics:model.metrics};
fs.writeFileSync(new URL('run-travel-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
