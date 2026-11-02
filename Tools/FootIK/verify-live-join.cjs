'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const K=require('../../Labs/FootIKLab/footik.js'),J=require('./live-join.cjs'),R=require('../../Labs/FootIKLab/recovery.js');
const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),input=JSON.parse(fs.readFileSync(path.join(folder,'walk-stairs.input.json'))),run=K.decode(input.source,input.parents);
const model=K.prepare(run,input.settings),start=performance.now(),cpu=process.cpuUsage();let identity=0,upperOnly=0,pins=0,maxPinError=0,maxLengthError=0;
for(const frame of model.frames){
 const result=J.join({candidate:frame,current:frame.raw,parents:input.parents,names:run.names});assert(result.identity);assert.equal(result.frame,frame);identity++;
 const upper=structuredClone(frame.raw);upper.q[run.names.indexOf('upperarm_l')]=R.qm(R.qexp([.04,0,0]),upper.q[run.names.indexOf('upperarm_l')]);
 const joined=J.join({candidate:frame,current:upper,parents:input.parents,names:run.names});
 for(const name of ['thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r']){const j=run.names.indexOf(name);assert.deepEqual(joined.frame.pose.points[j],frame.pose.points[j]);assert.deepEqual(joined.frame.pose.q[j],frame.pose.q[j]);}
 assert.deepEqual(joined.frame.pose.q[run.names.indexOf('upperarm_l')],upper.q[run.names.indexOf('upperarm_l')]);upperOnly++;
 if(frame.influence<.99||!frame.feet.some(f=>f.contact))continue;
 const actual=structuredClone(frame.raw);for(let j=1;j<26;j++)actual.points[j][0]+=.002;
 const moved=J.join({candidate:frame,current:actual,parents:input.parents,names:run.names,contacts:frame.feet.map(f=>f.contact)});
 for(let side=0;side<2;side++){
  const l=K.stableLeg(actual,run.names,side?'R':'L'),p=moved.frame.pose.points;
  maxLengthError=Math.max(maxLengthError,Math.abs(R.length(R.sub(p[l.hip],p[l.knee]))-l.upper),Math.abs(R.length(R.sub(p[l.knee],p[l.foot]))-l.lower));
  if(frame.feet[side].contact&&moved.frame.feet[side].contact){pins++;maxPinError=Math.max(maxPinError,moved.pinErrors[side]);}
 }
}
assert(maxPinError<1e-8,'pin drift '+maxPinError);assert(maxLengthError<1e-8);assert(pins>0);
const used=process.cpuUsage(cpu),report={passed:true,identityFrames:identity,upperOnlyFrames:upperOnly,activePinSamples:pins,maxPinErrorM:maxPinError,maxBoneLengthErrorM:maxLengthError,joinCpuMilliseconds:(used.user+used.system)/1000,joinWallMilliseconds:performance.now()-start,note:'Two-millimetre actual lower-pose translation plus different upper-NN rotation. This tests publication invariants, not large abrupt player-command visual quality.'};
fs.writeFileSync(path.join(folder,'live-join.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
