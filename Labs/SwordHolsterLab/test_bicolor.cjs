const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),R=require('./recovery.js');
const ctx=vm.createContext({...R,norm:R.length,normalize:R.unit});
vm.runInContext(fs.readFileSync(__dirname+'/renderer.js','utf8')+'\nglobalThis.TestRenderer=WebGLMotionRenderer;',ctx);
const renderer=Object.create(ctx.TestRenderer.prototype),base={points:[[0,0,0],[0,1,0]],axes:[[[1,0,0],[0,0,1],[0,1,0]]]};
const first=[];renderer.limbLongAxisHalf(first,base,0,1,.058,1);assert.equal(first.length,11*10*6*9);
for(const radians of [0,.5,Math.PI/2,Math.PI]){
 const q=R.qexp([0,radians,0]),data={points:base.points.map(p=>R.rotate(q,p)),axes:base.axes.map(a=>a.map(v=>R.rotate(q,v)))},before=JSON.stringify(data),mesh=[];
 renderer.limbLongAxisHalf(mesh,data,0,1,.058,1);
 const outward=renderer.limbTintAxis(data,0,1);
 for(let i=0;i<mesh.length;i+=9){
  assert.deepEqual(mesh.slice(i+6,i+9),[.08,.86,.94]);
  assert(R.dot(mesh.slice(i+3,i+6),outward)>=-1e-10,'cyan remains on bone-relative half');
  assert(R.length(R.sub(mesh.slice(i,i+3),R.rotate(q,first.slice(i,i+3))))<1e-10,'marker follows axial roll');
 }
 assert.equal(JSON.stringify(data),before,'rendering cannot mutate pose');
}
console.log('PASS: reused cyan half-shell follows bone rotation, preserves tint convention and does not mutate poses.');
