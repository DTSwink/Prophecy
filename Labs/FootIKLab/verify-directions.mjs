import fs from 'node:fs';
import path from 'node:path';
import {createRequire,Module} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),{audit}=require('./motion-audit.js');
const dir=fileURLToPath(new URL('.',import.meta.url)),read=n=>JSON.parse(fs.readFileSync(path.join(dir,n),'utf8')),rig=read('data/rig.json'),checks=[],cases=[],failures=[];
const check=(name,ok,measured)=>{const row={name,passed:!!ok};if(measured!==undefined)row.measured=measured;checks.push(row);if(!ok)failures.push(row);};
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
const hash=b=>createHash('sha256').update(b).digest('hex'),coreText=fs.readFileSync(path.join(dir,'footik.js'),'utf8');
const beforeText=fs.readFileSync(path.join(dir,'.nn-cache/footik-before-directions.txt'),'utf8'),beforeModule=new Module(path.join(dir,'footik-before-probe.js'));
beforeModule.filename=path.join(dir,'footik-before-probe.js');beforeModule.paths=Module._nodeModulePaths(dir);beforeModule._compile(beforeText,beforeModule.filename);const Before=beforeModule.exports;
let backwardWalk=null;
for(const gait of ['walk','run'])for(const direction of ['backward','left','right']){
 const sourcePath='.nn-cache/directional-'+gait+'-'+direction+'.json',sourceText=fs.readFileSync(path.join(dir,sourcePath),'utf8'),data=JSON.parse(sourceText),run=K.decode(data,rig.parents),prefix=gait+'/'+direction;
 check(prefix+' preserves genuine directional NN provenance',data.source==='matching omni seed + autoregressive lower/upper NN'&&data.lowerInferences>0&&data.upperInferences>0&&data.referenceError<2e-6&&!!data.command.sourceSha256,{source:data.source,referenceError:data.referenceError});
 check(prefix+' decodes command heading and direction rather than rotating a forward bank',run.direction===direction&&run.directionMeta.direction===direction&&run.directionMeta.sourceSha256===data.command.sourceSha256);
 const frozen=JSON.stringify(run.poses);
 for(const terrain of ['flat','stairs','down','uneven']){
  const settings={gait,direction,phase:.21,terrain,height:16,depth:35,steps:12,clearance:1},m=K.prepare(run,settings),a=audit({run,model:m,options:{geometry:false}}),label=prefix+'/'+terrain;
  let bone=0,pin=0,pinSlide=0,pinPairs=0,pins=0,footStep=0,allLegStep=0,positionStep=0,toeLocal=0,penetration=0,reachError=0,rootError=0,nnFrames=0,sourceStep=0,nnExact=true,stepLocation=null,positionLocation=null,penetrationLocation=null;
  for(let i=0;i<m.frames.length;i++){
   const f=m.frames[i];if(f.influence===0){nnFrames++;nnExact&&=f.pose===f.raw||JSON.stringify(f.pose)===JSON.stringify(f.raw);}
   rootError=Math.max(rootError,Math.abs(f.root[1]-m.terrain.rootHeight(f.root[2])));
   for(let side=0;side<2;side++){
    const l=S.leg(f.raw,run.names,side?'R':'L'),p=f.pose.points,c=f.feet[side].contact;
    for(const [parent,child]of [[l.hip,l.knee],[l.knee,l.foot],[l.foot,l.toe]])bone=Math.max(bone,Math.abs(distance(p[parent],p[child])-distance(f.raw.points[parent],f.raw.points[child])));
    if(f.feet[side].state!=='NN'){const gap=m.terrain.floorFor(p[l.foot],S.footPoints(f.pose,l.foot,l.toe,l.side))-p[l.foot][1];if(gap>penetration){penetration=gap;penetrationLocation={frame:i/2,side:l.side,state:f.feet[side].state};}}
    reachError=Math.max(reachError,distance(p[l.foot],f.feet[side].target));
    if(c){pins++;pin=Math.max(pin,distance(R.add(p[l.foot],R.rotate(f.pose.q[l.foot],c.localPoint)),c.point));
     if(i){const prior=m.frames[i-1].feet[side].contact;
      if(prior?.stanceId===c.stanceId){const pq=m.frames[i-1].pose.q;toeLocal=Math.max(toeLocal,angle(R.qm(R.qinv(f.pose.q[l.foot]),f.pose.q[l.toe]),R.qm(R.qinv(pq[l.foot]),pq[l.toe])));
       if(prior.pivotKey===c.pivotKey){pinPairs++;pinSlide=Math.max(pinSlide,distance(c.point,prior.point));}
      }
     }
    }
    if(i){const previous=m.frames[i-1];for(const j of [l.hip,l.knee,l.foot,l.toe]){const step=angle(f.pose.q[j],previous.pose.q[j]),move=distance(p[j],previous.pose.points[j]);if(step>allLegStep){allLegStep=step;stepLocation={frame:i/2,bone:run.names[j],state:f.feet[side].state,previousState:previous.feet[side].state,sourceAngle:angle(f.raw.q[j],previous.raw.q[j])};}if(move>positionStep){positionStep=move;positionLocation={frame:i/2,bone:run.names[j],state:f.feet[side].state,previousState:previous.feet[side].state,sourceMove:distance(f.raw.points[j],previous.raw.points[j])};}sourceStep=Math.max(sourceStep,angle(f.raw.q[j],previous.raw.q[j]));}footStep=Math.max(footStep,angle(f.pose.q[l.foot],previous.pose.q[l.foot]));}
   }
  }
  const knee=Math.max(a.summary.L.kneePoleStep?.value||0,a.summary.R.kneePoleStep?.value||0),finite=m.frames.every(f=>f.pose.points.flat().every(Number.isFinite)&&f.pose.q.flat().every(Number.isFinite));
  check(label+' finite pose and source remains immutable',finite&&JSON.stringify(run.poses)===frozen);
  check(label+' uncorrected approach/exit samples remain exact NN',nnExact&&nnFrames>0,{nnExact,nnFrames});
  check(label+' current-source bone lengths retained',bone<1e-6,bone);
  check(label+' commanded root remains on terrain ramp',rootError<1e-5,rootError);
  check(label+' corrected whole-shoe geometry clears finite treads',penetration<1e-5,penetration);
  check(label+' corrected ankle targets remain reachable',reachError<1e-5,reachError);
  check(label+' bounded pelvis adjustment',m.metrics.maxPelvis<=.300001,m.metrics.maxPelvis);
  check(label+' material heel/toe pivot is on its intended surface',pin<1e-6,pin);
  check(label+' retained material pivot does not slide',pinSlide<1e-6,pinSlide);
  check(label+' contact shoe retains local toe articulation',toeLocal<1e-4,toeLocal);
  check(label+' knee bend plane has no reversal away from extension',knee<15,knee);
  check(label+' no leg or ankle orientation flip',allLegStep<(gait==='walk'?15:20),{allLegStep,footStep,sourceStep,stepLocation});
  check(label+' no limb teleport at120Hz',positionStep<(gait==='walk'?.09:.14),{positionStep,positionLocation});
  check(label+' terrain contacts exist or flat clip is exact NN',terrain==='flat'?nnFrames===m.frames.length&&pins===0:pins>10&&pinPairs>5,{pins,pinPairs,nnFrames});
  const seek=[0,2.75,1.2,4.9,.5].map(t=>JSON.stringify(m.sample(t)));check(label+' reverse seek preserves deterministic poses',[.5,4.9,1.2,2.75,0].every((t,j)=>JSON.stringify(m.sample(t))===seek[4-j]));
  cases.push({gait,direction,terrain,sourceSha256:hash(sourceText),measurements:{bone,pin,pinSlide,pinPairs,pins,footStep,allLegStep,positionStep,toeLocal,penetration,reachError,rootError,nnFrames,knee,stepLocation,positionLocation,penetrationLocation},worstIntervals:a.worstIntervals.filter(w=>w.peakFrame/60<(m.terrain.end/m.speed)).slice(0,6)});
  if(gait==='walk'&&direction==='backward'&&terrain==='stairs')backwardWalk={run,settings,model:m};
 }
}
const old=Before.prepare(backwardWalk.run,backwardWalk.settings),now=backwardWalk.model,foot=backwardWalk.run.names.indexOf('foot_l');
const pitch=(m,frame)=>{const p=m.sample(frame/60).pose,l=S.leg(p,backwardWalk.run.names,'L');return Math.asin(Math.max(-1,Math.min(1,S.footFrame(p,l.foot,l.toe,'L').forward[1])))*180/Math.PI;};
const beforePitch=pitch(old,132.5),afterPitch=pitch(now,132.5),oldQ=old.sample(132.5/60).pose.q[foot],newQ=now.sample(132.5/60).pose.q[foot];
check('Backward Walk132.5 reduces excessive toe-down by at least10degrees',afterPitch-beforePitch>10,{beforePitch,afterPitch});
check('Backward Walk132.5 still rolls on a real material contact',!!now.sample(132.5/60).feet[0].contact&&now.sample(132.5/60).feet[0].state==='ROLL');
check('Backward roll correction preserves root trajectory',now.frames.every((f,i)=>distance(f.root,old.frames[i].root)<1e-9));
const result={passed:failures.length===0,scope:'Six genuine directional NN fixtures, four terrain modes; procedural core before eventual NN handoff. Numeric checks do not replace rendered inspection.',sourceSha256:hash(coreText),beforeSourceSha256:hash(beforeText),checks,failures,cases,backward132_5:{beforePitch,afterPitch,rotationChange:angle(oldQ,newQ)},visualFrames:[{gait:'walk',direction:'backward',frames:[112,124,128,132.5,133,137,141,196]},{gait:'run',direction:'backward',frames:[50,55,57,61,65,77,84]},{gait:'walk',direction:'left',frames:[74,78,82,86,196,200]},{gait:'walk',direction:'right',frames:[97,172,190,195,198]},{gait:'run',direction:'left',frames:[55,73.5,92,98]},{gait:'run',direction:'right',frames:[45,63,81,95,100]}]};
fs.writeFileSync(path.join(dir,'direction-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:result.passed,checks:checks.length,failures,cases:cases.length,backward132_5:result.backward132_5}));if(failures.length)process.exitCode=1;
