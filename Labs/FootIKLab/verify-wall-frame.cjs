const fs=require('fs'),z=require('zlib'),assert=require('assert/strict');
const R=require('./recovery.js'),S=require('./support.js'),K=require('./footik.js'),F=require('./surface.js'),C=require('./surface-coupling.js'),{load}=require('./test-bank.cjs');
const parents=require('./data/rig.json').parents,checks=[],cases=[],check=(name,ok)=>{assert(ok,name);checks.push(name);};
(async()=>{
for(const gait of ['run','walk']){
 const {request,response}=JSON.parse(z.gunzipSync(fs.readFileSync(`data/wall-frame-${gait}-fixture.json.gz`))),run=K.decode(request.source,parents);
 request.settings={...request.settings,pelvisCloser:0};
 // These are the approved checkpoint fixtures. Exact root replay below verifies
 // compatibility with today's solver when the new pelvis option is disabled.
 const {model}=await C.compute(run,request.settings,async(_,i)=>response.steps[i]);let hinge=1,bones=0,upper=0,replay=0,poleStep=0;
 for(let i=0;i<model.frames.length;i++){const f=model.frames[i];
  for(let j=2;j<run.names.length;j++)bones=Math.max(bones,Math.abs(R.length(R.sub(f.pose.points[j],f.pose.points[parents[j]]))-R.length(R.sub(f.raw.points[j],f.raw.points[parents[j]]))));
  for(let j=1;j<run.names.length;j++)if(!/^(thigh|calf|foot|ball)_/.test(run.names[j]))upper=Math.max(upper,R.length(R.sub(f.pose.points[j],f.raw.points[j])));
  for(const side of ['L','R']){const a=S.leg(f.raw,run.names,side),b=S.leg(f.pose,run.names,side);hinge=Math.min(hinge,R.dot(a.normal,b.normal));if(i){const old=S.leg(model.frames[i-1].pose,run.names,side),angle=Math.acos(Math.max(-1,Math.min(1,R.dot(old.normal,b.normal))))*180/Math.PI;poleStep=Math.max(poleStep,angle);}}
 }
 for(const w of model.coupling.windows){const expected=response.diagnostics.coupling.windows.find(x=>x.frame===w.frame);replay=Math.max(replay,R.length(R.sub(w.root,expected.root)),R.length(R.sub(w.velocity,expected.velocity)));}
 check(gait+' all601 poses finite; source bone lengths and upper articulation retained',model.frames.every(f=>f.pose.points.flat().every(Number.isFinite))&&bones<1e-8&&upper<1e-8);
 check(gait+' neither knee reverses or splays its NN hinge',hinge>.95&&poleStep<10);
 check(gait+' real NN root history replays exactly',replay<1e-8&&model.coupling.steps===149);
 check(gait+' material pins and sole collision retained',model.metrics.maxContactDrift<1e-8&&model.metrics.maxPenetration<1e-5&&model.metrics.maxReachError<1e-7&&model.metrics.wallContactFrames>0);
 const current=model.sample(143/60),hipHeight=R.dot(R.sub(current.raw.points[run.names.indexOf('pelvis')],current.root),current.surface.pinNormal);
 check(gait+' saved frame retains standing pelvis height in ground frame',hipHeight>.7&&hipHeight<1.05);
 cases.push({gait,hinge,poleStep,bones,upper,replay,hipHeight,metrics:model.metrics});
}
// Upright changes posture, never the NN's height in its supporting ground frame.
for(const upright of [0,.55,1]){const run=load('walk',.21),m=F.prepare(run,{gait:'walk',slopeAngle:90,upright});let error=0;for(let i=0;i<m.frames.length;i++){const f=m.frames[i],p=K.at(run,i/120),pelvis=run.names.indexOf('pelvis'),groundUp=R.rotate(f.surface.gaitRotation,[0,1,0]);error=Math.max(error,Math.abs(R.dot(R.sub(f.raw.points[pelvis],f.root),groundUp)-(p.points[pelvis][1]-p.points[0][1])));}check('Upright '+upright+' retains source ground-relative pelvis height',error<1e-9);}
fs.writeFileSync('snapshots/wall-frame-verification.json',JSON.stringify({passed:true,checks,cases},null,2));console.log(JSON.stringify({passed:true,checks:checks.length,cases}));
})().catch(e=>{console.error(e);process.exitCode=1});
