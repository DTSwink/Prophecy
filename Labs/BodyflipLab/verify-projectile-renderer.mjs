// Compare the uploaded vertex stream with the original renderer, including
// normals/materials, multiple projectiles, scale changes and asset replacement.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js');
const source=fs.readFileSync(new URL('renderer.js',import.meta.url),'utf8');
const assets=JSON.parse(fs.readFileSync(new URL('data/throws.json',import.meta.url),'utf8')).assets;
const ctx=vm.createContext({Recovery:R,normalize:R.unit,sub:R.sub,add:R.add,mul:R.mul,cross:R.cross});
vm.runInContext(source+';globalThis.make=()=>Object.create(WebGLMotionRenderer.prototype);globalThis.stream=()=>new LabVertexStream(32);',ctx);
const renderer=ctx.make();renderer.throwAssets=assets;
const mesh=ctx.stream();
function reference(items){
 const out=ctx.stream();
 for(const item of items){const a=assets[item.kind];if(!a)continue;
  const local=a.vertices.map(p=>p.map((v,i)=>v*item.scale[i])),axes=R.toAxes(item.q);
  const turn=p=>R.add(R.add(R.mul(axes[0],p[0]),R.mul(axes[1],p[1])),R.mul(axes[2],p[2]));
  const world=local.map(p=>R.add(item.p,turn(p)));
  for(let t=0;t<a.triangles.length;t+=3){const ids=a.triangles.slice(t,t+3),[p,b,c]=ids.map(i=>local[i]);
   const normal=turn(R.unit(R.cross(R.sub(b,p),R.sub(c,p))));
   for(const i of ids)out.push(...world[i],...normal,...(a.colors[i]||[.7,.7,.7]));
  }
 }return out.view();
}
let cases=0,vertices=0;
const near=(a,b)=>{assert.equal(a.length,b.length);for(let i=0;i<a.length;i++)assert.equal(a[i],b[i],'uploaded float '+i);};
const item=(kind,scale,p,q)=>({kind,scale,p,q});
const spear=item('spear',[1,1,1],[0,0,0],[0,0,0,1]);
const samples=[[],[spear]];
for(const scale of [[1,1,1],[.3,.7,1.4],[-1,1,1]]){
 samples.push([item('spear',scale,[2,-.75,1.3],R.qexp([.6,-1.2,.3]))]);
 samples.push([item('bomb',scale,[-3,2,1],R.qexp([2,.1,-.9])),item('spear',scale,[.8,1,0],R.qexp([-1,.4,2]))]);
}
for(const items of samples){mesh.length=0;renderer.addProjectiles(mesh,items);near(mesh.view(),reference(items));cases++;vertices+=mesh.length/9;}
const key='spear:1,1,1',buffers=renderer.throwMeshCache.get(key);
mesh.length=0;renderer.addProjectiles(mesh,[spear]);assert.equal(renderer.throwMeshCache.get(key),buffers,'repeat frames reuse cached buffers');
assets.spear={...assets.spear,colors:[]};mesh.length=0;renderer.addProjectiles(mesh,[spear]);near(mesh.view(),reference([spear]));cases++;
assert.notEqual(renderer.throwMeshCache.get(key),buffers,'replacement assets invalidate cached materials');
console.log(JSON.stringify({passed:true,cases,comparedVertices:vertices,uploadedFloat32Values:'exact',buffersReused:true}));
