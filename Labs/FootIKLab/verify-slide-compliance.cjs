'use strict';
// Offline before/after review of catch recovery and ankle/contact priorities.
// Recorded NN responses only. Diagnostics are injected into in-memory modules,
// never into the live runtime or saved viewer state.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),Module=require('module'),crypto=require('crypto');
const R=require('./recovery.js'),K=require('./footik.js'),S=require('./support.js'),J=require('./slide-joints.js');
const {add,sub,mul,dot,length,unit,qm,qinv,rotate}=R,DT=1/120,DEG=180/Math.PI;
const DIR=__dirname,OUT=path.join(DIR,'snapshots'),BEFORE=path.join(OUT,'slide-compliance-before-surface.js');
const hash=x=>crypto.createHash('sha256').update(typeof x==='string'?x:JSON.stringify(x)).digest('hex');
const median=a=>{const b=a.slice().sort((a,b)=>a-b);return b.length?b[Math.floor((b.length-1)/2)]:null;};
const stats=a=>({min:Math.min(...a),median:median(a),max:Math.max(...a)});
function compile(source,filename,overrides={}){const m=new Module(filename,module);m.filename=filename;m.paths=Module._nodeModulePaths(DIR);const original=m.require.bind(m);m.require=n=>n in overrides?overrides[n]:original(n);m._compile(source,filename);return m.exports;}
function coupling(source){
 const needle='return {pose,feet,hand:{side:near.side';
 if(!source.includes(needle))throw Error('Slide diagnostic insertion point changed');
 source=source.replace(needle,'return {contactMotion:Object.fromEntries(Object.entries(e.drag).map(([key,v])=>[key,{x:v.x.slice(),v:v.v.slice(),grip:v.grip,force:v.force.slice(),touching:v.touching}])),pose,feet,hand:{side:near.side');
 const frame='heading:slideResult.heading';
 if(!source.includes(frame))throw Error('Slide frame diagnostic insertion point changed');
 source=source.replace(frame,'heading:slideResult.heading,contactMotion:slideResult.contactMotion');
 const F=compile(source,path.join(DIR,'surface.js'));
 return compile(fs.readFileSync(path.join(DIR,'surface-coupling.js'),'utf8'),path.join(DIR,'surface-coupling.js'),{'./surface.js':F});
}
function isolatedRelease(source){
 const begin=source.indexOf('function dragContact('),end=source.indexOf('const limitedRotation=',begin);
 if(begin<0||end<0)throw Error('Contact spring extraction point changed');
 const build=new Function('R','s',`const {add,sub,mul,dot,length,unit}=R;const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};const tangent=(v,n)=>sub(v,mul(n,dot(v,n)));const hash=x=>{const v=Math.sin(x*127.1+311.7)*43758.5453;return v-Math.floor(v);};${source.slice(begin,end)};return dragContact;`);
 const drag=build(R,K.sanitize()),state={x:[0,.15,0],v:[0,0,0],phase:0,grip:0,force:[0,0,0]};let peak=0,return80=null;
 for(let i=0;i<240;i++){drag(state,[0,0,0],[0,0,1],DT,false);peak=Math.max(peak,length(state.v));if(return80===null&&length(state.x)<=.03)return80=(i+1)*DT;}
 return {initialDisplacementM:.15,initialVelocity:0,friction:false,return80Seconds:return80,peakSpeed:peak,residualM:length(state.x)};
}
function analyze(run,model){
 const frames=model.frames,start=frames.findIndex(f=>f.slide),settled=frames.findIndex(f=>f.slide?.blend===1),first=settled+60,joints=J.build(undefined,run.names,run.parents),contacts={},feet={};
 const near=frames[settled].slide.hand.side,idx=n=>run.names.indexOf(n),root=f=>f.pose.points[0];
 const material=(f,key)=>{if(key!=='hand')return f.pose.points[idx('foot_'+key.toLowerCase())];const i=idx('hand_'+near),sign=near==='l'?1:-1,q=f.pose.q[i];return add(f.pose.points[i],add(mul(rotate(q,[sign,0,0]),.0725),mul(rotate(q,[0,1,0]),sign===1?.020:-.025)));};
 for(const key of ['L','R','hand']){
  const samples=frames.slice(first).map((f,i)=>{const d=f.slide.contactMotion[key],r=length(d.x);return {frame:(i+first)/2,r,radial:r>1e-6?dot(d.x,d.v)/r:0,grip:d.grip,point:sub(material(f,key),root(f))};});
  const events=[];let begin=null;
  for(let i=1;i<samples.length;i++){
   if(begin===null&&samples[i-1].radial>=0&&samples[i].radial<0)begin=i-1;
   if(begin!==null&&(samples[i].radial>=0||i===samples.length-1)){
    const chunk=samples.slice(begin,i+1),from=chunk[0].r,to=chunk.at(-1).r,drop=from-to;
    if(drop>.015&&chunk.length*DT>.06&&samples[i].radial>=0){const crossing=chunk.findIndex(p=>p.r<=to+drop*.2),speed=[],inward=chunk.map(x=>-x.radial);for(let j=1;j<chunk.length;j++)speed.push(length(sub(chunk[j].point,chunk[j-1].point))/DT);const peak=Math.max(...speed);events.push({start:chunk[0].frame,end:chunk.at(-1).frame,displacementM:drop,return80Seconds:crossing*DT,durationSeconds:(chunk.length-1)*DT,peakInwardSpeed:Math.max(...inward),peakInwardFrame:chunk[inward.indexOf(Math.max(...inward))].frame,renderedPeakSpeed:peak,renderedPeakFrame:chunk[speed.indexOf(peak)+1].frame,releaseGrip:chunk[0].grip});}
    begin=null;
   }
  }
  const windowMotion=[];for(let i=0;i+60<samples.length;i+=15){const points=samples.slice(i,i+61).map(p=>p.point),delta=[0,1,2].map(k=>Math.max(...points.map(p=>p[k]))-Math.min(...points.map(p=>p[k])));windowMotion.push(length(delta));}
  contacts[key]={events,return80Seconds:stats(events.map(x=>x.return80Seconds)),meanReturnSpeed:stats(events.map(x=>.8*x.displacementM/x.return80Seconds)),peakInwardSpeed:stats(events.map(x=>x.peakInwardSpeed)),renderedPeakSpeed:stats(events.map(x=>x.renderedPeakSpeed)),halfSecondMotion:stats(windowMotion)};
 }
 let invalid=0,allInvalid=0,gap=0,penetration=0,boneError=0,kneeStep=0,ankleStep=0;const invalidExamples=[];
 for(const side of ['L','R']){
  const foot=idx('foot_'+side.toLowerCase()),toe=idx('ball_'+side.toLowerCase()),calf=idx('calf_'+side.toLowerCase()),hip=idx('thigh_'+side.toLowerCase()),tilts=[],relativeNeutral=[],kneeRelative=[];
  for(const f of frames.slice(first)){
   const p=f.pose,frame=S.footFrame(p,foot,toe,side),n=f.surface.pinNormal;
   tilts.push(Math.acos(Math.max(-1,Math.min(1,dot(frame.up,n))))*DEG);
   relativeNeutral.push(length(R.qlog(qm(qm(qinv(p.q[calf]),p.q[foot]),qinv(joints.joints[foot].refRelative))))*DEG);
   kneeRelative.push(sub(p.points[calf],p.points[hip]));
  }
  feet[side]={soleTiltDeg:stats(tilts),ankleNeutralDeviationDeg:stats(relativeNeutral),kneeRelative};
 }
 for(let i=settled;i<frames.length;i++){
  const f=frames[i],p=f.pose;
  gap=Math.max(gap,Math.abs(f.slide.hand.gap),...f.feet.map(x=>Math.abs(x.soleGap)));penetration=Math.max(penetration,...f.feet.map(x=>x.penetration));
  for(let j=2;j<run.names.length;j++){
   const parent=run.parents[j],d=joints.diagnose(j,p.q[parent],p.q[j]);
   boneError=Math.max(boneError,Math.abs(length(sub(p.points[j],p.points[parent]))-length(sub(frames[start].pose.points[j],frames[start].pose.points[parent]))));
   if(!d.withinLimits){allInvalid++;if(/^(calf|foot|ball|lowerarm|hand)_/.test(run.names[j])){invalid++;if(invalidExamples.length<6)invalidExamples.push({frame:i/2,bone:run.names[j],...d});}}
   if(i>settled){const q=qm(qinv(p.q[parent]),p.q[j]),prev=frames[i-1].pose,old=qm(qinv(prev.q[parent]),prev.q[j]),step=length(R.qlog(qm(q,qinv(old))))*DEG;if(run.names[j].startsWith('calf_'))kneeStep=Math.max(kneeStep,step);if(run.names[j].startsWith('foot_'))ankleStep=Math.max(ankleStep,step);}
  }
 }
 return {entryFrame:start/2,settledFrame:settled/2,contacts,feet,constraints:{invalid,allInvalid,invalidExamples,gap,penetration,boneError,kneeStep,ankleStep},rootHash:hash(frames.map(f=>[f.pose.points[0],f.surface.mass,f.surface.velocity])),prefixHash:hash(frames.slice(0,start).map(f=>f.pose)),nnSteps:model.coupling.steps};
}
(async()=>{
 if(!fs.existsSync(BEFORE))throw Error('Missing pre-change source snapshot');
 const beforeSource=fs.readFileSync(BEFORE,'utf8'),afterSource=fs.readFileSync(path.join(DIR,'surface.js'),'utf8'),cases=[],checks=[],release={before:isolatedRelease(beforeSource),after:isolatedRelease(afterSource)};
 const check=(name,passed,details)=>checks.push({name,passed:!!passed,...(details===undefined?{}:{details})});
 check('Identical15cm friction-free release returns more gradually',release.after.return80Seconds>release.before.return80Seconds&&release.after.peakSpeed<release.before.peakSpeed,release);
 for(const threshold of [2,5]){
  const fixture=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(OUT,`slide-live-${threshold}.json.gz`)))),run=K.decode(fixture.request.source,require('./data/rig.json').parents),result={threshold};
  for(const [key,source] of [['before',beforeSource],['after',afterSource]]){const C=coupling(source),{model}=await C.compute(run,fixture.request.settings,async(_,i)=>fixture.response.steps[i]);result[key]=analyze(run,model);}
  const a=result.before,b=result.after;result.comparison={};
  check(`${threshold}: root and pre-slide motion unchanged`,a.rootHash===b.rootHash&&a.prefixHash===b.prefixHash&&a.nnSteps===b.nnSteps);
  check(`${threshold}: ankle/toe/knee/elbow/wrist limits`,b.constraints.invalid===0,b.constraints.invalidExamples);
  check(`${threshold}: shoe/palm contact and fixed bone lengths`,b.constraints.gap<.004&&b.constraints.penetration<1e-5&&b.constraints.boneError<1e-8,b.constraints);
  check(`${threshold}: no new settled knee/ankle snap`,b.constraints.kneeStep<3&&b.constraints.ankleStep<3,b.constraints);
  for(const key of ['L','R','hand']){const old=a.contacts[key],next=b.contacts[key],comparison={beforeEvents:old.events.length,afterEvents:next.events.length,return80Seconds:[old.return80Seconds.median,next.return80Seconds.median],meanReturnSpeed:[old.meanReturnSpeed.median,next.meanReturnSpeed.median],peakInwardSpeed:[old.peakInwardSpeed.max,next.peakInwardSpeed.max],renderedPeakSpeed:[old.renderedPeakSpeed.max,next.renderedPeakSpeed.max],halfSecondMotion:[old.halfSecondMotion.median,next.halfSecondMotion.median]};result.comparison[key]=comparison;
   // Patches continue to drive the particle throughout recovery. A smaller
   // catch can finish sooner despite moving more slowly, so compare actual
   // metres/second rather than requiring every event to last longer.
   check(`${threshold}/${key}: recovery is slower with visible motion`,next.events.length>0&&next.meanReturnSpeed.median<old.meanReturnSpeed.median&&next.peakInwardSpeed.max<old.peakInwardSpeed.max&&next.renderedPeakSpeed.max<old.renderedPeakSpeed.max&&next.halfSecondMotion.median>.02,comparison);
  }
  for(const side of ['L','R']){const x=a.feet[side],y=b.feet[side];result.comparison['foot'+side]={soleTiltDeg:[x.soleTiltDeg,y.soleTiltDeg],ankleNeutralDeviationDeg:[x.ankleNeutralDeviationDeg,y.ankleNeutralDeviationDeg],maxKneePositionChangeM:Math.max(...x.kneeRelative.map((v,i)=>length(sub(v,y.kneeRelative[i]))))};delete x.kneeRelative;delete y.kneeRelative;}
  cases.push(result);
 }
 const report={passed:checks.every(c=>c.passed),beforeSha256:hash(beforeSource),afterSha256:hash(afterSource),sampleHz:120,release,description:'Measured local-max to local-min recovery of actual tangent compliance displacement; 80% means80% of each observed recovery distance, not zero offset. Only complete events exceeding1.5cm are included. Sole tilt is shoe up versus wall normal. Tilt/knee comparison is descriptive, not a requirement to maximize foot tilt.',checks,cases};
 fs.writeFileSync(path.join(OUT,'slide-compliance-verification.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({passed:report.passed,checks:checks.length,failed:checks.filter(c=>!c.passed),cases:cases.map(c=>({threshold:c.threshold,comparison:c.comparison}))}));
 if(!report.passed&&!process.argv.includes('--diagnostic'))process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
