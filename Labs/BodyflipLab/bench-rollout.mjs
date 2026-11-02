import fs from 'node:fs';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js'),T=require('./throw-attack.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const input=JSON.parse(fs.readFileSync('Saved/Diagnostics/BodyflipPort20261030/slash-performance-input.json')),settings=C.sanitize(input.settings),m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(p=>read(p).clips).map(F.decodeJump),catalog=new Map(read('data/vanilla.json').clips.map(meta=>[meta.name,C.decode(meta,bytes(meta.file),names,parents)]));T.load(read('data/throws.json'));
const post=async(path,body)=>{const r=await fetch('http://127.0.0.1:8876'+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error(await r.text());return r.json();};
const run=F.decodeNN(await post('/run',{gait:settings.mode==='walk'?'walk':'run',duration:5,phase:settings.runPhase,drawn:settings.attack==='pike'||settings.attack.startsWith('slash')}));
const reports=[];for(let test=0;test<3;test++){
 let nnMs=0,nnCalls=0;const began=performance.now(),f=await F.prepare(run,jumps,settings,parents,reference,async request=>{nnCalls++;const t=performance.now(),result=await post('/resume',request);nnMs+=performance.now()-t;return result;},()=>false,catalog,{cooperative:false}),prepared=performance.now()-began;
 const sampleBegin=performance.now(),frames=[];for(let i=0;i<=Math.floor(settings.trimOut*60);i++){const sample=f.sample(i/60);if(test===0)frames.push({frame:i,pose:sample.pose,phase:sample.phase});}const sampleMs=performance.now()-sampleBegin;
 reports.push({test,preparedMs:prepared,nnMs,nnCalls,sampleMs,aim:f.segments[1].physical.track.statistics,pushes:f.events.map(e=>e.pushTime)});console.log(reports.at(-1));
 if(test===0)fs.writeFileSync('Saved/Diagnostics/BodyflipPort20261030/rollout-native-frames.json',JSON.stringify({names,parents,frames}));
}
fs.writeFileSync('Saved/Diagnostics/BodyflipPort20261030/rollout-benchmark.json',JSON.stringify(reports,null,2));
