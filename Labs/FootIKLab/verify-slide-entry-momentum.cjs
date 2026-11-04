'use strict';
// Recorded policy replies only: no inference, browser or live-state mutation.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),z=require('node:zlib'),Module=require('node:module');
const R=require('./recovery.js'),K=require('./footik.js'),C=require('./surface-coupling.js'),D=require('./verify-slide-directions.cjs');
const dir=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKWall20261103'),parents=require('./data/rig.json').parents;
const read=p=>JSON.parse(z.gunzipSync(fs.readFileSync(p))),json=v=>JSON.stringify(v);
function priorAPI(){
 const load=(name,source,resolve)=>{const filename=path.join(__dirname,name),m=new Module(filename,module);m.filename=filename;m.paths=module.paths;if(resolve){const original=m.require.bind(m);m.require=n=>resolve(n,original);}m._compile(source,filename);return m.exports;};
 const entry=load('slide-entry-before-momentum.js',fs.readFileSync(path.join(dir,'slide48-before-entry.js'),'utf8'));
 const surface=load('slide-entry-momentum-before.js',fs.readFileSync(path.join(dir,'slide48-before-surface.js'),'utf8'),(n,original)=>n==='./slide-entry.js'?entry:original(n));
 return load('slide-entry-momentum-before-coupling.js',fs.readFileSync(path.join(__dirname,'surface-coupling.js'),'utf8'),(n,original)=>n==='./surface.js'?surface:original(n));
}
const beforeAPI=priorAPI();let checks=0;
const check=(condition,message)=>{assert.ok(condition,message);checks++;};
async function solve(api,fixture,overrides={},ends){
 const run=K.decode(fixture.request.source,parents),settings={...fixture.request.settings,...overrides};
 const session=api.createSession(run,settings,async(_,i)=>{assert.ok(fixture.response.steps[i],'Recorded NN exhausted');return fixture.response.steps[i];});
 try{for(const end of ends||[fixture.request.endTime])await session.extend(end);return {run,settings,model:session.model};}finally{session.close();}
}
function speed(model,i,j){const p=model.frames,relative=k=>R.sub(p[k].pose.points[j],p[k].pose.points[1]);return R.mul(R.sub(relative(i),relative(i-1)),120);}
function acceleration(model,i,j){return R.length(R.mul(R.sub(speed(model,i,j),speed(model,i-1,j)),120));}
function compare(old,current,name){
 const a=old.model,b=current.model,entry=b.frames.findIndex(f=>f.slide),oldReport=D.measure(old,name+'-before'),report=D.measure(current,name);
 check(entry>=0,name+': reaches slide');
 check(json(a.frames.slice(0,entry))===json(b.frames.slice(0,entry)),name+': all pre-slide output exact');
 check(json(a.frames.map(f=>[f.root,f.surface.velocity]))===json(b.frames.map(f=>[f.root,f.surface.velocity])),name+': root motion exact');
 let upperError=0,worstUpper=null,pelvisError=0;
 for(let i=entry;i<b.frames.length;i++)pelvisError=Math.max(pelvisError,R.length(R.sub(a.frames[i].pose.points[1],b.frames[i].pose.points[1])));
 check(pelvisError<1e-8,name+': authored pelvis path is unchanged');
 for(let i=entry;i<b.frames.length;i++)for(let j=1;j<18;j++){const error=Math.max(R.length(R.sub(a.frames[i].pose.points[j],b.frames[i].pose.points[j])),R.length(R.qlog(R.qm(a.frames[i].pose.q[j],R.qinv(b.frames[i].pose.q[j])))));if(error>upperError){upperError=error;worstUpper={frame:i/2,bone:current.run.names[j],error};}}
 // Body balance responds to actual foot friction. Its small rotation may
 // differ; the pelvis path and arm solver are not retimed or replaced.
 check(report.finite&&report.boneErrorM<1e-6,name+': finite and fixed bone lengths');
 check(!report.settledInvalid.length,name+': settled joints remain legal');
 check(!report.entryAddedLimitDeg.some(x=>x.bone.startsWith('thigh_')&&x.value>.01),name+': no added hip-limit violation');
 if(report.maxPenetrationM>Math.max(.005,oldReport.maxPenetrationM+.002))console.log(json({name,penetration:report.maxPenetrationM,prior:oldReport.maxPenetrationM,maxAcceleration:report.footAccelerationMps2[0]}));
 check(report.maxPenetrationM<=Math.max(.005,oldReport.maxPenetrationM+.002),name+': no worse shoe penetration');
 const velocity=current.run.names.map((n,j)=>({n,j})).filter(x=>/^foot_[lr]$/.test(x.n)).map(({n,j})=>({foot:n,before:R.length(speed(a,entry,j)),after:R.length(speed(b,entry,j)),incoming:R.length(speed(a,entry-1,j)),beforeAcceleration:acceleration(a,entry,j),afterAcceleration:acceleration(b,entry,j)}));
 return {name,entry:entry/2,velocity,upperError,maxPenetrationM:report.maxPenetrationM,priorPenetrationM:oldReport.maxPenetrationM,maxJointStep:report.jointStepsDeg[0],maxAcceleration:report.footAccelerationMps2[0]};
}
(async()=>{
 const fixture=read(path.join(dir,'slide48-before.fixture.json.gz')),results=[];
 for(const seconds of process.argv.includes('--cases-only')?[]:[.5,1]){
  const old=await solve(beforeAPI,fixture,{slideLegBlend:seconds}),current=await solve(C,fixture,{slideLegBlend:seconds}),receipt=compare(old,current,'phase26-'+seconds);
  for(const v of receipt.velocity){check(v.before<1e-8,'Reproduction: both feet stopped at entry');check(v.after>v.incoming*.65&&v.after<v.incoming*1.15,'Incoming foot movement continues without a kick');check(v.afterAcceleration<v.beforeAcceleration*.5,'Entry velocity discontinuity is more than halved');}
  if(seconds===1){
   check(receipt.maxPenetrationM<1e-5,'Slower current scene keeps the shoes clear');
   const split=await solve(C,fixture,{slideLegBlend:seconds},[.79,.8,.95,1.2,fixture.request.endTime]);
   check(json(split.model.frames)===json(current.model.frames),'Extending trim across and during entry is exact');
   fs.writeFileSync(path.join(dir,'slide48-after1.model.json.gz'),z.gzipSync(json({names:current.run.names,parents,settings:current.model.settings,frames:current.model.frames})));
  }
  results.push(receipt);console.log(json(receipt));
 }
 const cases=[['phase58',path.join(dir,'arrival-final.fixture.json.gz')],...['backward','walk','turn'].map(n=>[n,path.join(dir,'slide48-'+n+'.fixture.json.gz')])];
 for(const [name,file]of cases){const fixture=read(file),old=await solve(beforeAPI,fixture),current=await solve(C,fixture);const receipt=compare(old,current,name);results.push(receipt);console.log(json(receipt));}
 const report={passed:true,checks,results};fs.writeFileSync(path.join(dir,'slide48-verification.json'),JSON.stringify(report,null,2));console.log(json({passed:true,checks}));
})().catch(e=>{console.error(e);process.exitCode=1;});
