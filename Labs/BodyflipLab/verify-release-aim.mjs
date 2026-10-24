import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('./flight.js'),C=require('./core.js'),R=require('./recovery.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),jumps=read('data/jumps.json').clips.map(F.decodeJump),checks=[],measurements=[];
const angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(a),R.unit(b)))))*180/Math.PI;
for(const gait of ['run','walk'])for(const foot of ['L','R'])for(const flip of [0,40]){
 const run=F.decodeNN(read('data/'+gait+'-default-drawn.json')),f=F.create(run,jumps,{...C.defaults,matchLeg:false,mode:gait==='walk'?'walk':'jump',jumpFoot:foot,jumpBlend:1,supportAlpha:.03},m.parents,C.poseFromShared(m)),l=f.support.leg;
 const atRelease=f.sample(f.airStart).pose,frozenDirection=R.sub(atRelease.points[l.foot],atRelease.points[l.hip]);
 const frame=f.sample(f.airStart+.05,flip),p=frame.pose,toTarget=R.sub(f.support.terminal.foot,p.points[l.hip]),direction=R.sub(p.points[l.foot],p.points[l.hip]);
 const error=angle(direction,toTarget),frozenError=angle(frozenDirection,toTarget),name=[gait,foot,flip].join('/');
 assert.equal(frame.supportState,'BLEND',name);checks.push(name+' exercising release blend');
 assert(error<1.5,name+' current leg must aim at target, error='+error);checks.push(name+' live target alignment');
 if(!flip){assert(error<frozenError*.25,name+' must improve over frozen release pose');checks.push(name+' rejects frozen pose regression');}
 const upper=R.length(R.sub(p.points[l.hip],p.points[l.knee])),lower=R.length(R.sub(p.points[l.knee],p.points[l.foot]));
 assert(Math.abs(upper-l.upper)<1e-5&&Math.abs(lower-l.lower)<1e-5,name+' lengths');checks.push(name+' no leg stretching');
 measurements.push({gait,foot,flip,error,frozenError});
}
fs.writeFileSync(new URL('release-aim-verification.json',import.meta.url),JSON.stringify({passed:true,checks,measurements},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
