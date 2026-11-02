'use strict';
// Bounded, no-inference profile of an expired prediction followed by actual
// displayed history. Instrumentation is loaded only in this private process.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const {Worker,isMainThread,parentPort}=require('node:worker_threads');
if(isMainThread){
 const worker=new Worker(__filename),timer=setTimeout(()=>{worker.terminate();process.exitCode=1;console.error('30-second planner profile watchdog');},30000);
 worker.on('message',r=>console.log(JSON.stringify(r,null,2)));worker.on('error',e=>{console.error(e);process.exitCode=1;});worker.on('exit',()=>clearTimeout(timer));
}else{
 const folder=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),kfile=path.resolve(__dirname,'../../Labs/FootIKLab/footik.js'),stages={},calls=[];
 const mark=(name,fn)=>{const t=performance.now();try{return fn();}finally{const s=stages[name]??={calls:0,ms:0};s.calls++;s.ms+=performance.now()-t;}};
 global.__footikPlanningMark=mark;
 let text=fs.readFileSync(kfile,'utf8').replace("'use strict';","'use strict';const profileMark=global.__footikPlanningMark;");
 for(const name of ['decode','stableLeg','geometry','clearanceCurve','solve','at'])text=text.replace('function '+name+'(',`function ${name}(...args){return profileMark('${name}',()=>profile_${name}(...args));}\nfunction profile_${name}(`);
 const m=new Module(kfile,module);m.filename=kfile;m.paths=Module._nodeModulePaths(path.dirname(kfile));m._compile(text,kfile);require.cache[kfile]=m;
 const K=m.exports,T=require('../../Labs/FootIKLab/terrain.js'),P=require('./live-stair-planner.cjs');
 const prepare=K.prepare;K.prepare=(run,s,host)=>{
  const terrain=host.terrain,original=terrain.floorFor;terrain.floorFor=(...args)=>mark('floorFor',()=>original(...args));
  const began=performance.now(),before=structuredClone(stages);try{return prepare(run,s,host);}finally{terrain.floorFor=original;calls.push({frames:Math.round(run.duration*120)+1,boundary:!!host.contacts,ms:performance.now()-began,stages:Object.fromEntries(Object.entries(stages).map(([k,v])=>[k,{calls:v.calls-(before[k]?.calls||0),ms:v.ms-(before[k]?.ms||0)}]))});}
 };
 const input=JSON.parse(fs.readFileSync(path.join(folder,'walk-stairs.input.json'))),run=K.decode(input.source,input.parents),standard=T.create(input.settings);
 function frame(tick){const p=K.at(run,tick/120),height=standard.rootHeight(p.points[0][2]),pose={...p,points:p.points.map(v=>[v[0],v[1]+height,v[2]])};return {pose,raw:pose,root:pose.points[0],rootHeading:[0,0,1],pelvisOffset:0,influence:0,feet:[20,24].map((j,i)=>({side:i?'R':'L',state:'NN',target:pose.points[j],contact:null,error:0,penetration:0}))};}
 function window(from,to){const source={...input.source,roots:input.source.roots.slice(from/4,to/4+1),poses:input.source.poses.slice(from/4,to/4+1),rootYawDegrees:Array.from({length:(to-from)/4+1},()=>0),duration:(to-from)/120,totalDuration:(to-from)/120};source.directionMeta={...source.directionMeta,totalDuration:source.duration};return {source,sourceStartTick:from,terrain:{rootStartTick:from,rootRows:source.roots.map((p,i)=>({time:i/30,position:[p[0],standard.rootHeight(p[2]),p[2]]})),tiles:standard.tiles.map(t=>({id:t.id,point:[0,t.y,0],u:[1,0,0],v:[0,0,1],bounds:[t.x0,t.x1,t.z0,t.z1],shaped:t.id.startsWith('step')}))}};}
 (async()=>{const began=performance.now(),cpu=process.cpuUsage(),p=P.create({...input,...window(0,48),origin:[0,0,0],handoff:false});await p.plan();const result=await p.plan({...window(176,324),acceptedFrames:Array.from({length:181},(_,tick)=>({tick,frame:frame(tick)}))});if(!result.ready)throw Error('Profile did not publish');const used=process.cpuUsage(cpu),report={passed:true,wallMs:performance.now()-began,cpuMs:(used.user+used.system)/1000,status:p.status,stages,calls};fs.writeFileSync(path.join(folder,'live-planning-profile.json'),JSON.stringify(report,null,2));parentPort.postMessage(report);p.cancel();})().catch(e=>{console.error(e);process.exitCode=1;});
}
