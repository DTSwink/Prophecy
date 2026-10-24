import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),jumps=read('data/jumps.json').clips.map(F.decodeJump),checks=[];
// Measure the actual rendered foot/toe boxes, independently of support clearance.
const context=vm.createContext({...R,normalize:R.unit,norm:R.length,posAt:(p,i)=>p.points[i],axisAt:(p,i,a)=>p.axes[i][a]});
vm.runInContext(fs.readFileSync(new URL('renderer.js',import.meta.url),'utf8')+'\nglobalThis.footBoxes=WebGLMotionRenderer.prototype.footBoxes;',context);
const bottom=b=>b.center[1]-(Math.abs(b.forward[1])*b.dims[0]+Math.abs(b.side[1])*b.dims[1]+Math.abs(b.up[1])*b.dims[2])/2;
const sole=p=>Math.min(...['l','r'].flatMap(s=>Object.values(context.footBoxes(p,{ankle:m.names.indexOf('foot_'+s),toe:m.names.indexOf('ball_'+s)})).map(bottom)));
const results=[];
for(const file of ['run-default.json','run-default-drawn.json']){
 const run=F.decodeNN(read('data/'+file)),f=F.create(run,jumps,{...C.defaults,supportSpeed:300},m.parents,C.poseFromShared(m));
 let stance=0,airborne=0,maxStanceGap=-Infinity,minSole=Infinity;
 for(let t=0;t<=f.supportStart;t+=1/120){
  const raw=F.at(run,t,m.parents),shown=f.sample(t).pose,rawBottom=sole(raw),shownBottom=sole(shown);
  assert(shown.points.every((p,i)=>Math.abs(p[1]-raw.points[i][1])<1e-10),'NN vertical pose must be unchanged');
  assert(Math.abs(shownBottom-rawBottom)<1e-10,'Renderer sole must not get an extra vertical offset');
  if(rawBottom<.005){stance++;maxStanceGap=Math.max(maxStanceGap,shownBottom);}
  if(rawBottom>.02){airborne++;assert(shownBottom>.02,'Preserve running flight phase');}
  minSole=Math.min(minSole,shownBottom);
 }
 assert(stance>10&&airborne>2&&maxStanceGap<.005,'Grounded stance and normal airborne phases');
 checks.push(file+' exact source heights',file+' rendered stance reaches ground',file+' gait airborne phases retained');
 results.push({file,stanceSamples:stance,airborneSamples:airborne,maxStanceGapCm:maxStanceGap*100,minSoleCm:minSole*100,jumpStart:f.jumpStart});
}
const report={passed:true,checks,results};fs.writeFileSync(new URL('ground-verification.json',import.meta.url),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
