import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),{load}=require('./test-bank.cjs');
const fixture=JSON.parse(fs.readFileSync(new URL('data/release-before.json',import.meta.url))),run=load('walk',fixture.phase),model=K.prepare(run,fixture),checks=[],windows=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
for(const w of fixture.windows){
 const j=run.names.indexOf('foot_'+w.side),point=n=>model.sample(n/60).pose.points[j];
 const displacement=R.sub(point(w.end),point(w.start));
 check(w.start+' released foot advances instead of following NN stance',displacement[2]>w.displacement[2]*1.8&&displacement[2]>.35*displacement[1]);
 // The old fixture used different support and toe-off timing. Bound added lift
 // while allowing earlier preparation to reduce lift within this old window.
 check(w.start+' smoothed release does not inflate the old lift beyond the clearance budget',displacement[1]-w.displacement[1]<model.settings.clearance/100);
 const speeds=[],nnSpeeds=[];for(let i=w.start*2+1;i<=w.handoff*2;i++){speeds.push((model.frames[i].pose.points[j][2]-model.frames[i-1].pose.points[j][2])*120);nnSpeeds.push((model.frames[i].raw.points[j][2]-model.frames[i-1].raw.points[j][2])*120);}
 const maxSpeedChange=Math.max(...speeds.slice(1).map((v,i)=>Math.abs(v-speeds[i])));
 const maxAddedSpeedChange=Math.max(...speeds.slice(1).map((v,i)=>Math.abs(v-speeds[i])-Math.abs(nnSpeeds[i+1]-nnSpeeds[i])));
 check(w.start+' recovery never reverses or waits in place',Math.min(...speeds)>.05);
 check(w.start+' forward recovery has no catch-up velocity kick',maxAddedSpeedChange<.5);
 const f=model.sample(w.handoff/60),next=model.sample((w.handoff+.5)/60),nnSpeed=(next.raw.points[j][2]-f.raw.points[j][2])*120;
 const exit=model.frames.findIndex(f=>f.root[2]>=model.terrain.end&&f.influence===0),a=model.frames[exit],b=model.frames[exit+1];
 check(w.start+' completed recovery matches NN position and speed',Math.abs(a.pose.points[j][2]-a.raw.points[j][2])<1e-6&&Math.abs((b.pose.points[j][2]-a.pose.points[j][2])-(b.raw.points[j][2]-a.raw.points[j][2]))<1e-6);
 windows.push({...w,after:displacement,maxSpeedChange,maxAddedSpeedChange,joinSpeed:speeds.at(-1),nnSpeed});
}
check('Released shoes remain outside the treads',model.metrics.maxPenetration<1e-5);
check('Recovery remains inside leg reach',model.metrics.maxReachError<1e-5);
const result={passed:true,checks,windows};
fs.writeFileSync(new URL('release-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
