import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('./flight.js'),C=require('./core.js'),I=require('./idle.js'),R=require('./recovery.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),m=read('data/manifest.json'),b=fs.readFileSync(new URL('data/idle.bin',import.meta.url));
const idle=I.create(read('data/idle.json'),b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),m),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
let landing;const checks=[],check=(name,value)=>{assert(value,name);checks.push(name);};
try{F.sequence(idle.motion(),jumps,C.sanitize({mode:'idle',ramps:false}),m.parents,undefined,data=>{landing=data;throw Error('capture');});}catch(e){if(e.message!=='capture')throw e;}
const request={gait:'walk',drawn:true,names:m.names,frames:31,roots:landing.roots.slice(0,40),seeds:landing.seeds.map(p=>({points:p.points,axes:p.axes})),verifyReference:true};
const post=async q=>{const start=performance.now(),r=await fetch('http://127.0.0.1:8876/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(q)}),result=await r.json();if(!r.ok)throw Error(result.error);return {...result,wallMs:performance.now()-start};};
const original=await post(request),indices=Object.fromEntries(m.names.map((name,i)=>[name,i]));
check('First output preserves every landing point exactly',JSON.stringify(original.poses[0].points)===JSON.stringify(request.seeds[1].points.slice(1)));
check('First output preserves every landing orientation exactly',JSON.stringify(original.poses[0].axes)===JSON.stringify(request.seeds[1].axes.slice(1)));
check('Compiled step agrees with original lower policy and eager upper throughout recovery',original.referenceError<2e-6&&original.inferences===30);
const maxDiff=(a,b)=>Math.max(...a.flat(Infinity).map((v,i)=>Math.abs(v-b.flat(Infinity)[i])));
for(const history of [0,1]){
 const seed=request.seeds[history],root=request.roots[history];
 const local=p=>R.sub(p,root),basis=p=>[p[0],-p[2],p[1]];
 check('Lower history '+history+' contains actual pelvis and both ankle positions',[[0,'pelvis'],[9,'foot_l'],[25,'foot_r']].every(([offset,name])=>maxDiff(original.seedLower[history].slice(offset,offset+3),basis(local(seed.points[indices[name]])))<1e-6));
 check('Upper history '+history+' contains actual wrist positions',[[60,'hand_l'],[75,'hand_r']].every(([offset,name])=>maxDiff(original.seedUpper[history].slice(offset,offset+3),local(seed.points[indices[name]]))<1e-6));
}
const changed=structuredClone(request);changed.verifyReference=false;changed.seeds[1].points[indices.foot_l][0]+=.02;
const foot=await post(changed);
check('Changing landing foot changes lower recurrent prediction',maxDiff(original.poses[1].points.slice(17),foot.poses[1].points.slice(17))>1e-4);
const history=structuredClone(request);history.verifyReference=false;history.seeds[0].points[indices.hand_l][0]+=.02;
const hand=await post(history);
check('Previous pose supplies motion history, not a duplicated current pose',maxDiff(original.poses[1].points.slice(0,17),hand.poses[1].points.slice(0,17))>1e-4&&maxDiff(original.poses[0].points,hand.poses[0].points)===0);
const cached=await post(request);
check('Repeated preparation uses disk cache and identical output',cached.cache==='landing-seed'&&maxDiff(original.poses.at(-1).points,cached.poses.at(-1).points)===0);
check('Capsule root is returned unchanged',maxDiff(original.roots,request.roots.slice(1,32))<1e-7);
fs.writeFileSync(new URL('landing-verification.json',import.meta.url),JSON.stringify({passed:checks.length,checks,referenceError:original.referenceError,inferenceSeconds:foot.seconds,cachedMs:cached.wallMs,visualVerified:false},null,2)+'\n');
console.log(JSON.stringify({passed:checks.length,referenceError:original.referenceError,inferenceSeconds:foot.seconds,cachedMs:cached.wallMs}));
