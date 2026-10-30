// Actual collider geometry, rendered offline without opening a browser.
import fs from 'node:fs';import vm from 'node:vm';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),T=require('./torso.js');
const folder='Saved/BodyflipLab/HandJump',input=JSON.parse(fs.readFileSync(folder+'/'+(process.argv[2]||'floor-poses.json'))),m=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),{names,parents}=m,reference=C.poseFromShared(m);
const ctx=vm.createContext({...R,norm:R.length,normalize:R.unit,names,parents,reference,BodyflipTorso:T,BodyflipSupport:S,nameToIndex:new Map(names.map((n,i)=>[n,i])),swordMesh:null,posAt:(p,j)=>p.points[j],axisAt:(p,j,k)=>p.axes[j][k]});
vm.runInContext(fs.readFileSync(new URL('renderer.js',import.meta.url),'utf8')+'\nconst renderer=Object.create(WebGLMotionRenderer.prototype);renderer.torsoColliders=BodyflipTorso.create(names,parents,reference);function geometry(pose,surface){const mesh=new LabVertexStream(50000);renderer.addBody(mesh,{...pose,bicolor:true,hideSword:true});return mesh.view();}',ctx);
const sf=input.surface;ctx.surface=S.rectangle('audit',sf.origin,sf.u,sf.v,sf.bounds,.12);
const index=[],file=fs.openSync(folder+'/meshes.bin','w');let offset=0;
for(let i=0;i<input.frames.length;i++){
 if(process.argv.includes('--contact-only')&&(input.frames[i].time<input.timing.contact-5/60||input.frames[i].time>input.timing.contact+6/60))continue;
 const frame=input.frames[i];ctx.pose=frame.pose;const data=vm.runInContext('geometry(pose,surface)',ctx),bytes=Buffer.from(data.buffer,data.byteOffset,data.byteLength);fs.writeSync(file,bytes);index.push({frame:i,time:frame.time,phase:frame.phase,root:frame.root,offset,count:data.length});offset+=bytes.length;
}
fs.closeSync(file);fs.writeFileSync(folder+'/mesh-index.json',JSON.stringify({index,timing:input.timing,surface:input.surface}));console.log({frames:index.length,meshMB:offset/1e6});
