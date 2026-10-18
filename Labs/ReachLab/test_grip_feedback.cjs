// Isolated native-body kernel + the real lab arm/grab code. No desktop writes.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict'),{spawn}=require('child_process'),readline=require('readline');
const R=require('../SwordHolsterLab/recovery.js'),W=require('./wrist.js'),lab=__dirname,root=path.resolve(lab,'../..'),out=path.join(root,'Saved/Diagnostics/ReachGripFeedback20261016');
const json=p=>JSON.parse(fs.readFileSync(p,'utf8')),clone=x=>JSON.parse(JSON.stringify(x));
const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(lab,'test_kernel.py')],{windowsHide:true,stdio:['pipe','pipe','inherit']}),jobs=[];
readline.createInterface({input:child.stdout}).on('line',s=>{const j=jobs.shift(),r=JSON.parse(s);r.error?j.reject(Error(r.error)):j.resolve(r);});
const kernel=(p,b)=>new Promise((resolve,reject)=>{jobs.push({resolve,reject});child.stdin.write(JSON.stringify(b)+'\n');});
function context(){
 const c=vm.createContext({console,performance,callKernel:kernel,document:{getElementById:()=>({textContent:''})},Recovery:R,ReachWrist:W,data:json(path.join(lab,'data.json')),fingers:json(path.join(lab,'fingers.json')),defaultsData:json(path.join(lab,'reset_defaults.json'))});
 for(const f of ['grab.js','coupled.js'])vm.runInContext(fs.readFileSync(path.join(lab,f),'utf8'),c);
 const app=fs.readFileSync(path.join(lab,'app.js'),'utf8');vm.runInContext(app.slice(0,app.indexOf('const renderer=')),c);
 vm.runInContext('dataset=data;referenceBase=copy(data.base);resetDefaults=defaultsData;setBasePose(null);fingerData=fingers;fingerModels=[0,1].map(k=>ReachGrab.build(fingerData,k));ready=true;post=callKernel;function drawAll(){};',c);return c;
}
function makeFixture(c,n,legacy){
 c.n=n;c.legacy=legacy;c.template=json(path.join(lab,'fixtures/elbow_blend.json'));
 return vm.runInContext(`(()=>{
  const s=copy(template);delete s.motion;delete s.motionRef;s.playing=false;s.tick=n.tick;s.basePose=copy(n.base);s.pose=copy(n.pose);s.solverState=copy(n.state);s.handQ=hands.map(j=>n.pose[j].slice(3));s.returns=[null,null];s.wholeReturn=null;s.settings=defaults();
  s.settings.closure=n.angles[0];s.settings.grip=n.angles[1];s.settings.syncRotation=n.tuning[0];s.settings.elbowDownBlend=n.tuning[1];s.phat.wrists=n.hands.map(h=>h.joint);
  s.grabs=n.hands.map((h,k)=>{
   const radius=norm(sub(h.surface,h.ball.slice(0,3))),rotation=h.target.slice(3),normal=h.normal,center=sub(add(h.target.slice(0,3),R.rotate(rotation,h.palm)),mul(normal,radius+.35)),ball=[...center,...h.ball.slice(3)];
   const input={enabled:h.enabled,grab:h.grab,target:center,rotation:rotationDegrees(rotation),orientation:'target',radius,speed:h.speed,rotationSpeed:h.rotationSpeed};s.settings.hands[k]=input;
   const g={...ReachGrab.fresh(center),active:h.grab,gripped:h.gripped,close:h.close,curl:h.curl,contacts:h.contacts,radius,rotation,normal,palm:h.palm,key:ReachGrab.key(input),fitted:true,fitCount:1,ball,clearance:0};
   const actual=ReachGrab.relative(n.actualHands[k],n.space);
   if(g.gripped)g.attachment=ReachGrab.relative(ball,legacy?actual:h.target);
   g.feedback={legacy,goal:ReachGrab.relative(h.target,ball),normal:R.rotate(R.qinv(ball.slice(3)),normal),lastCenter:center};return g;
  });
  s.scenario={name:legacy?'UE grip feedback — before':'UE grip feedback — corrected',absoluteTick:n.tick,source:'ReachGripFeedback20261016/native-before.json',baseMode:'Captured native pose, contacts and actual grip mismatch; closed rigid-joint target feedback. No Jolt forces/collisions.'};
  const frame={basePose:copy(s.basePose),targets:s.grabs.map((g,k)=>({center:s.settings.hands[k].target,rotation:g.rotation,normal:g.normal}))};
  s.motion={startTick:s.tick,initial:copy(s),frames:[copy(frame),copy(frame)]};return s;
 })()`,c);
}
function restore(c,s){c.initial=s;vm.runInContext('setBasePose(initial.basePose);settings=copy(initial.settings);phat=copy(initial.phat);pose=copy(initial.pose);solverState=copy(initial.solverState);handQ=copy(initial.handQ);grabs=copy(initial.grabs);returns=copy(initial.returns);wholeReturn=copy(initial.wholeReturn);ticks=initial.tick;scenarioMotion=null;',c);}
async function run(c,s,options={}){
 restore(c,s);c.options=options;
 return vm.runInContext(`(async()=>{
 const result={first:[null,null],swivel:[0,0],signed:[0,0],min:[0,0],max:[0,0],maxStep:[0,0],maxLimit:0,maxLength:0,trace:[]};
 const bend=p=>arms.map(a=>{const axis=normalize(sub(p[a[3]].slice(0,3),p[a[1]].slice(0,3))),v=sub(p[a[2]].slice(0,3),p[a[1]].slice(0,3));return {axis,p:normalize(sub(v,mul(axis,dot(v,axis))))};});
 for(let i=0;i<(options.frames||480);i++){
  if(options.perturb)for(const g of grabs)if(g?.gripped)g.ball=[...add(g.ball.slice(0,3),[.03,-.02,.01]),...R.qm(R.qexp([.001,-.0005,.0008]),g.ball.slice(3))];
  if(options.drag&&i>=100&&i<220)settings.hands[1].target=add(settings.hands[1].target,[0,0,options.drag*2*Math.PI/120*Math.cos((i-100)*2*Math.PI/120)]);
  if(options.blend){if(i===100)settings.elbowDownBlend=0;if(i===220)settings.elbowDownBlend=1;}
  const old=bend(pose);await step(1,false);const now=bend(pose);
  for(let k=0;k<2;k++){
   if(grabs[k]?.gripped&&result.first[k]===null)result.first[k]=ticks;
   const prev=R.rotate(R.fromTo(old[k].axis,now[k].axis),old[k].p),a=Math.atan2(dot(cross(prev,now[k].p),now[k].axis),dot(prev,now[k].p))*180/Math.PI;
   result.signed[k]+=a;result.min[k]=Math.min(result.min[k],result.signed[k]);result.max[k]=Math.max(result.max[k],result.signed[k]);result.swivel[k]+=Math.abs(a);result.maxStep[k]=Math.max(result.maxStep[k],Math.abs(a));
   const [u,e,h]=arms[k].slice(1),q=pose[h].slice(3),limited=ReachWrist.constrain(phat.wrists[k],pose[e].slice(3),q);result.maxLimit=Math.max(result.maxLimit,1-Math.abs(dot(q,limited)));
   for(let j=0;j<2;j++)result.maxLength=Math.max(result.maxLength,Math.abs(norm(sub(pose[[e,h][j]].slice(0,3),pose[[u,e][j]].slice(0,3)))-armLengths[k][j]));
  }
  result.trace.push({tick:ticks,pose:copy(pose),balls:grabs.map(g=>g.ball),held:grabs.map(g=>g.gripped),reserve:grabs.map(g=>g.armPlan?.reserve)});
 }
 result.final=grabs.map(g=>({held:g.gripped,angle:g.angle,distance:g.distance,reserve:g.armPlan?.reserve}));return result;
 })()`,c);
}
(async()=>{try{
 fs.mkdirSync(out,{recursive:true});const rows=json(path.join(out,'native-before.json')).rows,c=context(),start=rows.find(r=>r.tick===120),fixtures={};
 const results=[];
 for(const legacy of [true,false]){
  const name=legacy?'UE_Grip_Feedback_Before':'UE_Grip_Feedback',fixture=makeFixture(c,start,legacy);fixtures[name]=fixture;fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(fixture));
  let stablePoseTrace;
  for(const mode of (legacy?['stationary']:['stationary','disturbance','drag','blend'])){
   const r=await run(c,fixture,{drag:mode==='drag'?10:0,blend:mode==='blend',perturb:mode==='disturbance'});
   const poseTrace=JSON.stringify(r.trace.map(t=>t.pose));if(mode==='stationary')stablePoseTrace=poseTrace;
   if(mode==='disturbance')assert.equal(poseTrace,stablePoseTrace,'Physical output disturbance must not become an authored command');
   r.settledCm=[13,17].map(j=>R.length(R.sub(r.trace.at(-1).pose[j].slice(0,3),r.trace.at(-61).pose[j].slice(0,3))));
   fs.writeFileSync(path.join(out,'latest-feedback-case.json'),JSON.stringify({name,mode,...r,trace:undefined},null,2));
   assert(r.maxLimit<1e-11&&r.maxLength<1e-8&&r.maxStep.every(a=>a<8.00001));assert(r.final.every(h=>h.held));
   if(legacy)assert(r.swivel[1]>300,'Old joint must reproduce excessive motion');
   else {assert(r.swivel[1]<(mode==='blend'?120:20),'Independent hold removes orbit');assert(r.settledCm.every(x=>x<.0001),'No late drift');}
   fs.writeFileSync(path.join(out,name+'-'+mode+'-motion.json'),JSON.stringify(r.trace));delete r.trace;results.push({name,mode,...r});
  }
 }
 fs.writeFileSync(path.join(out,'lab-feedback-results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
 }finally{child.stdin.end();}})().catch(e=>{console.error(e);child.kill();process.exitCode=1;});
