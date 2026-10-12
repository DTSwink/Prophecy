/* Playback composition only: both actions reuse the existing holster planner. */
(function(root){
'use strict';
const H=typeof module!=='undefined'?require('./holster.js'):root.Holster;
const actionOptions=(o,sheathe)=>({...o,...o[sheathe?'sheatheBody':'drawBody'],sheathe});
const actionName=model=>model.o.sheathe?'S':'D';
function assemble(first,second,options,reason=''){
 const offset=first.playbackDuration,frames=second?
  [...first.frames.slice(0,-1).map(f=>({...f,sequenceAction:actionName(first)})),...second.frames.map(f=>({...f,tick:f.tick+first.completionTick,sequenceAction:actionName(second)}))]:first.frames.map(f=>({...f,sequenceAction:actionName(first)}));
 return {...first,o:options,sequence:{first,second,offset,reason},frames,
  playbackDuration:offset+(second?.playbackDuration||0),
  completionTick:second?.completionTick!=null?first.completionTick+second.completionTick:null};
}
function waiting(first){
 const action=first.o.sheathe?'sheathing':'drawing',next=first.o.sheathe?'Drawing':'Sheathing';
 if(!first.o[first.o.sheathe?'sheatheReturn':'drawReturn'].enabled)return `Enable ${action} FK return to play both actions after the full return.`;
 if(first.completionTick===null)return `${next} waits for ${action} and its full return. Increase the time budget if needed.`;
 return '';
}
function prepare(data,setup,options){
 if(!options.sequenceMode)return H.prepare(data,setup,options);
 const sheathe=!!options.sheathe,first=H.prepare(data,setup,actionOptions(options,sheathe)),reason=waiting(first);
 const second=reason?null:H.prepare(data,setup,{...actionOptions(options,!sheathe),startTick:0},first.playbackDuration);
 return assemble(first,second,options,reason);
}
function retime(model,options){
 if(!model.sequence||!options.sequenceMode)return model.sequence||options.sequenceMode?prepare(model.data,model.setup,options):H.retime(model,options);
 const sheathe=!!options.sheathe;
 if(model.sequence.first.o.sheathe!==sheathe)return prepare(model.data,model.setup,options);
 const first=H.retime(model.sequence.first,actionOptions(options,sheathe)),reason=waiting(first);
 const nextOptions={...actionOptions(options,!sheathe),startTick:0},previous=model.sequence.second;
 const second=reason?null:previous&&previous.motionOffset===first.playbackDuration?
  H.retime(previous,nextOptions):H.prepare(model.data,model.setup,nextOptions,first.playbackDuration);
 return assemble(first,second,options,reason);
}
function segment(model,t){
 const s=model.sequence;
 return s?(s.second&&t>=s.offset?{model:s.second,offset:s.offset}:{model:s.first,offset:0}):{model,offset:0};
}
function edited(model,sheathe){
 const s=model.sequence,first=s?.first.o.sheathe===sheathe;
 return s?{model:first?s.first:s.second,offset:first?0:s.offset}:{model,offset:0};
}
function sample(model,t){
 const part=segment(model,t),f=H.sample(part.model,t-part.offset);
 return model.sequence?{...f,sequenceAction:actionName(part.model)}:f;
}
function recordedTime(model,t){const part=segment(model,t);return part.offset+H.recordedTime(part.model,t-part.offset);}
function previewTime(model,insertion,sheathe){const part=edited(model,sheathe);return part.model?part.offset+H.previewTime(part.model,insertion):model.playbackDuration;}
function previewBody(model,insertion,targets,t,sheathe){
 const part=segment(model,t);
 if(model.sequence&&part.model.o.sheathe!==sheathe)return {...sample(model,t),previewTime:t};
 const f=H.previewBody(part.model,insertion,targets,t-part.offset);
 return {...f,previewTime:t,...(model.sequence?{sequenceAction:actionName(part.model)}:{})};
}
// Avoid copying source assets with both prepared models through the worker.
function assets(model,data,setup){
 for(const part of model.sequence?[model,model.sequence.first,model.sequence.second]:[model])if(part){
  if(data){part.data=data;part.setup=setup;}else{delete part.data;delete part.setup;}
 }
 return model;
}
const api={prepare,retime,segment,edited,sample,recordedTime,previewTime,previewBody,assets};
if(typeof module!=='undefined')module.exports=api;else root.HolsterPlayback=api;
})(globalThis);
