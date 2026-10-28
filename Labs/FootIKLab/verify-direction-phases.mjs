// Read-only core review of alternate phases from genuine5s directional NN runs.
import fs from 'node:fs';import {createHash} from 'node:crypto';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),{audit}=require('./motion-audit.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),rig=read('data/rig.json'),checks=[],cases=[],failures=[];
const check=(name,ok,measured)=>{const row={name,passed:!!ok,measured};checks.push(row);if(!ok)failures.push(row);};
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
for(const gait of ['walk','run'])for(const direction of ['backward','left','right']){
 const data=read('.nn-cache/directional-phase-'+gait+'-'+direction+'.json'),run=K.decode(data,rig.parents),phase=data.phase,prefix=gait+'/'+direction+'/'+phase;
 check(prefix+' actual5s directional source',data.duration===5&&data.poses.length===152&&data.lowerInferences>0&&data.upperInferences>0&&data.command.direction===direction&&data.source.includes('autoregressive'),{source:data.source,sourceSha:data.command.sourceSha256});
 for(const terrain of ['flat','stairs','down','uneven']){
  const m=K.prepare(run,{gait,direction,phase,terrain,clearance:1,height:16,depth:35,steps:12}),a=audit({run,model:m,options:{geometry:false}}),label=prefix+'/'+terrain;
  let pin=0,pinSlide=0,pins=0,penetration=0,rootError=0,nnExact=true,bone=0,step=0,move=0,stepAt=null,moveAt=null,penAt=null;
  const anchors=new Map();
  for(let i=0;i<m.frames.length;i++){
   const f=m.frames[i];if(f.influence===0)nnExact&&=JSON.stringify(f.pose)===JSON.stringify(f.raw);
   rootError=Math.max(rootError,Math.abs(f.root[1]-m.terrain.rootHeight(f.root[2])));
   for(let side=0;side<2;side++){
    const l=S.leg(f.raw,run.names,side?'R':'L'),p=f.pose.points,foot=f.feet[side],c=foot.contact;
    for(const[parent,child]of[[l.hip,l.knee],[l.knee,l.foot],[l.foot,l.toe]])bone=Math.max(bone,Math.abs(distance(p[parent],p[child])-distance(f.raw.points[parent],f.raw.points[child])));
    if(foot.state!=='NN'){const x=m.terrain.floorFor(p[l.foot],S.footPoints(f.pose,l.foot,l.toe,l.side))-p[l.foot][1];if(x>penetration){penetration=x;penAt={frame:i/2,side:l.side,state:foot.state};}}
    if(c){pins++;pin=Math.max(pin,distance(R.add(p[l.foot],R.rotate(f.pose.q[l.foot],c.localPoint)),c.point));const key=c.stanceId+':'+c.pivotKey;if(anchors.has(key))pinSlide=Math.max(pinSlide,distance(c.point,anchors.get(key)));else anchors.set(key,c.point);}
    if(i)for(const j of[l.hip,l.knee,l.foot,l.toe]){const prev=m.frames[i-1],turn=angle(f.pose.q[j],prev.pose.q[j]),travel=distance(p[j],prev.pose.points[j]);if(turn>step){step=turn;stepAt={frame:i/2,bone:run.names[j],state:foot.state,source:angle(f.raw.q[j],prev.raw.q[j])};}if(travel>move){move=travel;moveAt={frame:i/2,bone:run.names[j],state:foot.state,source:distance(f.raw.points[j],prev.raw.points[j])};}}
   }
  }
  const knee=Math.max(a.summary.L.kneePoleStep.value,a.summary.R.kneePoleStep.value);
  check(label+' finite poses',m.frames.every(f=>[...f.pose.points.flat(),...f.pose.q.flat()].every(Number.isFinite)));
  check(label+' exact NN before and after corrections',nnExact);
  check(label+' source bone lengths',bone<1e-6,bone);
  check(label+' root ramp',rootError<1e-5,rootError);
  check(label+' whole-shoe clearance',penetration<1e-5,{penetration,penAt});
  check(label+' reachable targets',m.metrics.maxReachError<1e-5,m.metrics.maxReachError);
  check(label+' real material contact',pin<1e-6,pin);
  check(label+' no material slide',pinSlide<1e-6,pinSlide);
  check(label+' knee pole continuity',knee<15,knee);
  check(label+' leg and ankle angular continuity',step<(gait==='walk'?15:20),{step,stepAt});
  check(label+' no limb teleport',move<(gait==='walk'?.09:.14),{move,moveAt});
  check(label+' contact or pure NN on flat',terrain==='flat'?pins===0:pins>10,pins);
  check(label+' bounded pelvis',m.metrics.maxPelvis<=.300001,m.metrics.maxPelvis);
  cases.push({gait,direction,phase,terrain,pin,pinSlide,pins,penetration,penAt,bone,knee,step,stepAt,move,moveAt,rootError,sourceSha256:data.command.sourceSha256});
 }
}
const result={passed:!failures.length,checks,failures,cases,scope:'24 full5s procedural clips from six additional genuine NN phase fixtures; no terminal1.5s truncation, no server or inference work.',coreSha256:createHash('sha256').update(fs.readFileSync(new URL('footik.js',import.meta.url))).digest('hex')};
fs.writeFileSync(new URL('direction-phase-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:result.passed,checks:checks.length,cases:cases.length,failures}));if(failures.length)process.exitCode=1;
