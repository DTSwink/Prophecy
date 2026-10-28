import fs from 'node:fs';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),H=require('./handoff.js'),R=require('./recovery.js'),S=require('./support.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const run=K.decode(read('snapshots/flat-knee-phase60-source.json'),read('data/rig.json').parents);
const settings={gait:'walk',phase:.6,terrain:'stairs',height:16,depth:35,steps:12,enabled:true,clearance:1,pelvis:30,direction:'forward',rootYawSpeed:300,rootYawStart:1.2,rootYawStop:6,footYawLimit:45};
const original=K.prepare(run,settings),plan=H.requestFor(original,run);
if(process.argv.includes('--reference'))plan.request.verifyReference=true;
const response=await fetch('http://127.0.0.1:8890/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(plan.request)});
if(!response.ok)throw Error(await response.text());
const data=await response.json();fs.writeFileSync(new URL('snapshots/knee-225-continuation.json',import.meta.url),JSON.stringify(data));
const model=H.apply(original,run,plan,data),continuation=K.decode(data,run.parents),deg=180/Math.PI;
const angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(a),R.unit(b)))))*deg;
const flex=(p,l)=>angle(R.sub(p.points[l.knee],p.points[l.hip]),R.sub(p.points[l.foot],p.points[l.knee]));
const rows=[];
for(let n=218;n<=232;n+=.5){const f=model.sample(n/60),prev=model.sample((n-.5)/60),u=original.sample(n/60);rows.push({frame:n,exactNN:JSON.stringify(f.pose)===JSON.stringify(f.raw),feet:['L','R'].map(side=>{const l=S.leg(f.raw,run.names,side);return {side,flex:flex(f.pose,l),sourceWithoutTerrain:flex(u.raw,l),kneePoint:f.pose.points[l.knee],deltaKnee:R.length(R.sub(f.pose.points[l.knee],prev.pose.points[l.knee])),calfRotation:2*Math.acos(Math.min(1,Math.abs(R.dot(f.pose.q[l.knee],prev.pose.q[l.knee]))))*deg};})});}
const result={handoff:model.handoff,cache:data.cache,referenceError:data.referenceError,windowReferenceError:data.windowReferenceError,pinDiagnostics:data.pinDiagnostics,rows,policyFrames:continuation.poses.map((p,i)=>({frame:plan.time*60+i*2,feet:['L','R'].map(side=>({side,flex:flex(p,S.leg(p,run.names,side))}))})).filter(f=>f.frame>=218&&f.frame<=232)};
fs.writeFileSync(new URL('snapshots/knee-225-audit.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
