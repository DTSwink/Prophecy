// Offline audit/render input. Uses the actual lab mesh builder; no browser or UI.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),K=require('./kick-attack.js'),H=require('./attack-inertia.js'),T=require('./torso.js'),Aim=require('./attack-aim.js'),Support=require('./support.js');
const attack=process.argv[2]||'sweepKick',snapshots=path.resolve('Saved/BodyflipLab/SweepTurn'),folder=attack==='sweepKick'?snapshots:path.join(snapshots,attack);fs.mkdirSync(folder,{recursive:true});
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),buffer=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),meta=read('data/vanilla.json').clips.find(c=>c.name===attack),clip=C.decode(meta,buffer(meta.file),names,parents),args={clip,names,parents,reference,directArmed:true};
function oldModule(name,dependencies={}){const module={exports:{}};vm.runInNewContext(fs.readFileSync(path.join(snapshots,'before-'+name),'utf8'),{module,require:n=>dependencies[n]||require(n)});return module.exports;}
const oldAir=oldModule('airborne-motion.js'),oldKick=oldModule('kick-attack.js',{'./airborne-motion.js':oldAir}),before=oldKick.preview(args),after=K.preview(args),track=after.track;
const rig=H.model(names,parents,reference),com=p=>Aim.center(p,rig),origin=com(reference),center=p=>({...p,points:p.points.map(x=>R.add(x,R.sub(origin,com(p))))});
const target=[.8322482181993547,2.450370365100572,-.9468223761954488],aim=Aim.create({clip,names,parents,reference,track:{...after.response,start:0,end:track.end,returnEnd:track.stop,hitTime:after.hitTime,armedTime:track.armedTime},sampleHit:t=>after.response.sample(t)});
const rows=['Recorded','Before','Fixed','Fixed + aim 80%'],frames=[];
const frameCount=Math.ceil((track.stop-track.lead)*meta.fps+track.sourceStart)+1;
for(let f=0;f<frameCount;f++){
 const time=track.lead+(f-track.sourceStart)/30;
 const raw=center(f<meta.frames?track.at(f):track.sample(time)),old=before.response.sample(Math.max(0,time)),fixed=after.response.sample(Math.max(0,time)),aimed=aim.apply(fixed,Math.max(0,time),target,.8,true);
 frames.push({frame:f,time,poses:[raw,center(old),center(fixed),center(aimed)]});
}
fs.writeFileSync(path.join(folder,'poses.json'),JSON.stringify({names,parents,origin,target,rows,frames}));
const ctx=vm.createContext({...R,norm:R.length,normalize:R.unit,parents,names,reference,nameToIndex:new Map(names.map((n,i)=>[n,i])),swordMesh:null,posAt:(p,j)=>p.points[j],axisAt:(p,j,k)=>p.axes[j][k],BodyflipTorso:T,BodyflipSupport:Support});
vm.runInContext(fs.readFileSync(new URL('renderer.js',import.meta.url),'utf8')+'\nconst meshRenderer=Object.create(WebGLMotionRenderer.prototype);meshRenderer.torsoColliders=BodyflipTorso.create(names,parents,reference);function geometry(pose){const mesh=new LabVertexStream(50000);meshRenderer.addBody(mesh,{...pose,bicolor:true,hideSword:true});return mesh.view();}',ctx);
const index=[],file=fs.openSync(path.join(folder,'meshes.bin'),'w');let offset=0;
for(const frame of frames)for(let row=0;row<rows.length;row++){
 ctx.pose=frame.poses[row];const data=vm.runInContext('geometry(pose)',ctx),bytes=Buffer.from(data.buffer,data.byteOffset,data.byteLength);fs.writeSync(file,bytes);
 index.push({frame:frame.frame,row,offset,count:data.length});offset+=bytes.length;
}
fs.closeSync(file);fs.writeFileSync(path.join(folder,'mesh-index.json'),JSON.stringify({attack,sourceFrames:meta.frames,frameCount:frames.length,origin,rows,index}));console.log({frames:frames.length,stages:rows,meshMB:offset/1e6});
