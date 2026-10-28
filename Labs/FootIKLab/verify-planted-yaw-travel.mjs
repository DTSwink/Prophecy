// Actual motion quality regression for the reported rotating Walk departure.
// Contact/clearance correctness alone did not catch a near-stationary swing.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),rig=read('data/rig.json'),data=read('snapshots/ankle-turn-second-source.json'),settings=read('snapshots/ankle-turn-second-settings.json'),run=K.decode(data,rig.parents),m=K.prepare(run,settings),deg=180/Math.PI;
const checks=[],failures=[],check=(name,ok,value)=>{checks.push(name);if(!ok)failures.push({name,value});},angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*deg;
const leg=side=>S.leg(m.frames[0].pose,run.names,side?'R':'L'),legs=[leg(0),leg(1)],point=(i,s)=>m.frames[i].pose.points[legs[s].foot],v=(i,s)=>R.mul(R.sub(point(i,s),point(i-1,s)),120);
const start=144,end=164,travel=point(end,1)[2]-point(start,1)[2],minimum=Math.min(...m.frames.slice(start+1,end+1).map((_,j)=>v(start+1+j,1)[2])),at82=v(end,1);
check('72-82 right foot advances at least25cm along root course',travel>.25,travel);
check('72-82 right foot has no low-speed horizontal stall',minimum>.8,minimum);
check('82 right foot gains course-forward ground on moving root',at82[2]>m.speed,at82[2]-m.speed);
let maxFootStep=0,maxLegStep=0,materialError=0;
for(let i=1;i<m.frames.length;i++)for(let s=0;s<2;s++){
 const f=m.frames[i],p=m.frames[i-1],l=legs[s];maxFootStep=Math.max(maxFootStep,angle(f.pose.q[l.foot],p.pose.q[l.foot]));
 for(const bone of[l.hip,l.knee])maxLegStep=Math.max(maxLegStep,angle(f.pose.q[bone],p.pose.q[bone]));
 const c=f.feet[s].contact;if(c)materialError=Math.max(materialError,R.length(R.sub(R.add(point(i,s),R.rotate(f.pose.q[l.foot],c.localPoint)),c.point)));
}
const swings=[];
for(let s=0;s<2;s++)for(let a=0;a<m.frames.length-2;a++){
 const c=m.frames[a].feet[s].contact;if(!c||m.frames[a+1].feet[s].contact)continue;
 let b=a+1;while(b<m.frames.length-1&&!m.frames[b].feet[s].contact&&m.frames[b].feet[s].state!=='NN')b++;
 const from=point(a,s),to=point(b,s);if(!c.yaw||to[1]<=from[1]+.005||to[2]<=from[2]+.05)continue;
 const earlyEnd=Math.min(b,a+24),early=Array.from({length:earlyEnd-a},(_,j)=>v(a+1+j,s)),at40=Math.round(a+(b-a)*.4),d40=R.sub(point(at40,s),from),shoe=S.footFrame(m.frames[a].pose,legs[s].foot,legs[s].toe,s?'R':'L');
 swings.push({side:s?'R':'L',release:a/2,land:b/2,toeOffPitch:Math.atan2(shoe.forward[1],shoe.up[1])*deg,earlyUpPeak:Math.max(...early.map(d=>d[1])),earlyForwardPeak:Math.max(...early.map(d=>d[2])),first40Course:d40[2],first40RootRelative:d40[2]-m.speed*(at40-a)/120});a=b-1;
}
const reported=swings.find(s=>s.side==='R'&&s.release>=60&&s.release<=70);
check('reported departure identified',!!reported,swings);
check('reported departure keeps grounded toe-down push-off',reported&&reported.toeOffPitch<-8,reported?.toeOffPitch);
// Previously1.74m/s without pin-yaw; old turned path reached3.65m/s at69.5.
// Keep riser anticipation covered alongside forward travel: both must stay smooth.
check('reported departure avoids violent early vertical kick',reported&&reported.earlyUpPeak<2.5,reported?.earlyUpPeak);
check('full clip has no new ankle snap',maxFootStep<10,maxFootStep);
check('full clip has no new hip/knee snap',maxLegStep<7,maxLegStep);
check('whole shoe clearance maintained',m.metrics.maxPenetration<1e-5,m.metrics.maxPenetration);
check('whole clip reach retained',m.metrics.maxReachError<1e-6,m.metrics.maxReachError);
check('actual material pins retained',materialError<1e-7,materialError);
const result={passed:!failures.length,checks:checks.length,failures,travel72to82:travel,minCourseSpeed72to82:minimum,velocity82:at82,maxFootStep,maxLegStep,materialError,metrics:m.metrics,swings};
fs.writeFileSync(new URL('snapshots/yaw-knee-travel-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
assert.equal(failures.length,0,JSON.stringify(failures));
