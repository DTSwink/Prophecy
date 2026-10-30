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
const ids=['jumpInstantSpin','jumpPushWith','jumpPercent','jumpAttack','jumpAttackDelay','jumpAttackIn','jumpAttackOut','jumpEditor','jumpHere','jumpRemove','jumpTime','jumpLane','jumpPopover','jumpLabel','jumpStatus','jumpMarkers','jumpFlip','jumpTwist','jumpDelay','jumpDuration','jumpTurnIn','jumpTurnOut','jumpAxis','jumpPose','jumpPoseIn','jumpPoseHold','jumpPoseOut','jumpPoseTiming','minorOptions','jumpOptionsLabel'],elements=Object.fromEntries(ids.map(id=>[id,new Element()])),listeners={};
const document={getElementById:id=>elements[id],createElement:()=>new Element(),addEventListener:(name,fn)=>listeners[name]=fn,activeElement:null};
let settings=C.sanitize(),time=1.37,edits=0,seeks=[],results=[];
const context=vm.createContext({document,setTimeout,clearTimeout,Date,BodyflipCore:C,BodyflipJumpAttack:require('./jump-attack.js')});
vm.runInContext(fs.readFileSync(new URL('jump-track.js',import.meta.url),'utf8')+'\nglobalThis.Editor=JumpTrack;',context);
const editor=new context.Editor({get:()=>({settings,events:F.eventsFor(settings),results,time,max:12}),edit:events=>{edits++;settings=C.sanitize({...settings,jumpEvents:events});},seek:t=>seeks.push(t)}),checks=[];
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
settings.mode='idle';editor.sync();check('Schedule stays available in Idle',!elements.jumpEditor.hidden);
check('New jump keeps the prior rate and adds no pose',elements.jumpFlip.value===''&&elements.jumpTwist.value===''&&elements.jumpDelay.value==='0'&&elements.jumpPose.value==='none');
check('Pose blend fields inactive until a pose is selected',elements.jumpPoseIn.disabled&&elements.jumpPoseHold.disabled&&elements.jumpPoseOut.disabled);
for(const [id,value,key] of [['jumpPercent','25','jumpPercent'],['jumpAttack','jabR','attack'],['jumpAttackDelay','.3','attackDelay'],['jumpAttackIn','.15','attackIn'],['jumpAttackOut','.35','attackOut'],['jumpFlip','720','flip'],['jumpTwist','-360','twist'],['jumpDelay','.25','turnDelay'],['jumpDuration','1.2','turnDuration'],['jumpAxis','3','turnAxis'],['jumpPose','pose3','pose'],['jumpPoseIn','.3','poseIn'],['jumpPoseHold','.4','poseHold'],['jumpPoseOut','.5','poseOut']]){
 elements[id].value=value;elements[id].onchange();check('Edit persists '+key,settings.jumpEvents[0][key]===((id==='jumpPose'||id==='jumpAttack')?value:+value));
}
check('Pose blend fields become available',!elements.jumpPoseIn.disabled&&!elements.jumpPoseOut.disabled);
check('Old markers retain foot support',elements.jumpPushWith.value==='foot');
elements.jumpPushWith.value='handL';elements.jumpPushWith.onchange();check('Hand selection persists per marker',settings.jumpEvents[0].pushWith==='handL');
elements.jumpPushWith.value='handBoth';elements.jumpPushWith.onchange();
check('Both hands selection persists per marker',settings.jumpEvents[0].pushWith==='handBoth'&&elements.jumpPushWith.value==='handBoth');
check('Both hands survives saved settings roundtrip',C.sanitize(JSON.parse(JSON.stringify(settings))).jumpEvents[0].pushWith==='handBoth');
check('Existing hand choices and foot default remain stable',['foot','hand','handL','handR'].every(pushWith=>C.sanitizeJump({pushWith}).pushWith===pushWith)&&C.sanitizeJump({pushWith:'unknown'}).pushWith==='foot');
results=[{id:settings.jumpEvents[0].id,status:'Push',pushTime:1.5,surfaceId:'floor',supportKind:'hand',supportSide:'Both'}];editor.sync();
check('Paired push status says Both hands',elements.jumpStatus.textContent.endsWith('Both hands'));
results[0].supportSide='R';editor.sync();
check('Single-hand fallback status shows actual side without changing requested mode',elements.jumpStatus.textContent.endsWith('R hand')&&elements.jumpPushWith.value==='handBoth');
results=[];editor.sync();
check('Every direction is selectable',elements.jumpAxis.children.length===12);
document.activeElement=elements.jumpFlip;elements.jumpFlip.value='360';listeners.pointerdown({target:new Element()});document.activeElement=null;
check('Clicking away commits value before closing popup',settings.jumpEvents[0].flip===360&&elements.jumpPopover.hidden);
elements.jumpMarkers.children[0].onclick();const frozen=edits;elements.jumpFlip.onchange();check('Unchanged value does not recompute motion',edits===frozen);
elements.jumpFlip.value='';elements.jumpFlip.onchange();check('Empty speed keeps the inherited command',settings.jumpEvents[0].flip===null&&settings.jumpEvents[0].spinVersion===2&&elements.jumpFlip.value==='');
elements.jumpFlip.value='0';elements.jumpFlip.onchange();check('Explicit zero is retained as a stop command',settings.jumpEvents[0].flip===0&&elements.jumpFlip.value==='0');
elements.jumpFlip.value='360';elements.jumpFlip.onchange();
const configured=JSON.stringify(settings.jumpEvents[0]);editor.add(3);check('Adding another jump retains first choreography',JSON.stringify(settings.jumpEvents[0])===configured&&settings.jumpEvents[1].pose==='none');
elements.jumpPose.value='pose4';elements.jumpPose.onchange();elements.jumpMarkers.children[0].onclick();check('Selecting marker restores that jump settings',elements.jumpPose.value==='pose3'&&elements.jumpFlip.value==='360');
elements.jumpInstantSpin.checked=true;elements.jumpInstantSpin.onchange();
check('Instant spin edits only the selected jump',settings.jumpEvents[0].instantSpin===true&&settings.jumpEvents[1].instantSpin===false);
elements.jumpMarkers.children[1].onclick();check('Unchecked marker shows its own spin mode',elements.jumpInstantSpin.checked===false);
elements.jumpMarkers.children[0].onclick();check('Checked marker restores its spin mode',elements.jumpInstantSpin.checked===true);
const clone=JSON.parse(JSON.stringify(settings));check('Settings survive save and reload',JSON.stringify(C.sanitize(clone).jumpEvents)===JSON.stringify(settings.jumpEvents));
check('All choreography edits leave the playhead alone',time===1.37&&seeks.length===0);
const selected=editor.selected;listeners.pointerdown({target:elements.minorOptions});
check('More options retains the selected jump without leaving popup open',editor.selected===selected&&elements.jumpPopover.hidden&&elements.jumpOptionsLabel.textContent.startsWith('J1'));
for(const [id,value,key] of [['jumpTurnIn','.1','turnIn'],['jumpTurnOut','.3','turnOut'],['jumpDuration','1.1','turnDuration'],['jumpPoseOut','.4','poseOut']]){elements[id].value=value;elements[id].onchange();check('More options edits the retained jump '+key,settings.jumpEvents[0][key]===+value&&settings.jumpEvents[1][key]!==+value);}
elements.jumpMarkers.children[1].onclick();check('Selecting another marker updates advanced controls',elements.jumpTurnIn.value===String(settings.jumpEvents[1].turnIn)&&elements.jumpOptionsLabel.textContent.startsWith('J2'));
const html=fs.readFileSync(new URL('index.html',import.meta.url),'utf8');
check('Instant spin is appended inside the jump popup',html.indexOf('id="jumpInstantSpin"')>html.indexOf('id="jumpPushWith"')&&html.indexOf('id="jumpInstantSpin"')<html.indexOf('id="timeRead"')&&!html.includes('id="instantSpin"'));
check('No After or Gap controls remain',!html.includes('jumpAfter')&&!html.includes('jumpGap'));
check('Markers use existing playback timeline',html.indexOf('id="jumpEditor"')>html.indexOf('id="scrub"')&&html.indexOf('id="jumpEditor"')<html.indexOf('id="timeRead"'));
check('No second playback rail or playhead',!html.includes('jumpTicks')&&!html.includes('jumpPlayhead'));
check('Add button sits beside Loop at the start of the timeline',html.indexOf('id="jumpHere"')>html.indexOf('id="trimToggle"')&&html.indexOf('id="jumpHere"')<html.indexOf('class="timeline"'));
check('Main values stay below original popup controls',html.indexOf('id="jumpStatus"')<html.indexOf('id="jumpFlip"'));
check('Detailed timing appends at the bottom of More options',html.indexOf('id="rebound"')<html.indexOf('id="jumpDuration"')&&html.indexOf('id="jumpDuration"')<html.indexOf('class="readouts"')&&html.indexOf('id="jumpPoseOut"')<html.indexOf('class="readouts"'));
check('All four placeholders and No pose have stable identifiers',['none','pose1','pose2','pose3','pose4'].every(id=>html.includes('value="'+id+'"')));
check('Hand selector appends below existing marker fields',html.indexOf('id="jumpPushWith"')>html.indexOf('id="jumpAttackDelay"'));
const supportSelector=html.match(/<select id="jumpPushWith"[^>]*>(.*?)<\/select>/s)[1];
check('Both hands appends after all existing support choices',[...supportSelector.matchAll(/value="([^"]+)"/g)].map(match=>match[1]).join(',')==='foot,hand,handL,handR,handBoth'&&supportSelector.includes('value="handBoth">Both hands</option>'));
check('Hand timing appends at bottom of More options',html.indexOf('id="handBend"')>html.indexOf('id="softAttackLegs"')&&html.indexOf('id="handBend"')<html.indexOf('class="readouts"'));
fs.writeFileSync(new URL('jump-track-verification.json',import.meta.url),JSON.stringify({passed:true,browserLayoutVerified:false,checks},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,browserLayoutVerified:false}));
