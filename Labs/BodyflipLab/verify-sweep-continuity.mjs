import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),B=require('./airborne-motion.js'),K=require('./kick-attack.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),m=read('data/manifest.json'),reference=C.poseFromShared(m),metas=read('data/vanilla.json'),folder=new URL('../../Saved/BodyflipLab/SweepFollowup/',import.meta.url);
const load=(name,deps={})=>{const module={exports:{}};vm.runInNewContext(fs.readFileSync(new URL('before-'+name,folder),'utf8'),{module,require:n=>deps[n]||require(n)});return module.exports;};
const oldB=load('airborne-motion.js'),oldK=load('kick-attack.js',{'./airborne-motion.js':oldB}),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),decode=name=>{const meta=metas.clips.find(x=>x.name===name),b=fs.readFileSync(new URL(meta.file,import.meta.url));return C.decode(meta,b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),m.names,m.parents);};
const clip=decode('sweepKick'),args={clip,names:m.names,parents:m.parents,reference,directArmed:true,lead:.2,tail:.24708672},old=oldK.preview(args),now=K.preview(args),pelvis=m.names.indexOf('pelvis');let maxKeyError=0;
for(let f=0;f<36;f++){const a=old.track.at(f),b=now.track.at(f);maxKeyError=Math.max(maxKeyError,...a.q.map((q,j)=>angle(q,b.q[j])));}
assert(maxKeyError<1e-8,'authored key rotations unchanged');
const steps=[];for(let f=100;f<=105;f++){const t=f/60-41/60,p=t-1/60;steps.push({F:f,before:angle(old.track.sample(p).q[pelvis],old.track.sample(t).q[pelvis])*180/Math.PI,after:angle(now.track.sample(p).q[pelvis],now.track.sample(t).q[pelvis])*180/Math.PI});}
assert(steps.every((s,i)=>!i||s.after<steps[i-1].after),'reported interval slows progressively without the mid-frame detours');
let velocityGap=0;const eps=1e-5;
for(let f=9;f<35;f++){const t=now.track.lead+(f-8)/30,a=now.track.sample(t-eps),b=now.track.sample(t),c=now.track.sample(t+eps);for(let j=1;j<m.names.length;j++){const left=R.mul(R.qlog(R.qm(b.q[j],R.qinv(a.q[j]))),1/eps),right=R.mul(R.qlog(R.qm(c.q[j],R.qinv(b.q[j]))),1/eps);velocityGap=Math.max(velocityGap,R.length(R.sub(left,right)));}}
assert(velocityGap<.1,'continuous velocity at source keys');
let normalDifference=0,normalSamples=0;
for(const name of ['KickL','KickR'])for(const directArmed of [false,true]){const clip=decode(name),opts={...args,clip,directArmed},a=oldK.preview(opts),b=K.preview(opts);for(let i=0;i<=Math.ceil(a.track.stop*120);i++){const x=a.response.sample(i/120),y=b.response.sample(i/120);normalDifference=Math.max(normalDifference,...x.q.map((q,j)=>angle(q,y.q[j])),...x.points.map((p,j)=>R.length(R.sub(p,y.points[j]))));normalSamples++;}}
assert(normalDifference<1e-10,'normal kicks unchanged');
const result={passed:true,maxKeyError,velocityGap,normalDifference,normalSamples,steps};fs.writeFileSync(new URL('continuity.json',folder),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
