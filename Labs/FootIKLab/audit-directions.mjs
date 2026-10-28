import fs from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {writeReport} from './motion-audit.mjs';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),{audit}=require('./motion-audit.js');
const rig=JSON.parse(fs.readFileSync(new URL('data/rig.json',import.meta.url))),findings=[];
const deg=x=>x*180/Math.PI,round=x=>Number.isFinite(x)?+x.toFixed(4):null;
for(const gait of ['walk','run'])for(const direction of ['backward','left','right']){
 const data=JSON.parse(fs.readFileSync(new URL('.nn-cache/directional-'+gait+'-'+direction+'.json',import.meta.url))),run=K.decode(data,rig.parents),model=K.prepare(run,{gait,direction,phase:.21,terrain:'stairs',height:16,depth:35,steps:12,clearance:1}),report=audit({run,model});
 report.metadata.directionalCommand=data.command;
 writeReport(report,fileURLToPath(new URL('snapshots/direction-audit-'+gait+'-'+direction,import.meta.url)));
 const detail=(i,side)=>{
  const f=model.frames[i],l=S.leg(f.pose,run.names,side?'R':'L'),ff=S.footFrame(f.pose,l.foot,l.toe,l.side),raw=S.footFrame(f.raw,l.foot,l.toe,l.side),c=f.feet[side].contact;
  const sole=S.footPoints(f.pose,l.foot,l.toe,l.side).map(v=>R.dot(v,ff.forward)),front=Math.max(...sole),back=Math.min(...sole),pivot=c?R.dot(R.sub(c.point,f.pose.points[l.foot]),ff.forward):null;
  return {frame:i/2,state:f.feet[side].state,pitch:round(deg(Math.asin(Math.max(-1,Math.min(1,ff.forward[1]))))),nnPitch:round(deg(Math.asin(Math.max(-1,Math.min(1,raw.forward[1]))))),anatomicalForwardTravelDot:round(R.dot(R.unit([ff.forward[0],0,ff.forward[2]]),[0,0,1])),nnAnatomicalForwardTravelDot:round(R.dot(R.unit([raw.forward[0],0,raw.forward[2]]),[0,0,1])),
   pivotFraction:pivot===null?null:round((pivot-back)/(front-back)),ankleZ:round(f.pose.points[l.foot][2]),ankleY:round(f.pose.points[l.foot][1]),nnAnkleZ:round(f.raw.points[l.foot][2]),nnAnkleY:round(f.raw.points[l.foot][1]),ankleNN:report.rows[i].feet[side].ankleNNError,pelvisProgress:report.rows[i].feet[side].pelvisProgress,nnPelvisProgress:report.rows[i].feet[side].nnPelvisProgress};
 };
 const feet=[];
 for(let side=0;side<2;side++){
  const spans=[];for(let i=0;i<model.frames.length;i++)if(model.frames[i].feet[side].contact){const a=i,id=model.frames[i].feet[side].contact.stanceId;while(i+1<model.frames.length&&model.frames[i+1].feet[side].contact?.stanceId===id)i++;spans.push({first:detail(a,side),last:detail(i,side),after:detail(Math.min(i+2,model.frames.length-1),side)});}
  const peak=Math.round(report.summary[side?'R':'L'].ankleNNError.frame*2),nearPeak=[];for(let i=Math.max(0,peak-8);i<=Math.min(model.frames.length-1,peak+8);i+=2)nearPeak.push(detail(i,side));
  feet.push({side:side?'R':'L',spans,nearPeak,summary:report.summary[side?'R':'L']});
 }
 findings.push({gait,direction,source:data.source,referenceError:data.referenceError,speed:run.directionMeta.commandSpeed,metrics:model.metrics,feet});
}
fs.writeFileSync(new URL('snapshots/direction-findings.json',import.meta.url),JSON.stringify(findings,null,2));
console.log(JSON.stringify(findings.map(r=>({gait:r.gait,direction:r.direction,feet:r.feet.map(f=>({side:f.side,spans:f.spans.map(s=>({first:s.first.frame,last:s.last.frame,pitch:s.last.pitch,nnPitch:s.last.nnPitch,pivot:s.last.pivotFraction,direction:s.last.anatomicalForwardTravelDot})),peak:f.nearPeak[4]}))})),null,2));
