// Compare all returned fields with only release caching disabled. No editor/world.
import {sourceRuntime} from './source-runtime-test.mjs';
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';import crypto from 'node:crypto';
const profileFile=process.env.BODYFLIP_RELEASE_PROFILE,profileText=profileFile?fs.readFileSync(profileFile,'utf8'):null,profile=profileText?JSON.parse(profileText):null,current=profile?sourceRuntime():null;
const dir='Saved/Diagnostics/BodyflipPort20261030',file='Tools/Bodyflip/runtime-adapter.js',source=fs.readFileSync(file,'utf8'),runtime=current?.runtime||fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8');
const uncached="function releaseAt(track){const at=x=>aimed(x,sequence.sample(x).pose);return track.launchAt(at(track.releaseTime),track.transportVelocity(at),track.transportAngularVelocity(at));}\n";
// Historical adapter copies also predate intentional heading/entry fixes.
// Keep this comparison controlled: identical current code except the cache.
const baseline=source.replace(/function releaseAt\(track\)\{[\s\S]*?\nfunction sample\(/,uncached+'function sample(');assert.notEqual(baseline,source,'uncached reference hook');
const common={mode:'spaceGym',motion:'kinematic',aim:true,aimWeight:1,ramps:false,surfaceIK:false,trimOut:1.4,target:[-1,1,-2],spinLag:.6,attack:'small-throw',jumpEvents:[{id:'a',time:.1,attack:'small-throw',throwCharge:37,flip:150,twist:-60,spinVersion:2,jumpPercent:0}]};
const commands=[],push=(input,warm=false)=>commands.push({input:input.op==='start'&&profile?{...input,rigProfile:profile}:input,warm}),samples=(times,warm=false)=>times.forEach(time=>push({op:'sample',time},warm));
push({op:'start',settings:common,horizon:1.4});samples([0,.1,.4,1]);samples([1.1,1.2,1.3,1.1,1.25,1],true);samples([.5,1.2],true);
push({op:'mutate',time:1.1});samples([1.2],true);push({op:'target',target:[2,1,2]});samples([1,1.1,1.2]);
push({op:'prepare',time:2.4});samples([1.2,2,1.4,2.2]);push({op:'target',target:[-1,1,-2]});samples([1.2,1.3]);
push({op:'start',settings:{...common,aim:false,trimOut:2.4,jumpEvents:[{...common.jumpEvents[0],throwCharge:60}]},horizon:2.4});samples([1.5,1.7,2,2.2,1.7]);
push({op:'start',settings:{...common,aim:false,trimOut:4,jumpEvents:[{...common.jumpEvents[0],throwCharge:10},{...common.jumpEvents[0],id:'b',time:.9,attack:'big-throw'},{...common.jumpEvents[0],id:'c',time:2.1}]},horizon:4});samples([1,1.5,2,2.5,3,3.5,3.8,3,2]);
push({op:'start',settings:{...common,mode:'idle',aim:false,trimOut:.5,jumpEvents:[{...common.jumpEvents[0],throwCharge:10}],platforms:[{id:'floor',position:[0,-.2,0],size:[20,.4,200],rotation:[0,0,0,1]}]},horizon:.5});samples([.3,.4,.5]);push({op:'prepare',time:.9});samples([.7,.8,.4,.8]);
function fakeNN(json){const r=JSON.parse(json),last=r.seeds.at(-1),origin=last.points[0];return JSON.stringify({names:r.names.slice(1),fps:30,duration:(r.frames-1)/30,roots:r.roots.slice(0,r.frames),poses:Array.from({length:r.frames},(_,i)=>({points:last.points.slice(1).map(p=>p.map((v,k)=>v-origin[k]+r.roots[i][k])),axes:last.axes.slice(1)}))});}
function execute(code){
 let counted=code.replace('if(time>=a.releaseTime){const at=','if(time>=a.releaseTime){__releaseBuilds++;const at=');
 if(counted===code)counted=code.replace('if(!launch){const at=','if(!launch){__releaseBuilds++;const at=');
 if(counted===code)counted=code.replace('function releaseAt(track){const at=','function releaseAt(track){__releaseBuilds++;const at=');
 assert.notEqual(counted,code,'release counter hook');
 const context=vm.createContext({Date,performance,__releaseBuilds:0,__bodyflipAttack:id=>fs.readFileSync('Content/BodyflipLab/Attacks/'+id+'.json','utf8'),__bodyflipNN:fakeNN});
 vm.runInContext(runtime,context);vm.runInContext(counted,context);const call=context.BodyflipNative.raw;
 call({op:'assets',value:JSON.parse(fs.readFileSync('Content/BodyflipLab/Assets.json','utf8'))});
 const outputs=[],counts=[],costs=[];for(const {input} of commands){const before=context.__releaseBuilds,t=performance.now();let result;
  if(input.op==='mutate'){result=call({op:'sample',time:input.time});assert(result.releases.length);for(const field of ['p','q','v','omega','axis'])result.releases[0][field][0]+=99;}
  else result=call(structuredClone(input));costs.push(performance.now()-t);counts.push(context.__releaseBuilds-before);outputs.push(JSON.parse(JSON.stringify(result)));
 }
 return {outputs,counts,costs,builds:context.__releaseBuilds};
}
const before=execute(baseline),after=execute(source);let compared=0;for(let i=0;i<commands.length;i++){assert.deepEqual(after.outputs[i],before.outputs[i],'changed output at command '+i+' '+JSON.stringify(commands[i].input));compared++;}
assert(after.builds<before.builds/2,'release cache must remove repeated calculations');
const warm=commands.flatMap((c,i)=>c.warm?[i]:[]),sum=(r,ids)=>ids.reduce((v,i)=>v+r.costs[i],0),invalidations=commands.flatMap((c,i)=>['start','target','prepare'].includes(c.input.op)?[{command:i,op:c.input.op,nextBuild:after.counts.slice(i+1).find(n=>n>0)||0}]:[]);
const hash=s=>crypto.createHash('sha256').update(s).digest('hex'),changedSources=current?Object.entries(current.hashes).filter(([name,h])=>hash(fs.readFileSync('Labs/'+name))!==h).map(([name])=>name):[];if(hash(fs.readFileSync(file))!==hash(source))changedSources.push(file);if(profileFile&&hash(fs.readFileSync(profileFile))!==hash(profileText))changedSources.push(profileFile);
const report={passed:changedSources.length===0,changedSources,profileHash:profileText?hash(profileText):null,sourceModules:current?.hashes,commands:compared,baselineHash:hash(baseline),sourceHash:hash(source),runtimeHash:hash(runtime),baselineBuilds:before.builds,cachedBuilds:after.builds,warmSamples:warm.length,warmBeforeMs:sum(before,warm),warmAfterMs:sum(after,warm),invalidations};
fs.writeFileSync(dir+(profile?'/release-cache-native-profile.json':'/release-cache-parity.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));assert.deepEqual(changedSources,[],'sources changed during probe');
