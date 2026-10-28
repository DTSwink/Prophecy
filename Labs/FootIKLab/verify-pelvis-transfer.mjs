import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),S=require('./support.js'),R=require('./recovery.js'),{load}=require('./test-bank.cjs');
const before=JSON.parse(fs.readFileSync(new URL('data/pelvis-transfer-before.json',import.meta.url))),run=load(before.settings.gait,before.settings.phase),checks=[];
const start=performance.now(),m=K.prepare(run,before.settings),prepareMs=performance.now()-start;
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))));
let ankleError=0,rootError=0,pinAngle=0,extraExtension=0,stateChanges=0;
for(let i=0;i<m.frames.length;i++){
 const f=m.frames[i],old=before.rows[i];rootError=Math.max(rootError,distance(f.root,old.root));
 for(let side=0;side<2;side++){
  const l=S.leg(f.raw,run.names,side?'R':'L'),foot=f.feet[side];
  ankleError=Math.max(ankleError,distance(f.pose.points[l.foot],old.feet[side].p));
  if(foot.state!==old.feet[side].state)stateChanges++;
  if(foot.contact)pinAngle=Math.max(pinAngle,angle(f.pose.q[l.foot],old.feet[side].q),angle(f.pose.q[l.toe],old.feet[side].toeQ));
  const oldHip=R.add(f.raw.points[l.hip],[0,old.offset,0]);
  extraExtension=Math.max(extraExtension,distance(f.pose.points[l.hip],f.pose.points[l.foot])-distance(oldHip,old.feet[side].p));
 }
}
const offsets=m.frames.map(f=>f.pelvisTransfer||0),v=offsets.map((y,i)=>i?(y-offsets[i-1])*m.fps:0);
const maxSpeed=Math.max(...v.map(Math.abs)),maxAcceleration=Math.max(...v.slice(1).map((x,i)=>Math.abs(x-v[i])*m.fps));
check('Root ramp is unchanged',rootError<1e-9);
check('Both accepted ankle paths and velocities are retained',ankleError<1e-8);
check('All toe-off and landing states retain their timing',stateChanges===0);
check('Planted foot and toe orientation stay unchanged',pinAngle<1e-6);
check('Body rhythm never extends either leg farther',extraExtension<1e-7);
check('Current stairs have a visible but bounded loading accent',Math.min(...offsets)<-.025&&Math.min(...offsets)>-.05&&Math.max(...offsets)<1e-6);
check('Pelvis transfer remains smooth in speed and acceleration',maxSpeed<.3&&maxAcceleration<4);
check('Both middle steps slow through loading then rise faster during pull-up',[[99,114],[128.5,144]].every(([load,pull])=>v[Math.round(load*2)]<-.15&&v[Math.round(pull*2)]>.15));
check('Foot geometry stays clear and reachable',m.metrics.maxPenetration<1e-5&&m.metrics.maxReachError<1e-5);
check('Flat approach and exit are still exact NN',m.frames.filter(f=>f.influence===0).every(f=>f.pose===f.raw));
const saved=JSON.stringify(m.sample(2));m.sample(4);m.sample(.1);check('Body trajectory is deterministic while seeking',JSON.stringify(m.sample(2))===saved);
const result={passed:true,checks,prepareMs,ankleError,rootError,pinAngle,extraExtension,peakLoadingCm:-Math.min(...offsets)*100,maxSpeed,maxAcceleration};
fs.writeFileSync(new URL('pelvis-transfer-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
