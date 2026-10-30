'use strict';
// Recorded NN responses only: no model process or live scene writes.
const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert/strict');
const R=require('./recovery.js'),K=require('./footik.js'),F=require('./surface.js'),C=require('./surface-coupling.js'),J=require('./slide-joints.js');
const checks=[],check=(name,pass,details)=>{checks.push({name,passed:!!pass,details});assert(pass,name+' '+JSON.stringify(details??''));};
const s=K.sanitize(),shift=(n,v,settings=s)=>F.slideTargetShift(n,v,settings);
check('Defaults: 20 cm at 10 m/s',s.slideShift===20&&s.slideShiftSpeed===10);
for(const invalid of [null,'',NaN,Infinity]){const t=K.sanitize({slideShift:invalid,slideShiftSpeed:invalid});check('Invalid setting fallback '+invalid,t.slideShift===20&&t.slideShiftSpeed===10);}
check('Zero speed and zero shift give no offset',R.length(shift([0,0,1],[0,0,0]))===0&&R.length(shift([0,0,1],[0,-20,0],K.sanitize({slideShift:0})))===0);
check('Half speed gives half offset',Math.abs(R.length(shift([0,0,1],[0,-5,0]))-.1)<1e-12);
check('Total speed, independent of travel direction',JSON.stringify(shift([0,0,1],[3,4,0]))===JSON.stringify(shift([0,0,1],[0,-5,0])));
check('Offset stops growing at selected speed',Math.abs(R.length(shift([0,0,1],[0,-100,0]))-.2)<1e-12);
for(const angle of [45,80,90]){const n=[0,Math.cos(angle*Math.PI/180),Math.sin(angle*Math.PI/180)],v=shift(n,[0,-10,0]);check('Projected upward and tangent at '+angle,Math.abs(R.dot(n,v))<1e-12&&v[1]>0&&Math.abs(R.length(v)-.2)<1e-12);}
check('Horizontal plane has no uphill direction',R.length(shift([0,1,0],[10,0,0]))===0);
(async()=>{
 const {request,response}=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(__dirname,'snapshots/slide-live-2.json.gz'))));
 const run=K.decode(request.source,require('./data/rig.json').parents),joints=J.build(undefined,run.names,run.parents);
 const make=async options=>(await C.compute(run,{...request.settings,...options},async(_,i)=>response.steps[i])).model;
 const baseline=await make({slideShift:0}),large=await make({slideShift:50,slideShiftSpeed:.1});
 check('Root trajectory unchanged at maximum shift',JSON.stringify(large.frames.map(f=>f.root))===JSON.stringify(baseline.frames.map(f=>f.root)));
 check('Pre-slide NN/IK poses unchanged',large.frames.every((f,i)=>f.slide||JSON.stringify(f.pose)===JSON.stringify(baseline.frames[i].pose)));
 let invalid=0,maxStep=0,peak=null,penetration=0,gap=0;const raised={L:[],R:[],hand:[]};
 for(let i=1;i<large.frames.length;i++){
  const f=large.frames[i],b=baseline.frames[i];if(f.slide?.blend!==1)continue;
  for(let j=2;j<run.names.length;j++){invalid+=!joints.diagnose(j,f.pose.q[run.parents[j]],f.pose.q[j]).withinLimits;const d=R.length(R.qlog(R.qm(f.pose.q[j],R.qinv(large.frames[i-1].pose.q[j]))))*180/Math.PI;if(d>maxStep){maxStep=d;peak={frame:i/2,joint:run.names[j]};}}
  gap=Math.max(gap,f.slide.hand.gap,...f.feet.map(x=>Math.abs(x.soleGap)));penetration=Math.max(penetration,...f.feet.map(x=>x.penetration));
  for(const side of ['L','R']){const a=run.names.indexOf('foot_'+side.toLowerCase());raised[side].push((f.pose.points[a][1]-f.pose.points[run.names.indexOf('pelvis')][1])-(b.pose.points[a][1]-b.pose.points[run.names.indexOf('pelvis')][1]));}
  raised.hand.push(f.slide.hand.point[1]-b.slide.hand.point[1]);
 }
 const median=a=>a.sort((a,b)=>a-b)[Math.floor(a.length/2)],upward=Object.fromEntries(Object.entries(raised).map(([k,v])=>[k,median(v)]));
 // This is deliberately an extreme 50 cm / 0.1 m/s stress case. It checks
 // legality and absence of 90/180-degree flips, not normal-speed visual quality;
 // verify-slide-motion.cjs retains the stricter <20 degree check at defaults.
 check('Extreme shift retains legal joints without limb inversion',invalid===0&&maxStep<90,{invalid,maxStep,peak});
 check('Large shift retains wall contacts',gap<.004&&penetration<1e-5,{gap,penetration});
 check('Both feet and palm move upward',Object.values(upward).every(v=>v>.01),upward);
 const report={passed:true,checks};fs.writeFileSync(path.join(__dirname,'snapshots/slide-shift-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1;});
