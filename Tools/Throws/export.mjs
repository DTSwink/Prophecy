import fs from 'node:fs';
import crypto from 'node:crypto';
import {data,assets,saved,R,model,openReference} from './lab-reference.mjs';
const sim=await openReference(),profiles=[];
try{
 for(const c of data.clips){const m=model(sim,c.id,1),asset=assets[m.kind];profiles.push({id:c.id,names:data.names,parents:data.parents,fps:c.fps,end:c.duration*60,release:m.release,controls:m.controls,kind:m.kind,grip:m.grip,scale:m.scale,bind:asset.bind||{position:[0,0,0],rotation:[0,0,0,1]},longAxis:R.rotate(R.qinv(m.seed.q),m.seed.axis),mass:asset.mass,com:m.seed.comOffset,velocity:m.seed.v,twist:m.seed.twist,target:m.target,locals:m.clip.locals.map(l=>l.p.map((p,j)=>[...p,...l.q[j]])),curve:m.curve});}
 const profileFile=new URL('../../Content/ThrowLab/Profile.json',import.meta.url);
 const source=new URL('../../Labs/ThrowLab/approved/2026-10-29/saved-profile.json',import.meta.url);
 const result={schema:1,checkpoint:'a193d263',profileSha256:crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex'),profiles};
 fs.writeFileSync(profileFile,JSON.stringify(result));
 const cases=[];
 for(const p of profiles)for(const amount of p.id==='small-throw'?[0,.05,.25,.37,.5,.75,.99,1]:[1])for(const target of [p.target,[3,2,-2]]){
  const m=model(sim,p.id,amount,{target});
  const frames=[0,m.trigger-.0001,m.trigger,m.trigger+.0001,m.trigger+.2,m.releaseFrame,m.finish-.0001,m.finish,m.finish+.0001,m.finish+1,m.finish+8,p.end];
  for(let f=0;f<=p.end;f+=1.125)frames.push(f);
  cases.push({id:p.id,amount,target,release:m.releaseFrame,launch:m.launch,samples:[...new Set(frames.filter(f=>f>=0&&f<=p.end))].sort((a,b)=>a-b).map(frame=>({frame,pose:m.sample(frame).points.map((p,j)=>[...p,...m.sample(frame).q[j]])}))});
 }
 const out=new URL('../../Saved/Diagnostics/ThrowPort20261029/reference.json',import.meta.url);fs.mkdirSync(new URL('.',out),{recursive:true});fs.writeFileSync(out,JSON.stringify({cases}));
 console.log(JSON.stringify({profiles:profiles.length,cases:cases.length,samples:cases.reduce((n,c)=>n+c.samples.length,0),bytes:fs.statSync(profileFile).size,sha:result.profileSha256}));
}finally{sim.dispose();}
