const fs=require('fs'),path=require('path'),vm=require('vm'),{spawn}=require('child_process'),readline=require('readline'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../..'),lab=__dirname,out=path.join(root,'Saved/Diagnostics/ReachHeld20261016');
const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'test_kernel.py')],{windowsHide:true,stdio:['pipe','pipe','inherit']});
const jobs=[];readline.createInterface({input:child.stdout}).on('line',l=>{const j=jobs.shift(),r=JSON.parse(l);if(r.error)j.reject(Error(r.error));else j.resolve(r);});
const kernel=(p,b)=>new Promise((resolve,reject)=>{jobs.push({resolve,reject});child.stdin.write(JSON.stringify(b)+'\n');});
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
function setup(source){
 const c=vm.createContext({console,performance,callKernel:kernel,document:{getElementById:()=>({textContent:''})},Recovery:require(path.join(lab,'../SwordHolsterLab/recovery.js')),ReachWrist:require(path.join(lab,'wrist.js')),initial:json(process.env.FIXTURE||path.join(out,'current.json')),data:json(path.join(lab,'data.json')),fingers:json(path.join(lab,'fingers.json')),defaultsData:json(path.join(lab,'reset_defaults.json'))});
 for(const f of ['grab.js'])vm.runInContext(fs.readFileSync(path.join(lab,f),'utf8'),c);
 vm.runInContext(source,c);const app=fs.readFileSync(path.join(lab,'app.js'),'utf8');vm.runInContext(app.slice(0,app.indexOf('const renderer=')),c);
 vm.runInContext(`dataset=data;referenceBase=copy(data.base);resetDefaults=defaultsData;setBasePose(initial.basePose);fingerData=fingers;fingerModels=[0,1].map(k=>ReachGrab.build(fingerData,k));settings=copy(initial.settings);phat=copy(initial.phat);pose=copy(initial.pose);solverState=copy(initial.solverState);handQ=copy(initial.handQ);grabs=copy(initial.grabs);returns=copy(initial.returns);wholeReturn=copy(initial.wholeReturn);ticks=initial.tick;scenarioMotion=initial.motion;ready=true;post=callKernel;function drawAll(){};`,c);
 return c;
}
(async()=>{try{
 const results=[],amplitude=Number(process.env.AMPLITUDE||50),period=Number(process.env.PERIOD||60);
 for(const version of ['before','after']){
  const source=fs.readFileSync(version==='before'?path.join(out,'coupled-before.js'):path.join(lab,'coupled.js'),'utf8');const c=setup(source);
  results.push(await vm.runInContext(`(async()=>{
   const target=copy(settings.hands[1].target),trace=[],first=[null,null];let maxStep=0,maxAcceleration=0,flips=0,maxLimit=0,maxLength=0,lastV=null,maxSwivel=0,swivelFlips=0,lastSwivel=0,maxAngle=0,maxLeftSettledStep=0;const before=copy(pose);
   const cam=initial.camera,f=normalize([-Math.sin(cam.yaw),-(.27-cam.pitch*.55),-Math.cos(cam.yaw)]),up=cross(normalize(cross(f,[0,1,0])),f),direction=${process.env.SCREEN!=='0'?'[up[0],up[2],up[1]]':'[0,0,1]'};
   for(let i=0;i<480;i++){
    if(${process.env.FIXTURE?'false':'true'})settings.hands[1].target=add(target,mul(direction,i<60||i>=420?0:${amplitude}*Math.sin((i-60)*2*Math.PI/${period})));
    const oldLeft=pose[12].slice(0,3);
    const e=pose[16].slice(0,3),oldS=pose[15].slice(0,3),oldAxis=normalize(sub(pose[17].slice(0,3),oldS)),oldBend=sub(sub(e,oldS),mul(oldAxis,dot(sub(e,oldS),oldAxis)));await step(1,false);const velocity=sub(pose[16].slice(0,3),e),acc=lastV?norm(sub(velocity,lastV)):0;
    const newS=pose[15].slice(0,3),newAxis=normalize(sub(pose[17].slice(0,3),newS)),newBend=normalize(sub(sub(pose[16].slice(0,3),newS),mul(newAxis,dot(sub(pose[16].slice(0,3),newS),newAxis)))),transport=normalize(R.rotate(R.fromTo(oldAxis,newAxis),oldBend)),swivel=Math.atan2(dot(cross(transport,newBend),newAxis),dot(transport,newBend))*180/Math.PI;
    if(swivel*lastSwivel<0&&Math.abs(swivel)>.5&&Math.abs(lastSwivel)>.5)swivelFlips++;lastSwivel=swivel;maxSwivel=Math.max(maxSwivel,Math.abs(swivel));maxAngle=Math.max(maxAngle,grabs[1].angle);
    maxStep=Math.max(maxStep,norm(velocity));maxAcceleration=Math.max(maxAcceleration,acc);if(lastV&&dot(velocity,lastV)<0&&norm(velocity)>.2&&norm(lastV)>.2)flips++;lastV=velocity;
    for(let k=0;k<2;k++)if(grabs[k].gripped&&first[k]===null)first[k]=ticks;
    if(ticks>=200&&ticks<=300)maxLeftSettledStep=Math.max(maxLeftSettledStep,norm(sub(pose[12].slice(0,3),oldLeft)));
    const q=pose[17].slice(3),limited=ReachWrist.constrain(phat.wrists[1],pose[16].slice(3),q);maxLimit=Math.max(maxLimit,1-Math.abs(dot(q,limited)));
    for(let k=0;k<2;k++)maxLength=Math.max(maxLength,Math.abs(norm(sub(pose[16+k].slice(0,3),pose[15+k].slice(0,3)))-armLengths[1][k]));
    trace.push({tick:ticks,target:settings.hands[1].target.slice(),elbow:pose[16].slice(),hand:pose[17].slice(),velocity,acc,swivel,cos:grabs[1].armPlan.cos,angle:grabs[1].angle,distance:grabs[1].distance});
   }
   return {version:${JSON.stringify(version)},first,maxStep,maxAcceleration,flips,maxSwivel,swivelFlips,maxAngle,maxLeftSettledStep,maxLimit,maxLength,held:grabs.map(g=>g.gripped),trace};
  })()`,c));
 }
 const [before,after]=results;
 assert(after.held.every(Boolean));assert(after.maxLimit<1e-12);assert(after.maxLength<1e-8);
 if(!process.env.FIXTURE){
  assert(after.maxSwivel<1e-7,'Held elbow plane must transport continuously, including through near-extension');
  assert.equal(after.swivelFlips,0);assert(after.maxAngle<=before.maxAngle+1);
  if(amplitude===50&&period===60)assert(before.maxSwivel>90,'The fixture must reproduce the reported plane flip');
 }else{assert(after.first.every(t=>t!==null));assert.deepEqual(Array.from(after.first),Array.from(before.first));assert(after.maxLeftSettledStep<.1);}
 const name=process.env.FIXTURE?'recorded':'held-'+amplitude+'-'+period;
 const report={passed:true,amplitude,period,results:results.map(({trace,...r})=>r)};
 fs.writeFileSync(path.join(out,name+'-full.json'),JSON.stringify(results));fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{child.stdin.end();}})().catch(e=>{console.error(e);process.exitCode=1;child.kill();});
