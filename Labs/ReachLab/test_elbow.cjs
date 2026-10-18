// Owned stdin kernel only. Never drives, refreshes, or writes the live desktop.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict'),{spawn}=require('child_process'),readline=require('readline');
const lab=__dirname,root=path.resolve(lab,'../..'),out=path.join(root,'Saved/Diagnostics/ReachElbowDesign20261016');
const R=require('../SwordHolsterLab/recovery.js'),W=require('./wrist.js'),json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const child=spawn(process.env.REACH_PYTHON||'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(lab,'test_kernel.py')],{windowsHide:true,stdio:['pipe','pipe','inherit']}),jobs=[];
readline.createInterface({input:child.stdout}).on('line',s=>{const j=jobs.shift(),r=JSON.parse(s);r.error?j.reject(Error(r.error)):j.resolve(r);});
const kernel=(p,b)=>new Promise((resolve,reject)=>{jobs.push({resolve,reject});child.stdin.write(JSON.stringify(b)+'\n');});
function setup(fixture,options){
 const c=vm.createContext({console,performance,callKernel:kernel,document:{getElementById:()=>({textContent:''})},Recovery:R,ReachWrist:W,initial:fixture,options,data:json(path.join(lab,'data.json')),fingers:json(path.join(lab,'fingers.json')),defaultsData:json(path.join(lab,'reset_defaults.json'))});
 for(const f of ['grab.js','coupled.js'])vm.runInContext(fs.readFileSync(path.join(lab,f),'utf8'),c);
 const app=fs.readFileSync(path.join(lab,'app.js'),'utf8');vm.runInContext(app.slice(0,app.indexOf('const renderer=')),c);
 vm.runInContext(`dataset=data;referenceBase=copy(data.base);resetDefaults=defaultsData;setBasePose(initial.basePose);fingerData=fingers;fingerModels=[0,1].map(k=>ReachGrab.build(fingerData,k));settings=copy(initial.settings);phat=copy(initial.phat);pose=copy(initial.pose);solverState=copy(initial.solverState);handQ=copy(initial.handQ);grabs=copy(initial.grabs);returns=copy(initial.returns);wholeReturn=copy(initial.wholeReturn);ticks=initial.tick;scenarioMotion=initial.motion;ready=true;post=callKernel;function drawAll(){};
 if(options.blend!==undefined)settings.elbowDownBlend=options.blend;
 if(options.restart){pose=copy(dataset.base);solverState=Array(20).fill(0);grabs=[null,null];handQ=hands.map(j=>pose[j].slice(3));ticks=0;scenarioMotion=null;}`,c);
 return c;
}
async function run(name,fixture,options={}){
 const c=setup(fixture,options);
 const report=await vm.runInContext(`(async()=>{
 const first=[null,null],swivel=[0,0],maxSwivel=[0,0],settled=[0,0],trace=[],times=[];let maxLength=0,maxLimit=0,planCalls=0,intervalSolves=0;
 const plan=ReachCoupled.plan;ReachCoupled.plan=i=>{planCalls++;return plan(i);};
 const target=copy(settings.hands[1].target);
 const bend=p=>arms.map(a=>{const s=p[a[1]].slice(0,3),e=p[a[2]].slice(0,3),axis=normalize(sub(p[a[3]].slice(0,3),s)),u=sub(e,s);return {axis,pole:normalize(sub(u,mul(axis,dot(u,axis))))};});
 for(let i=0;i<(options.frames||480);i++){
  if(options.dynamic){if(i===15)settings.elbowDownBlend=1;if(i===45)settings.elbowDownBlend=0;if(i>=160&&i<280)settings.elbowDownBlend=(i-160)/119;if(i>=300&&i<420)settings.elbowDownBlend=1-(i-300)/119;}
  if(options.drag)settings.hands[1].target=add(target,[0,0,i<80||i>=400?0:options.drag*Math.sin((i-80)*2*Math.PI/80)]);
  const before=bend(pose);await step(1,false);const now=bend(pose);times.push(coupledMs);
  for(let k=0;k<2;k++){
   if(grabs[k]?.gripped&&first[k]===null)first[k]=ticks;
   if(grabs[k]?.armPlan?.intervalSolve)intervalSolves++;
   const transported=R.rotate(R.fromTo(before[k].axis,now[k].axis),before[k].pole),s=Math.atan2(dot(cross(transported,now[k].pole),now[k].axis),dot(transported,now[k].pole))*180/Math.PI;
   swivel[k]+=Math.abs(s);maxSwivel[k]=Math.max(maxSwivel[k],Math.abs(s));if(i>=440)settled[k]+=Math.abs(s);
   const [a,e,h]=arms[k].slice(1),q=pose[h].slice(3),limited=ReachWrist.constrain(phat.wrists[k],pose[e].slice(3),q);maxLimit=Math.max(maxLimit,1-Math.abs(dot(q,limited)));
   for(let j=0;j<2;j++)maxLength=Math.max(maxLength,Math.abs(norm(sub(pose[[e,h][j]].slice(0,3),pose[[a,e][j]].slice(0,3)))-armLengths[k][j]));
  }
  trace.push({tick:ticks,blend:settings.elbowDownBlend,pose:copy(pose),held:grabs.map(g=>g?.gripped),distance:grabs.map(g=>g?.distance),angle:grabs.map(g=>g?.angle)});
 }
 times.sort((a,b)=>a-b);return {first,swivel,maxSwivel,settled,maxLength,maxLimit,planCalls,intervalSolves,meanMs:times.reduce((a,b)=>a+b,0)/times.length,p95Ms:times[Math.floor(times.length*.95)],final:grabs.map((g,k)=>({held:g.gripped,angle:g.angle,distance:g.distance,reserve:g.armPlan.reserve,outward:bend(pose)[k].pole[0]*(k===0?1:-1),elbow:pose[arms[k][2]].slice(0,3)})),trace};})()`,c);
 fs.writeFileSync(path.join(out,name+'-motion.json'),JSON.stringify(report.trace));delete report.trace;
 assert(report.maxLimit<1e-11,name+' PHAT');assert(report.maxLength<1e-8,name+' bone lengths');assert(report.maxSwivel.every(v=>v<=8.00001),name+' swivel speed');assert(report.first.every(t=>t!==null),name+' acquisition');assert(report.final.every(h=>h.held),name+' maintained grip');assert.equal(report.planCalls,2,name+' one body plan per hand');
 return {name,...report};
}
(async()=>{try{
 fs.mkdirSync(out,{recursive:true});const fixture=json(path.join(lab,'fixtures/elbow_blend.json')),results=[];
 for(const blend of [0,.25,.5,.75,1]){
  const r=await run('blend-'+blend,fixture,{restart:true,blend});
  assert(r.swivel.every(v=>v<90),'No orbit at blend '+blend);assert(r.settled.every(v=>v<1e-5));assert(r.final.every(h=>h.angle<.001&&h.distance<.001&&h.outward>0),'Outward feasible posture at blend '+blend);
  if(results.length)for(let k=0;k<2;k++)assert(r.final[k].elbow[2]<results.at(-1).final[k].elbow[2],'Blend lowers each elbow monotonically');results.push(r);
 }
 results.push(await run('resume-held',fixture));results.push(await run('live-blend',fixture,{restart:true,blend:0,dynamic:true}));
 for(const amplitude of [20,50])results.push(await run('drag-'+amplitude,fixture,{drag:amplitude}));
 for(const name of ['UE_Elbow_Circling_Recorded','TestNN_Right_Recorded','TestNN_Right_Stalled_250'])results.push(await run(name,json(path.join(lab,'snapshots',name+'.json'))));
 fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({passed:true,results},null,2));console.log(JSON.stringify({passed:true,results},null,2));
 }finally{child.stdin.end();}})().catch(e=>{console.error(e);child.kill();process.exitCode=1;});
