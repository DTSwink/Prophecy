import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),rig=read('data/rig.json'),checks=[],measurements=[];
const check=(label,ok)=>{assert(ok,label);checks.push(label);};
const distance=(a,b)=>R.length(R.sub(a,b));
function kneePole(frame,names,side){
 const p=frame.pose,l=S.leg(frame.raw,names,side),axis=R.unit(R.sub(p.points[l.foot],p.points[l.hip])),v=R.sub(p.points[l.knee],p.points[l.hip]);
 return {axis:R.rotate(R.qinv(p.q[l.pelvis]),axis),pole:R.rotate(R.qinv(p.q[l.pelvis]),R.unit(R.sub(v,R.mul(axis,R.dot(axis,v)))))};
}

function inspect(run,gait,terrain){
 const source=JSON.stringify(run.poses),started=performance.now(),m=K.prepare(run,{gait,terrain});
 const result={gait,terrain,prepareMs:performance.now()-started,...m.metrics,maxBoneError:0,maxPinDrift:0,maxMaterialError:0,maxFrameAngle:0,maxFrameDistance:0,flatFrames:0,pinPairs:0,pivotTransfers:0,maxFootCorrection:0,maxExtraRoll:0,maxContactDownPitch:0,maxToeLocalError:0,maxToeLengthError:0,rollFrames:0};
 for(let i=0;i<m.frames.length;i++){
  const f=m.frames[i];
  if(f.influence===0){result.flatFrames++;assert.deepEqual(f.pose,f.raw,'Flat frame must be the exact NN pose');assert.equal(f.pelvisOffset,0);}
  for(let side=0;side<2;side++){
   const l=S.leg(f.raw,run.names,side?'R':'L'),p=f.pose.points;
   result.maxFootCorrection=Math.max(result.maxFootCorrection,2*Math.acos(Math.min(1,Math.abs(R.dot(f.pose.q[l.foot],f.raw.q[l.foot]))))*180/Math.PI);
   const toeLocal=q=>R.qm(R.qinv(q[l.foot]),q[l.toe]);
   const contact=f.feet[side].contact;
   if(contact){
    result.maxExtraRoll=Math.max(result.maxExtraRoll,Math.abs(contact.extraPitch));
    result.maxContactDownPitch=Math.max(result.maxContactDownPitch,-Math.asin(S.footFrame(f.pose,l.foot,l.toe,l.side).forward[1])*180/Math.PI);
    result.maxMaterialError=Math.max(result.maxMaterialError,distance(R.add(p[l.foot],R.rotate(f.pose.q[l.foot],contact.localPoint)),contact.point));
   }
   result.maxToeLengthError=Math.max(result.maxToeLengthError,Math.abs(distance(p[l.foot],p[l.toe])-distance(f.raw.points[l.foot],f.raw.points[l.toe])));
   if(f.feet[side].state==='ROLL'){
    result.rollFrames++;
    const gaps=S.footPoints(f.pose,l.foot,l.toe,l.side).map(o=>{const v=R.add(p[l.foot],o);return v[1]-m.terrain.height(v[0],v[2]);});
    assert(Math.min(...gaps)<.00301&&Math.min(...gaps)>-1e-5,'ROLL requires actual finite tread contact');
   }
   result.maxBoneError=Math.max(result.maxBoneError,Math.abs(distance(p[l.hip],p[l.knee])-l.upper),Math.abs(distance(p[l.knee],p[l.foot])-l.lower));
   if(i){const previous=m.frames[i-1];for(const j of [l.hip,l.knee,l.foot,l.toe]){
    result.maxFrameAngle=Math.max(result.maxFrameAngle,2*Math.acos(Math.min(1,Math.abs(R.dot(f.pose.q[j],previous.pose.q[j]))))*180/Math.PI);
    result.maxFrameDistance=Math.max(result.maxFrameDistance,distance(p[j],previous.pose.points[j]));
   }
   const prior=previous.feet[side].contact;
   if(contact&&prior?.stanceId===contact.stanceId){
    result.maxToeLocalError=Math.max(result.maxToeLocalError,1-Math.abs(R.dot(toeLocal(f.pose.q),toeLocal(previous.pose.q))));
    if(contact.pivotKey===prior.pivotKey){result.pinPairs++;result.maxPinDrift=Math.max(result.maxPinDrift,distance(contact.point,prior.point));}
    else result.pivotTransfers++;
   }}
  }
 }
 const label=gait+'/'+terrain;
 check(label+' finite poses',m.frames.every(f=>f.pose.points.flat().every(Number.isFinite)));
 check(label+' source NN unchanged',JSON.stringify(run.poses)===source);
 check(label+' exact NN on level approach/exit',result.flatFrames>0);
 check(label+' segment lengths retained',result.maxBoneError<1e-6);
 check(label+' root uses ramp only',m.frames.every(f=>Math.abs(f.root[1]-m.terrain.rootHeight(f.root[2]))<1e-6));
 check(label+' terrain correction clears rendered soles',result.maxPenetration<1e-5);
 check(label+' corrected targets reachable',result.maxReachError<1e-5);
 check(label+' bounded pelvis',result.maxPelvis<=.300001);
 check(label+' no bone orientation flip',result.maxFrameAngle<(gait==='walk'?15:20));
 check(label+' no limb teleport',result.maxFrameDistance<(gait==='walk'?.09:.14));
 check(label+' contact toe-down angle bounded',result.maxContactDownPitch<70.001);
 check(label+' rigid shoe articulation retained during contact',result.maxToeLocalError<1e-10&&result.maxToeLengthError<1e-8);
 check(label+' pin refers to the actual material point',result.maxMaterialError<1e-6);
 if(terrain==='flat')check(label+' whole clip is pure NN',result.flatFrames===m.frames.length&&result.maxPelvis===0);
 else{check(label+' actual stair contacts',result.pinPairs>10);check(label+' retained sole pivot has no world slide',result.maxPinDrift<1e-6);}
 const sample=JSON.stringify(m.sample(1.8));m.sample(4);m.sample(0);check(label+' deterministic reverse seeking',JSON.stringify(m.sample(1.8))===sample);
 if(gait==='walk'&&terrain==='stairs')for(const frame of [22])check('Reported F'+frame+' is exactly NN',JSON.stringify(m.sample(frame/60).pose)===JSON.stringify(m.sample(frame/60).raw));
 if(gait==='walk'&&terrain==='stairs'){
  const f=m.sample(80/60),left=S.leg(f.pose,run.names,'L'),right=S.leg(f.pose,run.names,'R');
  check('F80 left foot reaches tread by rolling',f.feet[0].state==='ROLL'&&f.feet[0].soleGap<.0001&&f.feet[0].soleGap>=-1e-6);
  const prior=m.sample(79/60),c=f.feet[0].contact;
  check('F80 ankle follows the fixed material pivot arc',prior.feet[0].contact?.pivotKey===c.pivotKey&&distance(prior.feet[0].contact.point,c.point)<1e-6&&distance(prior.pose.points[left.foot],f.pose.points[left.foot])>.001);
  const ankle=R.qm(R.qinv(f.pose.q[right.knee]),f.pose.q[right.foot]),nnAnkle=R.qm(R.qinv(f.raw.q[right.knee]),f.raw.q[right.foot]);
  check('F80 swing ankle remains within the landing articulation range',2*Math.acos(Math.min(1,Math.abs(R.dot(ankle,nnAnkle))))*180/Math.PI<45);
  result.frame80={leftRollDeg:f.feet[0].contactPitch,leftGapCm:f.feet[0].soleGap*100,rightSourcePitchDeg:Math.asin(S.footFrame(f.raw,right.foot,right.toe,'R').forward[1])*180/Math.PI};
  const bend=(frame,side)=>{const p=frame.pose,l=S.leg(frame.raw,run.names,side);return Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(R.sub(p.points[l.knee],p.points[l.hip])),R.unit(R.sub(p.points[l.foot],p.points[l.knee]))))))*180/Math.PI;};
  result.reportedKnees=[];
  for(const [frame,side,limit] of [[75,'L',4],[96,'R',7]]){
   const angles=[-1,0,1].map(n=>bend(m.sample((frame+n)/60),side));
   const maxChange=Math.max(Math.abs(angles[1]-angles[0]),Math.abs(angles[2]-angles[1]));
   check('F'+frame+' knee extends gradually',maxChange<limit);
   result.reportedKnees.push({frame,side,angles,maxChange});
  }
  // The rising swing now flexes this knee deliberately; check velocity continuity,
  // rather than imposing the old extension trajectory's speed at this frame.
  const risingBends=[102,103,104,105,106].map(n=>bend(m.sample(n/60),'R'));
  const bendSteps=risingBends.slice(1).map((v,i)=>v-risingBends[i]);
  // Coordinated forward travel flexes the knee faster than vertical-only lift;
  // retain the acceleration bound, plus the unchanged whole-course bone limits.
  check('104 rising knee flexes without an angular velocity spike',Math.max(...bendSteps.map(Math.abs))<10&&Math.max(...bendSteps.slice(1).map((v,i)=>Math.abs(v-bendSteps[i])))<1.5);
  result.reportedKnees.push({frame:104,side:'R',angles:risingBends,steps:bendSteps});
  const ascent=m.frames.slice(167,185).map(f=>f.pose.points[left.foot][1]);
  const liftSteps=ascent.slice(1).map((v,i)=>v-ascent[i]);
  check('84-92 left swing ascends continuously without a tread hover',Math.min(...liftSteps)>0);
  check('84-92 left swing avoids the late riser lift spike',Math.max(...liftSteps)<.045&&Math.max(...liftSteps.slice(1).map((v,i)=>Math.abs(v-liftSteps[i])))<.01);
  const firstRiser=m.frames.findIndex((f,i)=>i>=168&&i<=184&&
   f.pose.points[left.foot][1]-f.feet[0].soleGap-(m.frames[i-1].pose.points[left.foot][1]-m.frames[i-1].feet[0].soleGap)>.1);
  // Gap includes the shoe edge at the riser plane, not only its higher
  // endpoint corner. Require positive clearance for that complete shape.
  check('Left sole clears the first swing riser before crossing it',firstRiser>=0&&m.frames[firstRiser].feet[0].soleGap>0);
  result.ascent84to92={minHalfFrameLift:Math.min(...liftSteps),maxHalfFrameLift:Math.max(...liftSteps),riserFrame:firstRiser/2,riserClearance:m.frames[firstRiser].feet[0].soleGap};
  const advance=m.frames.slice(212,241).map(f=>f.pose.points[right.foot]);
  const travel=advance.slice(1).map((p,i)=>R.sub(p,advance[i]));
  // Sole-centred placement can keep this foot rolling on a nearer tread while
  // the old ankle-ray fixture had already released it. Test the actual state.
  check('106-120 retains contact or advances after release',travel.every((d,i)=>m.frames[213+i].feet[1].contact||(d[2]>.005&&d[1]>0)));
  const p106=m.sample(106/60).pose.points[right.foot],p110=m.sample(110/60).pose.points[right.foot];
  result.diagonal108={forwardCm:100*(p110[2]-p106[2]),upCm:100*(p110[1]-p106[1])};
  check('106-110 rolls in place or has useful forward clearance travel',m.frames.slice(212,221).every(f=>f.feet[1].contact)||(result.diagonal108.forwardCm>12&&result.diagonal108.upCm<18));
  const exitSwing=m.frames.slice(342,353).map(f=>f.pose.points[right.foot]);
  const exitSteps=exitSwing.slice(1).map((p,i)=>R.sub(p,exitSwing[i]));
  // Retained contacts and delayed exit handoff can change phase alignment;
  // the active clearance arc must still advance smoothly in both directions.
  check('171-176 exit swing advances while clearing risers',exitSteps.every(d=>d[1]>0&&d[2]>.01));
  check('171-176 exit swing avoids discrete lift corrections',Math.max(...exitSteps.slice(1).map((d,i)=>Math.abs(d[1]-exitSteps[i][1])))<.005);
  const exitHeights=m.frames.slice(337,364).map(f=>f.pose.points[right.foot][1]);
  const exitLift=exitHeights.slice(1).map((y,i)=>y-exitHeights[i]);
  check('169-181 exit swing has no renewed riser kick before the NN handoff',Math.max(...exitLift.slice(1).map((d,i)=>Math.abs(d-exitLift[i])))<.01);
  check('Exit toe-off retains material contact until the bounded 50ms lift preparation',m.frames.slice(328,331).every(f=>f.feet[1].contact&&f.feet[1].soleGap<1e-5));
  result.exitSwing171to176={minLift:Math.min(...exitSteps.map(d=>d[1])),maxLift:Math.max(...exitSteps.map(d=>d[1])),minForward:Math.min(...exitSteps.map(d=>d[2]))};
  check('Heel-to-toe contact transfers are exercised',result.pivotTransfers>0);
  result.maxPoleStep=0;result.maxPoleAcceleration=0;result.pole79to80=[];
  for(const side of ['L','R']){
   let previousDelta=0;
   for(let i=1;i<m.frames.length;i++){
    const a=kneePole(m.frames[i-1],run.names,side),b=kneePole(m.frames[i],run.names,side),transported=R.rotate(R.fromTo(a.axis,b.axis),a.pole);
    const delta=Math.atan2(R.dot(R.cross(transported,b.pole),b.axis),R.dot(transported,b.pole))*180/Math.PI;
    if(i>1&&[i-2,i-1,i].every(j=>m.frames[j].influence===1)){
     result.maxPoleStep=Math.max(result.maxPoleStep,Math.abs(delta));
     result.maxPoleAcceleration=Math.max(result.maxPoleAcceleration,Math.abs(delta-previousDelta));
    }
    if(side==='R'&&i>=158&&i<=161)result.pole79to80.push(delta);
    previousDelta=delta;
   }
  }
  check('Both IK knee poles have smooth angular velocity throughout the course',result.maxPoleStep<1.3&&result.maxPoleAcceleration<.7);
  check('Right knee pole at 79-80 has no sharp reversal',Math.max(...result.pole79to80.map(Math.abs))<1);
  const held=m.sample(101/60).feet[1];
  check('101 trailing foot retains its material pin',held.state==='ROLL'&&held.soleGap<.0001);
  check('101 rolls as needed without approaching full leg extension',distance(m.sample(101/60).pose.points[right.foot],m.sample(101/60).pose.points[right.hip])<right.reach*.98);
  const released=m.sample(107/60),trailing=S.leg(released.raw,run.names,'R');
  const dragPitch=Math.asin(S.footFrame(released.pose,trailing.foot,trailing.toe,'R').forward[1])*180/Math.PI;
  check('Trailing foot keeps its pin or remains toe-down after release',released.feet[1].contact||(released.feet[1].state==='SWING'&&dragPitch<0));
  result.trailing101={pitch:Math.asin(S.footFrame(m.sample(101/60).pose,trailing.foot,trailing.toe,'R').forward[1])*180/Math.PI,extraRoll:held.contact.extraPitch};
  result.trailing107={pitch:dragPitch};

 }
 if(terrain==='stairs'){
  const exitHeight=m.terrain.rootHeight(m.terrain.end);
  const levelExit=m.frames.findIndex(f=>f.root[2]>=m.terrain.end&&['L','R'].every(side=>{
   const l=S.leg(f.raw,run.names,side);
   return S.footPoints(f.raw,l.foot,l.toe,side).every(o=>{const p=R.add(f.raw.points[l.foot],o);return Math.abs(m.terrain.height(p[0],p[2])-exitHeight)<1e-8;});
  }));
  const handoff=m.frames.findIndex((f,i)=>i>=levelExit&&f.influence===0);
  check(gait+' completes foot recovery then returns to exact NN within one stride',handoff>=levelExit&&handoff-levelExit<120&&m.frames.slice(handoff).every(f=>f.pose===f.raw&&f.pelvisOffset===0));
  result.exactNNExitFrame=handoff/2;
 }
 measurements.push(result);return m;
}
for(const gait of ['walk','run']){
 const fixture=read('data/'+gait+'-fixture.json'),run=K.decode(fixture,rig.parents),meta=read('data/'+gait+'-phases.json');
 check(gait+' bank source matches expected NN',meta.lowerSource==='continuous autoregressive '+(gait==='walk'?'Walk':'Run')+' NN');
 check(gait+' model provenance retained',meta.provenance[gait].sha256===(gait==='walk'?'8bae21c5b3159d69726cd98867c85000b51d566012708eed36374b2b5a9d4c79':'0f2565ac72c5209153cbd910135209487f9ef8a0e234ed0c6d99df2ff30a299e'));
 const bytes=fs.readFileSync(new URL('data/'+gait+'-phases.bin',import.meta.url)),reuse=read('reuse.json');
 check(gait+' bank byte-identical to copied Bodyflip bank',createHash('sha256').update(bytes).digest('hex')===reuse.files['data/'+gait+'-phases.bin']);
 check(gait+' authored root speed retained',Math.abs((fixture.roots[150][2]-fixture.roots[0][2])/5-(gait==='walk'?2:5))<1e-4);
 for(const terrain of ['flat','stairs','down','uneven'])inspect(run,gait,terrain);
 // Every stored phase must retain the source samples exactly on flat terrain.
 const width=3+meta.names.length*12;
 for(let slot=0;slot<=meta.stride;slot++){
  const roots=[],poses=[];
  for(let frame=0;frame<meta.framesPerPhase;frame++){
   const offset=(slot*meta.framesPerPhase+frame)*width*4,v=Array.from({length:width},(_,j)=>bytes.readFloatLE(offset+j*4));
   roots.push(v.slice(0,3));poses.push({points:meta.names.map((_,j)=>v.slice(3+j*12,6+j*12)),axes:meta.names.map((_,j)=>[0,1,2].map(a=>v.slice(6+j*12+a*3,9+j*12+a*3)))});
  }
  const data={...meta,duration:5,roots,poses},decoded=K.decode(data,rig.parents),flat=K.prepare(decoded,{gait,terrain:'flat'});
  check(gait+' phase '+slot+' flat pose is unchanged',flat.frames.every(f=>f.pose===f.raw));
  for(let frame=0;frame<=150;frame++){
   const p=flat.frames[frame*4].pose;
   for(let j=1;j<p.points.length;j++)assert(distance(p.points[j],R.add(poses[frame].points[j-1],[-roots[0][0],0,-roots[0][2]]))<1e-7,'Exact NN policy sample');
  }
 }
}
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8'),app=fs.readFileSync(new URL('app.js',import.meta.url),'utf8');
check('Seconds readout replaced by frame counter',!html.includes('id="timeRead"')&&html.includes('F 0 / 300'));
check('Bracket tooltips use frames',app.includes("el.dataset.time='F '"));
check('One playback rail retained',html.split('id="scrub"').length===2);
const result={passed:true,checks,measurements};fs.writeFileSync(new URL('verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:true,checks:checks.length,measurements}));
