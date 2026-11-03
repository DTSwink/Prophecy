'use strict';
(function(root){
const clone=value=>JSON.parse(JSON.stringify(value));
const C=typeof module!=='undefined'?require('./core.js'):root.BodyflipCore;
const modes=['jump','walk','idle','spaceGym','footIK'];
const terrainMode=typeof module!=='undefined'?require('./terrain-mode.js'):root.BodyflipTerrainMode;
const timelineKeys=['jumpEvents','runSeconds','jumpEarly','runPhase','startYaw','trimIn','trimOut','trimLoop','playbackSpeed','loop','platforms','surfaceIK','footIKSettings','airFlip','flipSpeed','twistSpeed','flipAngle','twistAngle'];
const timeline=settings=>Object.fromEntries(timelineKeys.map(key=>[key,settings[key]??C.defaults[key]]));
function snapshot(state){
 const next=clone({schema:'bodyflip-lab-v1',settings:state.settings||{},camera:state.camera||{},playback:state.playback||{},modePlaybacks:state.modePlaybacks||{}});
 const mode=C.sanitize(next.settings).mode;
 next.modePlaybacks[mode]={settings:timeline(next.settings),playback:clone(next.playback)};
 return next;
}
function switchMode(state,mode){
 if(!modes.includes(mode))throw Error('Mode unavailable');
 const next=snapshot(state),saved=next.modePlaybacks[mode]||(mode==='footIK'?{settings:terrainMode.preset(),playback:{time:0,attackTime:-1,playing:false}}:null)||{settings:{...timeline(C.defaults),jumpEvents:[]},playback:{time:0,attackTime:-1,flip:0,twist:0,playing:false,hit:false,bestMiss:null}};
 for(const key of timelineKeys)delete next.settings[key];
 next.settings={...next.settings,...timeline(C.defaults),...saved.settings,mode};next.playback=clone(saved.playback);
 return snapshot(next);
}
function open(state){
 const library=state.scenes;
 if(library?.version===1&&Array.isArray(library.items)&&library.items.length&&library.items.some(s=>s.id===library.active))return clone(library);
 return {version:1,active:'original',items:[{id:'original',name:'Inclines',state:snapshot(state)}]};
}
function capture(library,state){const next=clone(library);next.items.find(s=>s.id===next.active).state=snapshot(state);return next;}
function pack(library){const current=library.items.find(s=>s.id===library.active);if(!current)throw Error('Scene unavailable');return {...snapshot(current.state),scenes:clone(library)};}
function select(library,id){if(!library.items.some(s=>s.id===id))throw Error('Scene unavailable');return {...clone(library),active:id};}
function rename(library,name){const next=clone(library),clean=String(name).trim().slice(0,64);if(!clean)throw Error('Enter a scene name');next.items.find(s=>s.id===next.active).name=clean;return next;}
function copy(library,name,id){if(library.items.some(s=>s.id===id))throw Error('Scene already exists');const next=clone(library),state=snapshot(next.items.find(s=>s.id===next.active).state);state.playback.playing=false;for(const saved of Object.values(state.modePlaybacks))saved.playback.playing=false;next.items.push({id,name:'',state});next.active=id;return rename(next,name);}
function create(library,name,id,state){if(library.items.some(s=>s.id===id))throw Error('Scene already exists');const next=clone(library);next.items.push({id,name:'',state:snapshot(state)});next.active=id;return rename(next,name);}
const api={open,capture,pack,select,rename,copy,create,snapshot,switchMode};if(typeof module!=='undefined')module.exports=api;else root.BodyflipScenes=api;
})(typeof window!=='undefined'?window:globalThis);
