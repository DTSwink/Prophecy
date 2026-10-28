const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert/strict'),{createRequire}=require('module');
const file=path.resolve(__dirname,'footik.js'),req=createRequire(file),box={module:{exports:{}},exports:{},require:req,console};
vm.runInNewContext(fs.readFileSync(__dirname+'/snapshots/pre-step-accent-footik.js','utf8'),box);
const old=box.module.exports,K=req(file),R=req('./recovery.js'),S=req('./support.js');
(async()=>{
 const cache=__dirname+'/snapshots/step-accent-source.json';
 let data;
 if(fs.existsSync(cache))data=JSON.parse(fs.readFileSync(cache));
 else{const response=await fetch('http://127.0.0.1:8890/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'direction',policy:'run',gait:'walk',duration:5,phase:.36,direction:'forward',rootYawSpeed:300,rootYawStart:1.2,rootYawStop:6})});assert(response.ok);data=await response.json();fs.writeFileSync(cache,JSON.stringify(data));}
 const run=K.decode(data,JSON.parse(fs.readFileSync(__dirname+'/data/rig.json')).parents),settings={gait:'walk',phase:.36,terrain:'stairs',height:16,depth:35,steps:12,enabled:true,clearance:1,pelvis:30,rootYawSpeed:300,rootYawStart:1.2,rootYawStop:6},before=old.prepare(run,settings),results=[];
 for(const accent of[0,100,150,200,300,400]){
  const m=K.prepare(run,{...settings,stepAccent:accent}),y=m.frames.map(f=>f.pelvisTransfer||0),v=y.slice(1).map((x,i)=>(x-y[i])*120);
  let ankle=0,pin=0,states=0;
  for(let i=0;i<m.frames.length;i++)for(let side=0;side<2;side++){
   const a=m.frames[i],b=before.frames[i],l=S.leg(a.raw,run.names,side?'R':'L');
   ankle=Math.max(ankle,R.length(R.sub(a.pose.points[l.foot],b.pose.points[l.foot])));
   if(a.feet[side].contact)pin=Math.max(pin,2*Math.acos(Math.min(1,Math.abs(R.dot(a.pose.q[l.foot],b.pose.q[l.foot])))));
   if(a.feet[side].state!==b.feet[side].state)states++;
  }
  const result={accent,loadingCm:-Math.min(...y)*100,maxV:Math.max(...v.map(Math.abs)),maxA:Math.max(...v.slice(1).map((x,i)=>Math.abs(x-v[i])*120)),ankle,pin,states,metrics:m.metrics};
  if(accent===100)assert.equal(JSON.stringify(m.frames),JSON.stringify(before.frames),'100 restores exact previous motion');
  if(accent===0)assert(y.every(x=>x===0),'0 disables accent');
  assert(ankle<1e-7&&pin<1e-6&&states===0,'foot paths, planted orientation and timings unchanged');
  assert(m.metrics.maxPenetration<1e-5&&m.metrics.maxReachError<1e-6,'clearance and reach');
  assert(result.maxV<.4*Math.max(1,accent/200)&&result.maxA<10*Math.max(1,accent/200),'derivatives bounded proportionally to requested accent');
  assert(m.frames.filter(f=>!f.influence).every(f=>f.pose===f.raw),'NN regions unchanged');
  if(results.length)assert(result.loadingCm>=results.at(-1).loadingCm-1e-5,'higher accent must not reduce loading');
  results.push(result);console.log(JSON.stringify(result));
 }
 assert(results[3].loadingCm>results[1].loadingCm*1.5,'200 gives stronger loading');
 fs.writeFileSync(__dirname+'/snapshots/step-accent-verification.json',JSON.stringify({passed:true,results},null,2));
})();
