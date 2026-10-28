// Read-only motion diagnostics; saved fixtures use the actual Run-policy Walk NN.
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const rig=read('data/rig.json'),source=read('snapshots/ankle-turn-second-source.json'),settings=read('snapshots/ankle-turn-second-settings.json');
const run=K.decode(source,rig.parents),motion=K.prepare(run,settings),deg=180/Math.PI;
const clamp=x=>Math.max(-1,Math.min(1,x)),dist=(a,b)=>R.length(R.sub(a,b));
const yaw=v=>Math.atan2(v[0],v[2])*deg,wrap=x=>((x+540)%360)-180;
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*deg;
function pole(p,l){
 const axis=R.unit(R.sub(p.points[l.foot],p.points[l.hip])),v=R.sub(p.points[l.knee],p.points[l.hip]);
 const bendVec=R.sub(v,R.mul(axis,R.dot(axis,v))),inverse=R.qinv(p.q[l.pelvis]);
 return {axis:R.rotate(inverse,axis),pole:R.rotate(inverse,R.unit(bendVec)),bend:Math.acos(clamp(R.dot(R.unit(R.sub(p.points[l.knee],p.points[l.hip])),R.unit(R.sub(p.points[l.foot],p.points[l.knee])))))*deg,arm:R.length(bendVec)};
}
function poleStep(a,b){const transported=R.rotate(R.fromTo(a.axis,b.axis),a.pole);return Math.atan2(R.dot(R.cross(transported,b.pole),b.axis),R.dot(transported,b.pole))*deg;}
const rows=[],maxima={},record=(name,value,row)=>{if(!maxima[name]||Math.abs(value)>Math.abs(maxima[name].value))maxima[name]={value,frame:row.frame,side:row.side,state:row.state};};
for(let i=0;i<motion.frames.length;i++)for(let side=0;side<2;side++){
 const f=motion.frames[i],p=f.pose,raw=f.raw,l=S.leg(raw,run.names,side?'R':'L'),shoe=S.footFrame(p,l.foot,l.toe,l.side),nnShoe=S.footFrame(raw,l.foot,l.toe,l.side),actual=pole(p,l),nn=pole(raw,l),foot=f.feet[side];
 const body=R.rotate(p.q[l.pelvis],[0,-1,0]);
 const row={frame:i/2,side:l.side,state:foot.state,influence:f.influence,bodyYaw:yaw(body),footYaw:yaw(shoe.forward),nnYaw:yaw(nnShoe.forward),bodyError:wrap(yaw(shoe.forward)-yaw(body)),nnError:wrap(yaw(shoe.forward)-yaw(nnShoe.forward)),pitch:Math.atan2(shoe.forward[1],shoe.up[1])*deg,up:shoe.up[1],kneeBend:actual.bend,nnKneeBend:nn.bend,poleError:Math.acos(clamp(R.dot(actual.pole,R.rotate(R.fromTo(nn.axis,actual.axis),nn.pole))))*deg};
 if(foot.contact){row.contact=foot.contact;row.materialError=dist(R.add(p.points[l.foot],R.rotate(p.q[l.foot],foot.contact.localPoint)),foot.contact.point);record('pinBodyYaw',row.bodyError,row);record('pinNNYaw',row.nnError,row);record('materialError',row.materialError,row);}
 if(i){
  const prev=motion.frames[i-1],before=pole(prev.pose,l),rawBefore=pole(prev.raw,l);
  row.poleStep=poleStep(before,actual);row.nnPoleStep=poleStep(rawBefore,nn);row.kneeBendStep=actual.bend-before.bend;row.nnKneeBendStep=nn.bend-rawBefore.bend;
  row.poleStepExcess=row.poleStep-row.nnPoleStep;row.footRotationStep=angle(p.q[l.foot],prev.pose.q[l.foot]);
  row.kneePositionStep=dist(p.points[l.knee],prev.pose.points[l.knee]);
  if(actual.arm>.02&&before.arm>.02){record('poleStep',row.poleStep,row);record('nnPoleStep',row.nnPoleStep,row);record('poleStepExcess',row.poleStepExcess,row);record('poleError',row.poleError,row);}
  record('kneeBendStep',row.kneeBendStep,row);record('footRotationStep',row.footRotationStep,row);record('kneePositionStep',row.kneePositionStep,row);
  if(i>1){const prior=rows[rows.length-2];row.poleAcceleration=row.poleStep-prior.poleStep;row.nnPoleAcceleration=row.nnPoleStep-prior.nnPoleStep;if(actual.arm>.02&&before.arm>.02)record('poleAcceleration',row.poleAcceleration,row);}
 }
 rows.push(row);
}
const worst=(key,predicate=()=>true)=>rows.filter(r=>Number.isFinite(r[key])&&predicate(r)).sort((a,b)=>Math.abs(b[key])-Math.abs(a[key])).slice(0,12).map(r=>({frame:r.frame,side:r.side,state:r.state,[key]:r[key],nnPoleStep:r.nnPoleStep,poleStep:r.poleStep,kneeBend:r.kneeBend,nnKneeBend:r.nnKneeBend,poleError:r.poleError,bodyError:r.bodyError}));
const result={fps:motion.fps,count:motion.frames.length,settings,metrics:motion.metrics,maxima,at67:rows.filter(r=>r.frame===67),worstPole:worst('poleStep'),worstAcceleration:worst('poleAcceleration'),worstBend:worst('kneeBendStep'),worstPinnedYaw:worst('bodyError',r=>!!r.contact),rows};
const output=process.argv[2]||'snapshots/yaw-knee-audit.json';
fs.writeFileSync(new URL(output,import.meta.url),JSON.stringify(result,null,2));
console.log(JSON.stringify({...result,rows:undefined},null,2));
