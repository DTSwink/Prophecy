const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),path=require('path'),{createRequire}=require('module');
const req=createRequire(path.join(__dirname,'surface.js')),F=req('./surface.js'),K=req('./footik.js'),R=req('./recovery.js'),{load}=req('./test-bank.cjs');
const read=p=>JSON.parse(fs.readFileSync(path.join(__dirname,p))),distance=(a,b)=>R.length(R.sub(a,b)),up=[0,1,0],wall=[0,0,-1],checks=[],cases=[];
const check=(label,ok)=>{assert(ok,label);checks.push(label);};
const settings=F.settings({inclineGravity:true});
for(const [angle,expected] of [[0,0],[44.9,0],[45,1],[67.5,1],[90,1]])check('incline threshold, no ramp '+angle,Math.abs(F.gravityShare([0,Math.cos(angle*Math.PI/180),-Math.sin(angle*Math.PI/180)],settings)-expected)<1e-9);
for(const angle of[45,60,90])for(const percent of[0,25,50,100]){
 const normal=[0,Math.cos(angle*Math.PI/180),-Math.sin(angle*Math.PI/180)],s={...settings,fullGravity:percent},share=F.gravityShare(normal,s),out=F.gravityDrive([3,20,-5],normal,share);
 check('full gravity independent of thrust '+angle+'/'+percent,F.gravityActive(normal,s));
 check('world vertical thrust only '+angle+'/'+percent,distance(out,[3,20*(1-percent/100),-5])<1e-9);
}
check('90 threshold is defined',F.gravityShare(wall,{...settings,minGravityIncline:90})===1&&F.gravityShare(up,{...settings,minGravityIncline:90})===0);
check('zero full gravity retains drive',F.gravityShare(wall,{...settings,fullGravity:0})===0);
check('full wall gravity removes vertical controller force',Math.abs(F.gravityDrive([3,20,-5],wall,1)[1])<1e-12);
for(const percent of[0,25,50,100])for(const v of[[0,0,2],[1,0,2],[0,-.0002,2],[0,0,-2]]){
 const out=F.transferVelocity(v,up,wall,percent),project=R.sub(v,R.mul(wall,R.dot(v,wall))),expected=R.dot(project,project)+percent/100*(R.dot(v,v)-R.dot(project,project));
 check('transfer energy '+JSON.stringify([percent,v]),Math.abs(R.dot(out,out)-expected)<1e-9&&Math.abs(R.dot(out,wall))<1e-9);
 if(percent===0)check('projection endpoint '+v,distance(out,project)<1e-9);
 if(percent===100)check('transport direction '+v,Math.sign(out[1])===Math.sign(v[2]));
}
const box={module:{exports:{}},exports:{},require:req,console};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'snapshots/pre-incline-gravity-surface.js'),'utf8'),box);const before=box.module.exports;
const priorBox={module:{exports:{}},exports:{},require:req,console};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'snapshots/pre-root-thrust-surface.js'),'utf8'),priorBox);const prior=priorBox.module.exports;
{
 const run=load('walk',.69),s={inclineGravity:true,minGravityIncline:60,slopeAngle:45,fullGravity:100},a=prior.prepare(run,s),b=F.prepare(run,s);
 check('below minimum preserves previous motion',JSON.stringify(a.frames.map(f=>[f.pose,f.surface.mass,f.surface.velocity]))===JSON.stringify(b.frames.map(f=>[f.pose,f.surface.mass,f.surface.velocity])));
 const initial=F.prepare(run,{inclineGravity:true,minGravityIncline:45,slopeAngle:60,approach:'parallel',fullGravity:0}).frames[0].surface;
 check('zero percent does not switch gravity off',initial.gravityActive&&Math.abs(initial.acceleration[1]+9.81)<1e-9);
 check('no automatic gravity compensation above threshold',R.length(initial.drive)<1e-9&&R.length(initial.supportForce)<1e-9);
}
const rig=read('data/rig.json'),actual=K.decode(read('snapshots/step-accent-source.json'),rig.parents);
for(const [run,gait] of[[load('walk',.69),'walk'],[load('run',.21),'run'],[actual,'walk']])for(const angle of[45,67.5,90])for(const fullGravity of[0,100]){
 const label=[run===actual?'actual turning Walk':gait,angle,fullGravity].join('/'),s={gait,slopeAngle:angle,approach:'toward',inclineGravity:true,minGravityIncline:45,fullGravity,energyConservation:100},m=F.prepare(run,s);
 let velocityError=0,positionError=0,wallGravityError=0,activeFrames=0;
 for(let i=0;i<m.frames.length;i++){
  const f=m.frames[i],a=f.surface;
  assert(f.pose.points.flat().every(Number.isFinite));
  assert.deepEqual(a.gravity,[0,-9.81,0]);
  if(a.gravityActive){activeFrames++;if(fullGravity===100){wallGravityError=Math.max(wallGravityError,Math.abs(a.acceleration[1]+9.81));assert(a.drive[1]===0);assert(a.supportForce[1]===0);}}
  if(i+1<m.frames.length){const b=m.frames[i+1].surface,v=R.add(a.velocity,R.mul(a.acceleration,1/120));velocityError=Math.max(velocityError,distance(b.velocity,R.add(v,a.collisionImpulse)));positionError=Math.max(positionError,distance(b.mass,R.add(R.add(a.mass,R.mul(v,1/120)),a.collisionCorrection)));}
 }
 check(label+' exact integration',velocityError<1e-9&&positionError<1e-9);
 check(label+' full vertical acceleration is gravity on every active slope',wallGravityError<1e-8&&activeFrames>0);
 check(label+' shoes clear and legs remain reachable',m.metrics.maxPenetration<1e-4&&m.metrics.maxReachError<1e-7);
 check(label+' material pins remain fixed',m.metrics.maxContactDrift<1e-8);
 const transfers=m.events.filter(e=>e.type==='root-transfer');
 check(label+' transfers do not create kinetic energy',transfers.every(e=>R.length(e.after)<=R.length(e.before)+1e-9));
 check(label+' no timer expiry',m.events.every(e=>e.type!=='wall-release'));
 cases.push({label,metrics:m.metrics,wallGravityError,activeFrames,transfers:transfers.length,maxHeight:Math.max(...m.frames.map(f=>f.surface.mass[1]))});
}
for(const angle of[0,45,90]){
 const s={gait:'walk',slopeAngle:angle,inclineGravity:false},run=load('walk',.69),a=before.prepare(run,s),b=F.prepare(run,s);
 check('mode off exact previous frames '+angle,JSON.stringify(a.frames)===JSON.stringify(b.frames));
}
const run=load('walk',.69),s={gait:'walk',slopeAngle:90,inclineGravity:true,fullGravity:100};
const no=F.prepare(run,{...s,energyConservation:0}),yes=F.prepare(run,{...s,energyConservation:100});
const e0=no.events.find(e=>e.type==='root-transfer'),e1=yes.events.find(e=>e.type==='root-transfer');
check('initial wall 0 loses forward speed',Math.abs(e0.after[1])<.002);
check('initial wall 100 redirects forward speed upward',e1.after[1]>1.99&&Math.abs(R.length(e1.before)-R.length(e1.after))<1e-9);
check('conserved entry climbs higher under gravity',Math.max(...yes.frames.map(f=>f.surface.mass[1]))>Math.max(...no.frames.map(f=>f.surface.mass[1]))+.15);
const report={passed:true,checks:checks.length,cases};fs.writeFileSync(path.join(__dirname,'snapshots/incline-gravity-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({passed:true,checks:checks.length,cases:cases.length}));
