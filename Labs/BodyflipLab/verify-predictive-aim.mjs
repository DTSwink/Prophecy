import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),H=require('./attack-inertia.js'),K=require('./kick-attack.js'),Aim=require('./attack-aim.js'),F=require('./flight.js'),I=require('./idle.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),meta=read('data/vanilla.json'),catalog=new Map(meta.clips.map(v=>[v.name,C.decode(v,bytes(v.file),names,parents)]));
const dist=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),directionError=(a,b)=>dist(R.unit(a),R.unit(b));

const Project=require('./target-rig.js').create(names,parents,reference),project=p=>Project.project(p);
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),m).motion(),results=[];
for(const name of ['slashL','slashR','KickR','headbutt','sweepKick','pike'])for(const rate of [-360,360]){
 const settings=C.sanitize({mode:'spaceGym',spinLag:.6,spinInertia:1,kickToArmed:true,aimWeight:1,jumpEvents:[{id:'a',time:.1,spinVersion:2,instantSpin:true,flip:rate,twist:150,jumpPercent:0,attack:name,attackDelay:.2}],trimOut:4}),seq=F.sequence(idle,jumps,settings,parents,reference,null,catalog,{horizon:4}),track=seq.segments[0].attack,clip=catalog.get(name),plan=Aim.create({clip,track,names,parents,reference,sampleHit:t=>seq.sample(t).pose,project}),raw=seq.sample(track.hitTime).pose;
 for(const v of [[0,0,1],[0,0,-1],[1,.5,-.5],[0,1,0],[0,-1,0]]){
  const target=R.add(plan.origin,R.mul(R.unit(v),1.5)),pose=project(plan.apply(raw,track.hitTime,target)),error=directionError(R.sub(plan.point(pose),Aim.center(pose,plan.rig)),v),dCOM=dist(Aim.center(raw,plan.rig),Aim.center(pose,plan.rig));
  results.push({name,rate,v,error,dCOM,parameters:plan.solution(target).parameters});
  assert(pose.points.flat().every(Number.isFinite));assert(dCOM<1e-8);assert(error<1e-5,JSON.stringify(results.at(-1)));
 }
 console.log(name,rate,'ok');
}
fs.mkdirSync('Saved/BodyflipLab/PredictiveAim',{recursive:true});fs.writeFileSync('Saved/BodyflipLab/PredictiveAim/results.json',JSON.stringify(results,null,2));console.log({cases:results.length,maxError:Math.max(...results.map(r=>r.error))});
