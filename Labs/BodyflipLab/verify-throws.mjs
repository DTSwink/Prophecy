import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
import {openReference,model as original} from '../../Tools/Throws/lab-reference.mjs';
const require=createRequire(import.meta.url),T=require('./throw-attack.js'),C=require('./core.js'),R=require('./recovery.js');
T.load(JSON.parse(fs.readFileSync(new URL('data/throws.json',import.meta.url))));const sim=await openReference();let checks=0,max=0;
const near=(a,b,label,tol=1e-10)=>{const d=R.length(R.sub(a,b));max=Math.max(max,d);assert(d<tol,label+': '+d);checks++;};
for(const [kind,p]of Object.entries(T.data.physical)){const axes=R.toAxes(p.rotation);for(let i=0;i<3;i++)for(let j=0;j<3;j++){const rebuilt=axes.reduce((n,a,k)=>n+a[i]*p.principal[k]*a[j],0);assert(Math.abs(rebuilt-p.inertia[j][i])<2e-11,'physical inertia '+kind);checks++;}assert(p.principal.every(v=>v>0),'positive principal moments');checks++;}
try{for(const id of ['big-throw','small-throw'])for(const amount of id==='big-throw'?[1]:[0,.1,.37,.65,1]){const a=original(sim,id,amount),b=T.model(id,amount);near([a.releaseFrame,a.trigger,a.finish],[b.releaseFrame,b.trigger,b.finish],'timing');for(const key of ['p','q','v','omega','axis'])near(a.launch[key],b.launch[key],'launch '+id+'/'+amount+'/'+key);for(let f=0;f<=a.clip.duration*60;f+=.5){const p=a.sample(f),q=b.sample(f);for(let i=0;i<p.points.length;i++){near(p.points[i],q.points[i],'point');near(p.q[i],q.q[i],'rotation');}}}}
finally{sim.dispose();}
const manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),reference=C.poseFromShared(manifest),{names,parents}=manifest;
const source=t=>({pose:reference,root:reference.points[0],velocity:[0,0,0],phase:'SPACE'}),segment={sample:source,airStart:0,jumpStart:0,abortTime:Infinity};
for(const id of ['big-throw','small-throw']){
 const track=T.create({id:'throw',attack:id,throwCharge:37,throwSpeed:1},segment,null,names,parents,C.sanitize(),reference),pose=track.sample(track.releaseTime).pose,packet=track.launchAt(pose);
 assert(track.releaseTime>0&&packet.kind===(id==='big-throw'?'spear':'bomb'));checks++;
 for(const axis of [[.4,.7,-.3],[0,Math.PI,0]]){const turn=R.qexp(axis),delta=[2,-1,4],rotated={points:pose.points.map(p=>R.add(R.rotate(turn,p),delta)),q:pose.q.map(q=>R.qm(turn,q))},p=track.launchAt(rotated,R.rotate(turn,[1,2,3])),expected=track.launchAt(pose,[1,2,3]);near(p.p,R.add(R.rotate(turn,expected.p),delta),'launch position covariance');near(p.v,R.rotate(turn,expected.v),'launch velocity covariance');near(p.omega,R.rotate(turn,expected.omega),'launch spin covariance');}
 const a=track.sample(track.returnEnd-1e-8).pose,b=track.sample(track.returnEnd).pose;for(let i=0;i<names.length;i++)near(a.points[i],b.points[i],'return position',1e-5);
}
console.log(JSON.stringify({passed:true,checks,maxDifference:max}));
