import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./torso.js'),A=require('./jump-attack.js'),G=require('./space-gym.js');
globalThis.Recovery=R;
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),m=read('data/manifest.json'),idle=C.poseFromShared(m),specs=T.create(m.names,m.parents,idle),checks=[];
const check=(name,value)=>{assert(value,name);checks.push(name);},distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
check('One separate collider for each spine',specs.length===5&&specs.every((s,i)=>s.name==='spine_0'+(i+1)));
const upper=A.bones(m.names,m.parents);check('Attack starts at spine_01 and excludes pelvis',upper[0]===m.names.indexOf('spine_01')&&!upper.includes(m.names.indexOf('pelvis')));
for(const spec of specs){
 const local=R.localize(idle.points,idle.q,m.parents);local.q[spec.bone]=R.qm(local.q[spec.bone],R.qexp([.3,0,0]));const pose=R.fk(local,m.parents),a=T.world(idle,spec),b=T.world(pose,spec);
 check(spec.name+' visible box follows its own axial rotation',angle(a.rotation,b.rotation)>.29);
 check(spec.name+' retains exact rigid dimensions',JSON.stringify(a.dims)===JSON.stringify(b.dims));
 check(spec.name+' center follows its bone-local offset',distance(b.center,R.add(pose.points[spec.bone],R.rotate(pose.q[spec.bone],spec.offset)))<1e-12);
}
const {createPhysics}=await import('./physics.mjs'),physics=await createPhysics(m,idle);
try{
 const actual=physics.torsoGeometry();let maxDimensionError=0,maxOffsetError=0,maxRotationError=0;
 for(let i=0;i<specs.length;i++){const s=specs[i],a=actual[i];check(s.name+' is an actual Jolt box',a.box);maxDimensionError=Math.max(maxDimensionError,distance(s.dims,a.dims));maxOffsetError=Math.max(maxOffsetError,distance(s.offset,a.offset));maxRotationError=Math.max(maxRotationError,angle(s.rotation,a.rotation));}
 check('Rendered and Jolt dimensions match',maxDimensionError<1e-7);check('Rendered and Jolt local offsets match',maxOffsetError<1e-7);check('Rendered and Jolt local orientations match',maxRotationError<1e-7);
 const meta=read('data/vanilla.json').clips.find(c=>c.name==='slashLD'),bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),clip=C.decode(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),m.names,m.parents);
 const base=t=>({pose:idle,root:idle.points[0],phase:'SPACE'}),segment=G.action({time:0},base),attack=A.create({attack:'slashLD'},segment,new Map([['slashLD',clip]]),m.names,m.parents,{...C.defaults,pelvisAttackCompensation:0});
 const sample=attack.sample(attack.start+attack.duration).pose,target=A.attackAt(clip,meta.phases.armed,m.names,m.parents),local=R.localize(sample.points,sample.q,m.parents),spine=specs[0].bone;
 check('spine_01 reaches the authored attack rotation',angle(local.q[spine],target.q[spine])<1e-7);
 check('spine_01 attack is visibly moving',angle(idle.q[spine],sample.q[spine])>.01);
 check('Attack keeps pelvis fixed',distance(sample.points[1],idle.points[1])<1e-12&&angle(sample.q[1],idle.q[1])<1e-12);
 physics.configure({dynamic:true,kinematic:true,surfaces:[],zeroGravity:true});physics.reset(idle);physics.step(sample,1/60);
 check('Kinematic body uses the same constrained attack target',physics.read().points.every((p,i)=>distance(p,physics.target(sample).points[i])<1e-10));
 physics.configure({dynamic:true,kinematic:false,surfaces:[],zeroGravity:true});physics.reset(idle);for(let i=0;i<120;i++)physics.step(attack.sample(i/240).pose,1/240);
 const diagnostic=physics.diagnostics();check('Simulated torso keeps the five constrained bodies finite',diagnostic.finite&&diagnostic.bodies===25&&diagnostic.joints===24&&diagnostic.anchorError<.02);
 const receipt={passed:checks.length,maxDimensionError,maxOffsetError,maxRotationError,simAnchorError:diagnostic.anchorError,checks};fs.writeFileSync(new URL('torso-verification.json',import.meta.url),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
}finally{physics.dispose();}
