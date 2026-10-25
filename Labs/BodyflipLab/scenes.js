'use strict';
(function(root){
const clone=value=>JSON.parse(JSON.stringify(value));
const snapshot=state=>clone({schema:'bodyflip-lab-v1',settings:state.settings||{},camera:state.camera||{},playback:state.playback||{}});
function open(state){
 const library=state.scenes;
 if(library?.version===1&&Array.isArray(library.items)&&library.items.length&&library.items.some(s=>s.id===library.active))return clone(library);
 return {version:1,active:'original',items:[{id:'original',name:'Inclines',state:snapshot(state)}]};
}
function capture(library,state){const next=clone(library);next.items.find(s=>s.id===next.active).state=snapshot(state);return next;}
function pack(library){const current=library.items.find(s=>s.id===library.active);if(!current)throw Error('Scene unavailable');return {...snapshot(current.state),scenes:clone(library)};}
function select(library,id){if(!library.items.some(s=>s.id===id))throw Error('Scene unavailable');return {...clone(library),active:id};}
function rename(library,name){const next=clone(library),clean=String(name).trim().slice(0,64);if(!clean)throw Error('Enter a scene name');next.items.find(s=>s.id===next.active).name=clean;return next;}
function copy(library,name,id){if(library.items.some(s=>s.id===id))throw Error('Scene already exists');const next=clone(library),state=snapshot(next.items.find(s=>s.id===next.active).state);state.playback.playing=false;next.items.push({id,name:'',state});next.active=id;return rename(next,name);}
const api={open,capture,pack,select,rename,copy};if(typeof module!=='undefined')module.exports=api;else root.BodyflipScenes=api;
})(typeof window!=='undefined'?window:globalThis);
