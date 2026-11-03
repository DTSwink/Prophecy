// Read-only diagnostic captures. Live lab settings and production code are never written.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
const root=process.cwd(),base=path.join(root,'Labs/BodyflipLab'),out=path.join(root,'Saved/Diagnostics/BodyflipOtherReview20261103');fs.mkdirSync(out,{recursive:true});
const require=createRequire(import.meta.url),R=require(base+'/recovery.js'),C=require(base+'/core.js'),T=require(base+'/throw-attack.js'),J=require(base+'/jump-attack.js'),F=require(base+'/flight.js'),G=require(base+'/space-gym.js');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8').replace(/^\uFEFF/,'')),manifest=read(base+'/data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest);
const pose=p=>({points:p.points,q:p.q});
const frames=(end,actual,target)=>Array.from({length:Math.ceil(end*60)+1},(_,i)=>{const time=Math.min(end,i/60);return {time,actual:pose(actual(time)),target:target?pose(target(time)):null};});
T.load(read(base+'/data/throws.json'));
const direct=[];
for(const attack of ['big-throw','small-throw']){
 const event={attack,throwCharge:100},segment={sample:()=>({pose:reference}),airStart:0,jumpStart:0,abortTime:Infinity},settings=C.sanitize({distributePelvisTurn:true});
 const track=T.create(event,segment,null,names,parents,settings,reference),shared=J.create({...event,attack:'slashL'},segment,null,names,parents,settings,reference,{clipOverride:track.clip});
 direct.push({label:`Lab check: ${attack} return`,note:'Orange: current throw pose. Purple: the shared slash-return path that this old test expects. This is a lab algorithm comparison, not Unreal physics.',actualLabel:'Current throw pose',targetLabel:'Old test: shared slash return',names,frames:frames(track.returnEnd+.1,t=>track.sample(t).pose,t=>shared.sample(t).pose),focusTime:track.end,focusBone:'hand_l',noFloor:true});
}
const jumps=['jumps.json','jumps-standing.json'].flatMap(n=>read(base+'/data/'+n).clips).map(F.decodeJump),first={id:'first',time:0,jumpPercent:0,spinVersion:2,flip:-300,twist:1400,instantSpin:true},settings=C.sanitize({spinInertia:1,spinLag:.6,mode:'spaceGym'});
const stopped=G.sequence({names,poses:[reference]},jumps,settings,parents,[first,{...first,id:'stop',time:.4,flip:0,twist:0}],null,reference),held=stopped.sample(.4).pose;
direct.push({label:'Lab check: zero-spin command',note:'Zero flip/twist is requested at 0.4 s. Purple freezes the pose at that command; the old test expects rotation to have stopped by 0.5 s. Not Unreal physics.',actualLabel:'Current spin response',targetLabel:'Pose held at stop command',names,frames:frames(1,t=>stopped.sample(t).pose,t=>t<.4?stopped.sample(t).pose:held),focusTime:.5,focusBone:'pelvis',noFloor:true});
fs.writeFileSync(out+'/direct.json',JSON.stringify(direct));
function runExtract(file,source){
 const url=pathToFileURL(base+'/'+file).href;
 source=source.replaceAll('import.meta.url',JSON.stringify(url)).replace("await import('./physics.mjs')",`await import(${JSON.stringify(pathToFileURL(base+'/physics.mjs').href)})`);
 const dest=out+'/'+file;fs.writeFileSync(dest,source);const run=spawnSync(process.execPath,[dest],{encoding:'utf8',timeout:240000,maxBuffer:1024*1024*4});fs.writeFileSync(dest+'.log',(run.stdout||'')+(run.stderr||''));
 if(run.status!==0)throw Error(file+': '+run.stderr);console.log(file+': captured');
}
const swordSource=fs.readFileSync(base+'/verify-coupled-weapon-return.mjs','utf8');
runExtract('capture-sword.mjs',swordSource.slice(0,swordSource.indexOf(' const results=[];'))+`
 ctx.spec={attack:'slashLU',cut:20,weight:.4};
 await vm.runInContext(\`(async()=>{settings=C.sanitize({...settings,mode:'spaceGym',airFlip:false,spaceFallAnimation:true,attackReturnDistance:spec.weight,attackEndFrames:{[spec.attack]:spec.cut},jumpEvents:[{...settings.jumpEvents[0],enabled:true,attack:spec.attack,flip:0,twist:0}]});await prepareRun({preserveTime:true});})()\`,ctx);
 const result=vm.runInContext(\`(()=>{const tr=flight.segments[0].attack,render=Object.create(WebGLMotionRenderer.prototype),hand=names.indexOf(swordMesh.hand_node||'hand_r');return {names,focusTime:tr.end,focusBone:'hand_r',weapon:{bone:hand,vertices:Array.from({length:swordMesh.vertices.length/3},(_,i)=>render.swordLocalToWorld(Array.from(swordMesh.vertices.slice(i*3,i*3+3)),[0,0,0],[[1,0,0],[0,1,0],[0,0,1]])),faces:Array.from({length:swordMesh.triangles.length/3},(_,i)=>Array.from(swordMesh.triangles.slice(i*3,i*3+3)))},frames:Array.from({length:Math.ceil((tr.returnEnd+.15)*60)+1},(_,i)=>{const time=i/60,p=physics.target(aimTimelinePoseAt(time));return {time,actual:{points:p.points,q:p.q},target:null};})};})()\`,ctx);
 Object.assign(result,{label:'Lab check: trimmed Slash LU return',note:'Current lab motion for the old sword-turn check (cut 20). The check limits accumulated sword rotation; it defines no separate target pose. Overlay is unavailable for this case.',actualLabel:'Current lab pose',noFloor:true});fs.writeFileSync(${JSON.stringify(out+'/sword.json')},JSON.stringify([result]));
 }finally{physics?.dispose();}
`);
const foot=fs.readFileSync(base+'/verify-foot-ik.mjs','utf8');
runExtract('capture-incline.mjs',foot.slice(0,foot.indexOf("for(const gait"))+foot.slice(foot.indexOf('const jumps='),foot.indexOf("check('Landing still seeds"))+`
 const result={label:'Lab check: inclined landing',note:'Current lab jump/landing using a fresh NN continuation. Old check flags a pose discontinuity at landing. It does not define a second full target animation.',actualLabel:'Current lab pose',names,focusTime:landing,focusBone:'foot_r',surface:S.platformRecord(ramp),frames:Array.from({length:Math.ceil((landing+.7)*60)+1},(_,i)=>{const time=i/60,p=sequence.sample(time).pose;return {time,actual:{points:p.points,q:p.q},target:null};})};fs.writeFileSync(${JSON.stringify(out+'/incline.json')},JSON.stringify([result]));
`);
const landing=fs.readFileSync(base+'/verify-landing-continuity.mjs','utf8');
runExtract('capture-landing.mjs',landing.slice(0,landing.indexOf('const generate='))+`
 const generate=async q=>{const response=await fetch('http://127.0.0.1:8876/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(q)});const data=await response.json();if(!response.ok)throw Error(data.error);return data;};
 const seq=await F.prepare(run,jumps,{...settings,trimOut:3.8},parents,reference,generate);
 const result={label:'Lab check: landing continuation',note:'Fresh continuation for the old landing fixture. The failing test rejected outdated cached NN input before producing a motion; this shows the current setup, not a proven reproduced bug.',actualLabel:'Current lab pose',names,focusTime:seq.landings[0]?.time||3.1,focusBone:'thigh_r',frames:Array.from({length:229},(_,i)=>{const time=i/60,p=T.project(seq.sample(time).pose,seq.surfaces);return {time,actual:{points:p.points,q:p.q},target:null};})};fs.writeFileSync(${JSON.stringify(out+'/landing.json')},JSON.stringify([result]));
`);
console.log(out);
