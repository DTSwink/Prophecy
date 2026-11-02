'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),Module=require('node:module'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),folder=path.join(root,'Saved/Diagnostics/FootIKPort20261030'),packaged=process.argv.includes('--packaged');
global.__footikNN=()=>{throw Error('Unexpected NN call in frame transport proof');};
if(packaged)vm.runInThisContext(fs.readFileSync(path.join(root,'Content/FootIKLab/Runtime.js'),'utf8'));
else{
 const file=path.join(__dirname,'live-stair-planner.cjs'),m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(__dirname);
 // Same synchronous no-policy branch as the native packager, in memory only.
 m._compile(fs.readFileSync(file,'utf8').replaceAll('async function ','function ').replaceAll('await ',''),file);
 global.FootIKRequire=name=>name==='live-stair-planner.cjs'?m.exports:require(path.join(root,name==='live-join.cjs'?'Tools/FootIK':'Labs/FootIKLab',name));
 vm.runInThisContext(fs.readFileSync(path.join(__dirname,'runtime-adapter.js'),'utf8'));
}
const call=text=>JSON.parse(global.FootIKNative.command(text)),command=value=>call(JSON.stringify(value));
let frames=0,queries=0;
for(const name of ['walk-flat','walk-stairs']){
 const input=JSON.parse(fs.readFileSync(path.join(folder,name+'.input.json'))),source=structuredClone(input.source);
 source.poses=source.poses.slice(0,31);source.roots=source.roots.slice(0,31);source.rootYawDegrees=source.rootYawDegrees?.slice(0,31);source.duration=source.totalDuration=1;source.directionMeta={...source.directionMeta,totalDuration:1};
 const result=command({...input,source,op:'liveEvaluate',epoch:name,currentTick:0});assert(result.ready);
 for(const args of [{},{start:-8,count:3},{start:0,count:0},{start:0,count:-1},{start:4,count:12},{start:118,count:500},{start:0,count:500},{start:121,count:3},{start:'invalid',count:2},{start:0,count:'invalid'}]){
  const old=command({op:'liveFrames',...args}),texts=command({op:'liveFrameTexts',...args});assert(texts.every(v=>typeof v==='string'));
  assert.deepEqual(texts.map(JSON.parse),old);assert.equal(JSON.stringify(texts.map(JSON.parse)),JSON.stringify(old));frames+=old.length;queries++;
 }
 // Import an actual in-memory signed zero (JSON.parse preserves it) and check
 // that both output operations follow the existing JSON zero normalization.
 const accepted=command({op:'liveFrames',start:0,count:1})[0];accepted.transportZero=0;
 call(JSON.stringify({op:'liveCommit',acceptedFrames:[{tick:0,frame:accepted}]}).replace('"transportZero":0','"transportZero":-0'));
 const ordinary=command({op:'liveFrames',start:0,count:1}),textual=command({op:'liveFrameTexts',start:0,count:1});
 assert.deepEqual(textual.map(JSON.parse),ordinary);assert.equal(Object.is(ordinary[0].transportZero,-0),false);frames++;
 command({op:'close'});assert.throws(()=>command({op:'liveFrameTexts'}),/No prospective/);assert.throws(()=>command({op:'liveFrames'}),/No prospective/);
}
const report={passed:true,packaged,completeFramesCompared:frames,rangeQueries:queries,signedZeroMatchesExistingJSON:true,disabledRejects:true};
fs.writeFileSync(path.join(folder,packaged?'live-frame-texts-packaged.json':'live-frame-texts-source.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
