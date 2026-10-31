// Compare the packaged host against the same surface-aware projection used by
// app.js/physics.target, not merely against a second engine running the adapter.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const ctx=vm.createContext({__bodyflipAttack:id=>fs.readFileSync('Content/BodyflipLab/Attacks/'+id+'.json','utf8')});
vm.runInContext(fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8'),ctx);
ctx.json=fs.readFileSync('Content/BodyflipLab/Assets.json','utf8');
const result=vm.runInContext(`(()=>{
 const load=n=>BodyflipRequire('BodyflipLab/'+n+'.js'),C=load('core'),F=load('flight'),R=load('recovery'),T=load('target-rig'),I=load('idle'),d=JSON.parse(json),B=BodyflipNative.raw;
 const axes=p=>({...p,axes:p.q.map(R.toAxes)});d.reference=axes(d.reference);d.jumps.forEach(c=>c.poses=c.poses.map(axes));
 const idle=I.create(d.idleMeta,new Float32Array(d.idleValues).buffer,d),rig=T.create(d.names,d.parents,d.reference),originalSequence=F.sequence;
 // Supply an otherwise legal pose eight cm into the surface at the host
 // boundary, as an attack/pose modification can do after flight evaluation.
 const lower=frame=>({...frame,pose:{...frame.pose,points:frame.pose.points.map((p,i)=>i?R.add(p,[0,-.08,0]):p)}});
 F.sequence=(...args)=>{const seq=originalSequence(...args),sample=seq.sample;return {...seq,sample:t=>lower(sample(t))};};
 B({op:'assets',value:JSON.parse(json)});let maxError=0,clearanceEffect=0,checks=0;
 for(const aim of [false,true])for(const height of [0,.04,.12]){
  const settings=C.sanitize({mode:'idle',attack:'none',aim,trimOut:.1,ramps:false,jumpEvents:[],platforms:[{id:'floor',position:[0,height-.2,0],size:[20,.4,20],rotation:[0,0,0,1]}]});
  const run=idle.motion(settings.runPhase),seq=originalSequence(run,d.jumps,settings,d.parents,d.reference,null,new Map(),{horizon:.1});
  B({op:'start',settings,horizon:.1});
  for(const t of [0,1/60,.1]){const raw=lower(seq.sample(t)).pose,expected=rig.project(raw,seq.surfaces),missing=rig.project(raw),actual=B({op:'sample',time:t}).pose;
   for(let i=0;i<26;i++){maxError=Math.max(maxError,R.length(R.sub(expected.points[i],actual.points[i])));clearanceEffect=Math.max(clearanceEffect,R.length(R.sub(expected.points[i],missing.points[i])));}checks++;
  }
 }
 return {checks,maxError,clearanceEffect};
})()`,ctx);
assert(result.maxError<1e-9,JSON.stringify(result));assert(result.clearanceEffect>.001,'Fixture must exercise actual surface clearance');
fs.writeFileSync('Saved/Diagnostics/BodyflipPort20261030/surface-projection-parity.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
