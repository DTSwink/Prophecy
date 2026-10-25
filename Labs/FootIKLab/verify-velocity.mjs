import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),{load}=require('./test-bank.cjs');
const checks=[],check=(name,ok)=>{assert(ok,name);checks.push(name);};
// Exclude deliberate contact/ordinary NN stance. Measure full world velocity,
// not only height or foot displacement relative to the moving pelvis.
function stalls(rows){return rows.filter(r=>r.feet.some(f=>f.state==='SWING'&&f.nnV[2]>1.2&&R.length(f.v)<.6*R.length(f.nnV)));}
function trace(run,m){const rows=[];for(let i=1;i<m.frames.length-1;i++){const f=m.frames[i];rows.push({frame:i/2,feet:['L','R'].map((s,k)=>{const j=run.names.indexOf('foot_'+s.toLowerCase());return {side:s,state:f.feet[k].state,point:f.pose.points[j],raw:f.raw.points[j],v:R.mul(R.sub(m.frames[i+1].pose.points[j],m.frames[i-1].pose.points[j]),60),nnV:R.mul(R.sub(m.frames[i+1].raw.points[j],m.frames[i-1].raw.points[j]),60),penetration:f.feet[k].penetration};})});}return rows;}
const before=JSON.parse(fs.readFileSync(new URL('data/velocity-phase49-before.json',import.meta.url))),run=load('walk',.49),m=K.prepare(run,{phase:.49}),after=trace(run,m);
const window=(rows,a,b)=>rows.filter(r=>r.frame>=a&&r.frame<=b);
const oldStalls=stalls(window(before.rows,172,181)),newStalls=stalls(window(after,172,181));
check('Measured old exit stall is detected from whole foot velocity',oldStalls.length>=3);
check('Saved phase49 exit no longer waits for NN motion',newStalls.length===0);
const lift=rows=>Math.max(...window(rows,40,48).map(r=>r.feet[1].v[1]));
check('Saved phase49 first riser has no upward velocity spike',lift(after)<1.2&&lift(after)<lift(before.rows)*.3);
const peakY=rows=>Math.max(...window(rows,28,56).map(r=>r.feet[1].point[1]));
check('Smoothing does not inflate the first swing clearance dome',peakY(after)<=peakY(before.rows)+.005);
const acceleration=window(after,32,50).map((r,i,arr)=>i?Math.abs(r.feet[1].v[1]-arr[i-1].feet[1].v[1]):0);
check('First riser vertical speed changes continuously',Math.max(...acceleration)<.25);
check('Entry forward movement stays close to NN',window(after,34,50).every(r=>Math.abs(r.feet[1].v[2]-r.feet[1].nnV[2])<.5));
// Early reach release deliberately departs from NN stance timing; compare
// speed at the handoff rather than requiring the same path throughout recovery.
const handoff=m.frames.findIndex(f=>f.root[2]>=m.terrain.end&&f.influence===0)/2;
check('Forward recovery joins NN speed at the completed foot handoff',window(after,handoff,handoff+1).every(r=>Math.abs(r.feet[0].v[2]-r.feet[0].nnV[2])<.5));
check('Saved phase49 full course soles clear terrain',m.metrics.maxPenetration<1e-5);
check('Saved phase49 full course targets remain reachable',m.metrics.maxReachError<1e-5);
check('World root velocity remains the source 2m/s',m.frames.slice(1).every((f,i)=>Math.abs((f.root[2]-m.frames[i].root[2])*120-2)<.002));
const phaseResults=[];
for(const phase of [0,.25,.49,.75]){const r=load('walk',phase),p=K.prepare(r,{phase}),rows=trace(r,p),exit=rows.filter(x=>x.frame>=172&&x.frame<=181);phaseResults.push({phase,stalls:stalls(exit).map(x=>x.frame),maxPenetration:p.metrics.maxPenetration});check('Phase '+phase+' exit has no artificial velocity stall',!stalls(exit).length);check('Phase '+phase+' clears all soles',p.metrics.maxPenetration<1e-5);}
const result={passed:true,checks,measured:{beforeStallFrames:oldStalls.map(r=>r.frame),afterStallFrames:newStalls.map(r=>r.frame),beforePeakUpSpeed:lift(before.rows),afterPeakUpSpeed:lift(after),beforePeakHeight:peakY(before.rows),afterPeakHeight:peakY(after),phaseResults}};
fs.writeFileSync(new URL('velocity-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
