import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),F=require('./flight.js');
// Small event/DOM adapter: checks real editor behavior, not browser layout.
class Element {
 constructor(){this.children=[];this.dataset={};this.style={};this.attrs={};this.classList={toggle:()=>{}};this.clientWidth=1000;this.offsetLeft=100;this.value='';}
 append(e){e.parent=this;this.children.push(e);}
 remove(){this.parent.children=this.parent.children.filter(e=>e!==this);}
 replaceChildren(...list){this.children=[];list.forEach(e=>this.append(e));}
 setAttribute(k,v){this.attrs[k]=v;}
 setPointerCapture(){}
 getBoundingClientRect(){return {left:100,width:1000};}
 closest(){return this.className==='jump-marker'?this:null;}
 contains(e){return this===e||this.children.some(c=>c.contains(e));}
}
const ids=['jumpEditor','jumpHere','jumpRemove','jumpTime','jumpLane','jumpPopover','jumpLabel','jumpStatus','jumpMarkers'],elements=Object.fromEntries(ids.map(id=>[id,new Element()])),listeners={};
const document={getElementById:id=>elements[id],createElement:()=>new Element(),addEventListener:(name,fn)=>listeners[name]=fn,activeElement:null};
let settings=C.sanitize(),time=1.37,edits=0,seeks=[];
const context=vm.createContext({document,setTimeout,clearTimeout,Date});
vm.runInContext(fs.readFileSync(new URL('jump-track.js',import.meta.url),'utf8')+'\nglobalThis.Editor=JumpTrack;',context);
const editor=new context.Editor({get:()=>({settings,events:F.eventsFor(settings),results:[],time,max:12}),edit:events=>{edits++;settings=C.sanitize({...settings,jumpEvents:events});},seek:t=>seeks.push(t)}),checks=[];
const check=(name,condition)=>{assert(condition,name);checks.push(name);};
editor.sync();check('Default strip has no expanded editor',elements.jumpPopover.hidden&&elements.jumpMarkers.children.length===1);
elements.jumpHere.onclick();check('Plus adds at playhead on 60 Hz frame',settings.jumpEvents.length===2&&settings.jumpEvents[1].time===82/60);
check('Adding does not change playhead',time===1.37&&seeks.length===0);
check('New marker opens exact time editor',!elements.jumpPopover.hidden&&elements.jumpTime.value==='1.367');
const id=editor.selected;elements.jumpTime.value='0.4';elements.jumpTime.onchange();
check('Time editing sorts while retaining selection',settings.jumpEvents[0].id===id&&editor.selected===id&&settings.jumpEvents[0].time===.4);
const marker=elements.jumpMarkers.children.find(e=>e.dataset.id===id),lane=elements.jumpLane;
lane.onpointerdown({button:0,target:marker,clientX:200,pointerId:1,preventDefault(){}});
lane.onpointermove({clientX:300});lane.onpointerup();
check('Dragging changes the selected time by timeline scale',settings.jumpEvents.find(e=>e.id===id).time===1.6);
check('Dragging keeps playback time',time===1.37&&seeks.length===0);
listeners.pointerdown({target:new Element()});check('Clicking away closes editor',elements.jumpPopover.hidden);
marker.onclick();check('Clicking marker restores editor',!elements.jumpPopover.hidden);
listeners.keydown({code:'Escape'});check('Escape closes editor',elements.jumpPopover.hidden);
marker.onclick();elements.jumpTime.value='';const before=edits;elements.jumpTime.onchange();check('Empty time does not create a zero-time jump',before===edits&&elements.jumpTime.value==='1.600');
elements.jumpRemove.onclick();check('Delete removes only selected marker',settings.jumpEvents.length===1&&!settings.jumpEvents.some(e=>e.id===id));
elements.jumpMarkers.children[0].onclick();elements.jumpRemove.onclick();
check('All markers can be deleted without regenerating first jump',settings.jumpEvents.length===0&&elements.jumpMarkers.children.length===0);
elements.jumpHere.onclick();check('Plus can add after deleting all jumps',settings.jumpEvents.length===1&&settings.jumpEvents[0].time===82/60);
settings.mode='space';editor.sync();check('Schedule hides in Space mode',elements.jumpEditor.hidden);
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8');
check('No After or Gap controls remain',!html.includes('jumpAfter')&&!html.includes('jumpGap'));
check('Markers use existing playback timeline',html.indexOf('id="jumpEditor"')>html.indexOf('id="scrub"')&&html.indexOf('id="jumpEditor"')<html.indexOf('id="timeRead"'));
check('No second playback rail or playhead',!html.includes('jumpTicks')&&!html.includes('jumpPlayhead'));
check('Add button sits beside Loop at the start of the timeline',html.indexOf('id="jumpHere"')>html.indexOf('id="trimToggle"')&&html.indexOf('id="jumpHere"')<html.indexOf('class="timeline"'));
fs.writeFileSync(new URL('jump-track-verification.json',import.meta.url),JSON.stringify({passed:true,browserLayoutVerified:false,checks},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,browserLayoutVerified:false}));
