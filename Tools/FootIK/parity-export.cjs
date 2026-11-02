'use strict';
// Independent Node oracle for the native FootIK runtime. Sequential, offline,
// no new policy inference. Generated large files belong under Saved only.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
try{const os=require('node:os');os.setPriority(0,process.env.FOOTIK_DIAG_NORMAL_PRIORITY?os.constants.priority.PRIORITY_NORMAL:os.constants.priority.PRIORITY_BELOW_NORMAL);}catch{}
const {root,cases}=require('./parity-cases.cjs');
const K=require('../../Labs/FootIKLab/footik.js'),F=require('../../Labs/FootIKLab/surface.js'),C=require('../../Labs/FootIKLab/surface-coupling.js');
const H=require('../../Labs/FootIKLab/handoff.js');
const parents=require('../../Labs/FootIKLab/data/rig.json').parents;
const sourceFiles=['footik.js','handoff.js','surface.js','surface-coupling.js','recovery.js','support.js','terrain.js','slide-joints.js','slide-entry.js','slide-arms.js'];
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
function canonicalFrame(frame){
 const out={pose:{points:frame.pose.points,q:frame.pose.q},root:frame.root};
 for(const key of ['feet','surface','slide','pelvisOffset','pelvisTransfer','influence','nn'])if(frame[key]!==undefined)out[key]=frame[key];
 return out;
}
async function oracle(input){
 const run=K.decode(input.source,parents);
 if(input.handoff){const requests=[],model=await H.prepare(run,input.settings,async request=>{requests.push(request);if(!input.handoffReply)throw Error('Missing recorded NN handoff reply');return input.handoffReply;});return {model,requests};}
 if(input.policySteps){
  const requests=[],session=C.createSession(run,input.settings,async(request,i)=>{
   const reply=input.policySteps[i];if(!reply)throw Error(`Recorded policy replies exhausted at ${i}`);requests.push(request);return reply;
  });
  try{await session.extend(input.endTime??5);return {model:session.model,requests};}finally{session.close();}
 }
 return {model:input.settings.terrain==='incline'?F.prepare(run,input.settings):K.prepare(run,input.settings),requests:[]};
}
async function main(){
 if(process.versions.v8!=='13.6.233.17-node.51')throw Error('Reference export requires pinned Node 24.19.0 / V8 13.6.233.17-node.51; got '+process.version+' / '+process.versions.v8);
 const args=process.argv.slice(2),out=path.resolve(root,args.find(a=>a.startsWith('--out='))?.slice(6)||'Saved/Diagnostics/FootIKPort20261030'),filter=args.find(a=>a.startsWith('--case='))?.slice(7);
 fs.mkdirSync(out,{recursive:true});
 const sources=Object.fromEntries(sourceFiles.map(n=>[n,hash(path.join(root,'Labs/FootIKLab',n))]));
 const manifest={schema:'footik-native-parity-v1',referenceRuntime:{node:process.version,v8:process.versions.v8},sourceHashes:sources,positionToleranceM:1e-8,quaternionTolerance:1e-10,cases:[]};
 for(const item of cases().filter(c=>!filter||new RegExp(filter).test(c.name))){
  const begin=performance.now(),input={...item.input,parents};
  const {model,requests}=await oracle(input),expected={frames:model.frames.map(canonicalFrame),windows:model.coupling?.windows||[],requests,events:model.events||[]};
  const inputFile=`${item.name}.input.json`,expectedFile=`${item.name}.expected.json`;
  fs.writeFileSync(path.join(out,inputFile),JSON.stringify(input));fs.writeFileSync(path.join(out,expectedFile),JSON.stringify(expected));
  const report={name:item.name,tags:item.tags,input:inputFile,expected:expectedFile,dependency:item.dependency,dependencyHash:hash(path.join(root,item.dependency)),frames:expected.frames.length,policySteps:requests.length,slideFrames:model.frames.filter(f=>f.slide).length,oracleMs:performance.now()-begin};
  manifest.cases.push(report);console.log(JSON.stringify(report));
 }
 if(!manifest.cases.length)throw Error('No parity cases matched');
 for(const name of sourceFiles)if(hash(path.join(root,'Labs/FootIKLab',name))!==sources[name])throw Error(`Source changed during oracle export: ${name}; repeat export after edits settle`);
 fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(manifest,null,2));
 console.log(JSON.stringify({passed:true,cases:manifest.cases.length,frames:manifest.cases.reduce((n,c)=>n+c.frames,0),directory:out}));
}
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1;});
module.exports={canonicalFrame,oracle};
