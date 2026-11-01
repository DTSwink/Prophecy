// Exact FinalNoAim manifest launch, baked offline in the Bodyflip projectile world.
import fs from 'node:fs';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),S=require('./support.js');globalThis.Recovery=R;
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),pkg=read('data/throws.json'),manifest=read('data/manifest.json'),reference=C.poseFromShared(manifest),away={...reference,points:reference.points.map(p=>R.add(p,[100,0,100]))};T.load(pkg);
const {createPhysics}=await import('./physics.mjs'),sim=await createPhysics(manifest,reference),clips={};
try{for(const id of ['big-throw','small-throw']){
 const m=T.model(id,1),release=m.releaseFrame/60,scale=m.scale,launch={...m.launch,kind:m.kind,scale,comOffset:m.seed.comOffset,mass:pkg.assets[m.kind].mass,aero:m.controls.aero,releaseTime:release,id};
 sim.configure({dynamic:true,kinematic:true,zeroGravity:false,surfaces:[S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-100,100,-100,100],.5)]});sim.reset(away);sim.setProjectiles(pkg.assets,[launch]);
 const fps=120,frames=[];for(let i=0;i<=Math.ceil((m.clip.duration-release)*fps);i++){const state=sim.projectilesAt(release+i/fps,()=>away)[0];frames.push({p:state.p,q:state.q,v:state.v,omega:state.omega,phase:'released'});}
 clips[id]={kind:m.kind,scale,release,fps,frames,launch};
}}finally{sim.dispose();}
const result={schema:'bodyflip-throw-reference-v1',sourceHash:pkg.sourceHash,approved:'FinalNoAim',scene:{target:pkg.settings.target,radius:pkg.settings.radius,floorY:0},clips};fs.writeFileSync(new URL('data/throw-reference.json',import.meta.url),JSON.stringify(result));console.log({passed:true,clips:Object.keys(clips)});
