'use strict';
// Test-only facade for exercising the actual packaged synchronous protocol.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
module.exports.create=options=>{
 global.__footikNN=()=>{throw Error('Unexpected NN call in live host protocol proof');};
 vm.runInThisContext(fs.readFileSync(path.resolve(__dirname,'../../Content/FootIKLab/Runtime.js'),'utf8'));
 const native=global.FootIKNative.command,command=value=>JSON.parse(native(JSON.stringify(value))),epoch='host-proof';let initialized=false;
 const status=()=>command({op:'status'});
 return {
  plan(update={}){const currentTick=update.acceptedFrames?.at(-1)?.tick??(initialized?Math.max(0,status().through):(options.initialHistory?.currentTick??options.sourceStartTick??0));const result=command({...options,...update,op:'liveEvaluate',epoch,currentTick});initialized=true;return result;},
  accept(acceptedFrames){return command({op:'liveCommit',acceptedFrames});},
  commit(tick){command({op:'liveCommit',through:tick});return command({op:'liveFrames',start:tick,count:1})[0];},
  frame(tick){return command({op:'liveFrames',start:tick,count:1})[0];},
  get status(){return status();},
  cancel(){command({op:'close'});}
 };
};
