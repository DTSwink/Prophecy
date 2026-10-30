import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),base=process.cwd()+'/Labs/BodyflipLab/',R=require(base+'recovery.js'),C=require(base+'core.js');


const F=require(base+'flight.js'),read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),fixture=read(base+'fixtures/'+(process.argv.includes('--backward')?'landing-heading':'landing-continuity')+'.json'),state={settings:fixture.settings},settings=C.sanitize({...state.settings,...JSON.parse(process.env.AUDIT_SETTINGS||'{}')}),manifest=read(base+'data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['jumps.json','jumps-standing.json'].flatMap(f=>read(base+'data/'+f).clips).map(F.decodeJump);
const gait=settings.mode==='jump'?'run':'walk',drawn=settings.attack==='pike'||settings.attack.startsWith('slash'),stem=gait+(drawn?'-drawn':'')+'-phases',meta=read(base+'data/'+stem+'.json'),width=3+meta.names.length*12,countFrames=Math.ceil(5*meta.fps)+2,phase=Math.round((settings.runPhase%1)*meta.stride),bytes=Buffer.alloc(countFrames*width*4),fd=fs.openSync(base+'data/'+stem+'.bin','r');
try{if(fs.readSync(fd,bytes,0,bytes.length,phase*meta.framesPerPhase*width*4)!==bytes.length)throw Error('Incomplete cached phase');}finally{fs.closeSync(fd);}
const roots=[],poses=[];for(let f=0;f<countFrames;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}





import assert from 'node:assert/strict';
const run=F.decodeNN({...meta,duration:5,roots,poses}),floor={id:'floor',position:[0,-.2,0],rotation:[0,0,0,1],size:[200,.4,200]},input={...settings,airFlip:false,platforms:[floor],ramps:false,surfaceIK:false,jumpEvents:[],trimOut:.5},checks=[];
const check=(ok,label)=>{assert(ok,label);checks.push(label);},distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
for(const mode of ['idle','walk','jump','spaceGym']){
 const baseline=F.sequence(run,jumps,{...input,mode,startYaw:0},parents,reference,null,null,{horizon:.5});
 for(const yaw of [-180,-90,45,90,180]){
  const seq=F.sequence(run,jumps,{...input,mode,startYaw:yaw},parents,reference,null,null,{horizon:.5}),q=R.qexp([0,yaw*Math.PI/180,0]);
  for(const t of [0,.2,.4]){const a=baseline.sample(t),b=seq.sample(t);
   for(let i=0;i<names.length;i++){check(distance(b.pose.points[i],R.add(a.root,R.rotate(q,R.sub(a.pose.points[i],a.root))))<1e-6,'Yawed position '+mode+'/'+yaw+'/'+t+'/'+i);check(angle(b.pose.q[i],R.qm(q,a.pose.q[i]))<1e-6,'Yawed orientation '+mode+'/'+yaw+'/'+t+'/'+i);}
  }
 }
}

check(C.sanitize({}).startYaw===0,'Old scenes default to zero');check(C.sanitize({startYaw:NaN}).startYaw===0,'Finite yaw');
const requests=[],policy=async q=>{requests.push(q);const pose=q.seeds[1],origin=q.roots[1];return {names:q.names.slice(1),fps:30,duration:(q.frames-1)/30,roots:q.roots.slice(1,q.frames+1),poses:Array.from({length:q.frames},(_,i)=>({points:pose.points.slice(1).map(p=>R.add(p,R.sub(q.roots[i+1],origin))),axes:pose.axes.slice(1)})),continuation:{}};};
const seq=await F.prepare(run,jumps,{...input,mode:'jump',startYaw:180,trimOut:.5},parents,reference,policy),q=requests[0];
check(q.roots[2][2]<q.roots[1][2],'NN commands backward velocity in facing frame');
for(const time of [0,.2,.5]){const f=seq.sample(time);check(Math.abs(f.root[0])<1e-8&&Math.abs(f.root[2]-seq.speed*time)<1e-7,'World travel direction unchanged');check(R.rotate(f.pose.q[0],[0,0,1])[2]<-.99,'Root faces backwards');}
check(q.frames<=17,'Initial NN generation bounded by trim');const prefix=JSON.stringify(seq.sample(.2));await seq.extend(.8);check(prefix===JSON.stringify(seq.sample(.2)),'Yawed NN prefix retained on trim extension');check(requests.at(-1).continuation,'NN extension retains recurrence');
console.log(JSON.stringify({passed:true,checks:checks.length}));
