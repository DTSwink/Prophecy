import fs from 'node:fs';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),F=require('./flight.js'),P=require('./platforms.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8')),checks=[];
const check=(name,v)=>{assert(v,name);checks.push(name);},dist=(a,b)=>R.length(R.sub(a,b));
const basic={id:'block',position:[0,0,0],rotation:[0,0,0,1],size:[2,.2,2]};
for(const surface of S.terrain(4.88)){
 const copy=S.platformSurface(S.platformRecord(surface));
 check(surface.id+' editable roundtrip normal',dist(surface.normal,copy.normal)<1e-9);
 check(surface.id+' editable roundtrip box',dist(surface.box.center,copy.box.center)<1e-9&&dist(surface.box.dims,copy.box.dims)<1e-9);
}
const moved=P.transformed(basic,'move',0,3,[1,0,0]);check('Translation follows axis',dist(moved.position,[3,0,0])<1e-9);
const rotated=P.transformed(basic,'rotate',2,Math.PI/2,[0,0,1]);check('Rotation turns support normal',dist(S.platformSurface(rotated).normal,[-1,0,0])<1e-9);
const scaled=P.transformed(basic,'scale',0,2);check('Axis scale preserves other dimensions',dist(scaled.size,[4,.2,2])<1e-9);
check('Uniform scale preserves proportions',dist(P.transformed(basic,'scale',3,3).size,[6,.6,6])<1e-9);
check('Negative scale cannot invert a platform',P.transformed(basic,'scale',0,-10).size[0]===.02);
const saved=C.sanitize({platforms:[moved,rotated,scaled]});check('Transforms persist through JSON',JSON.stringify(C.sanitize(JSON.parse(JSON.stringify(saved))).platforms)===JSON.stringify(saved.platforms));
check('Empty layout stays empty',S.scene(4,C.sanitize({platforms:[]})).length===0);
const hit=P.hitBox({origin:[0,4,0],direction:[0,-1,0]},basic);check('Picking hits slab top',Math.abs(hit.point[1]-.1)<1e-9);
check('Picking rejects finite edge miss',P.hitBox({origin:[2,4,0],direction:[0,-1,0]},basic)===null);
const nearest=P.pick({origin:[0,4,0],direction:[0,-1,0]},[S.platformSurface(basic),S.platformSurface({...basic,id:'near',position:[0,2,0]})]);check('Picking selects nearest platform',nearest.id==='near');
const camera={eye:[0,2,6],forward:R.unit([0,-2,-6]),right:[1,0,0],up:R.unit([0,6,-2]),focalCss:700},rect={left:280,top:60,width:1000,height:600};
const point=[.5,.1,.3],screen=P.project(point,camera,rect),ray=P.ray(camera,rect,screen.x+rect.left,screen.y+rect.top);
check('Ray accounts for viewport offset',R.length(R.cross(R.sub(point,ray.origin),ray.direction))<1e-8);
for(const normal of [[1,0,0],[0,0,-1],[-1,0,0],[0,1,0],R.unit([1,1,0])]){
 const angle=Math.acos(R.dot(normal,[0,1,0]));
 for(const skew of [0,.5,1]){const direction=F.jumpDirection(normal,skew);check('Angular up skew '+normal+'/'+skew,Math.abs(Math.acos(Math.max(-1,Math.min(1,direction[1])))-angle*(1-skew))<1e-7);}
}
check('Default wall push is 45 degrees up',Math.abs(F.jumpDirection([1,0,0],C.defaults.jumpSkew)[1]-Math.SQRT1_2)<1e-9);
const m=read('data/manifest.json'),run=F.decodeNN(read('data/roll-check.json')),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),pose=F.at(run,.5,m.parents),leg=S.leg(pose,run.names,'R');
const normal=[0,0,-1],contact=R.add(pose.points[leg.foot],S.lowestOffset(pose,leg,normal)),wall=S.rectangle('wall',contact,[1,0,0],[0,1,0],[-2,2,-2,2]);
const context={time:0,surface:wall,poseAt:()=>pose,velocityAt:()=>[0,0,0],speed:0},settings=C.sanitize({...read('roll-settings.json'),loadMs:0,jumpFoot:'R',jumpSkew:.5});
const wallJump=F.create(run,jumps,settings,m.parents,pose,context);
check('Vertical wall contact can start a jump',Number.isFinite(wallJump.jumpStart));
check('Wall plant rotations remain finite when forward equals normal',wallJump.support.leg.plant.footQ.every(Number.isFinite));
const t=2/jumps.find(c=>c.name===wallJump.start).fps,a=wallJump.sample(wallJump.jumpStart).root,b=wallJump.sample(wallJump.jumpStart+t).root,delta=R.sub(b,a);
check('Authored wall push gains height',delta[1]>0);
check('Wall launch at rest is 45 degrees over first two samples',Math.abs(delta[1]+delta[2])<1e-6);
const empty=F.sequence(run,jumps,{...settings,platforms:[],jumpEvents:[{id:'jump',time:.5,surface:'auto'}]},m.parents);
check('Deleting all surfaces cannot manufacture lift',empty.events[0].status==='Miss'&&empty.segments.length===0);
// Exercise the actual gizmo event handlers with a small DOM adapter.
class Element{constructor(){this.listeners={};this.childNodes=[];this.hidden=false;this.attrs={};this.innerHTML='';}addEventListener(k,v){this.listeners[k]=v;}setAttribute(k,v){this.attrs[k]=v;}replaceChildren(){this.childNodes=[];this.innerHTML='';}setPointerCapture(){}}
const elements={platformGizmo:new Element(),platformMode:new Element()};globalThis.document={getElementById:k=>elements[k]};
let editSettings=C.sanitize({platforms:[basic]}),commits=0,pauses=0;
const editor=new P.Editor({get:()=>({settings:editSettings,edge:4,surfaces:S.scene(4,editSettings),camera,rect,center:[0,1,0]}),pause:()=>pauses++,draw:()=>editor.render(),change:list=>{editSettings=C.sanitize({...editSettings,platforms:list});},commit:()=>commits++});
const preview=editor.previewSelection(780,360);
check('Press renders gizmo immediately without pausing or replanning',editor.selected==='block'&&elements.platformGizmo.innerHTML.includes('data-axis=')&&pauses===0&&commits===0);
editor.finishSelection(preview,true);
check('Orbit cancellation restores previous selection without pausing',editor.selected===null&&pauses===0);
editor.select(780,360);check('Clicking platform selects it',editor.selected==='block');
editor.select(screen.x+rect.left,screen.y+rect.top);
check('Off-center surface click anchors gizmo at slab center',editor.selected==='block'&&dist(editor.anchorLocal,[0,0,0])<1e-10);
const selectedPreview=editor.previewSelection(780,360);editor.finishSelection(selectedPreview,true,true);
check('Orbit clears an existing selection instead of restoring it',editor.selected===null);
editor.select(780,360);
const start=P.project([0,0,0],camera,rect),pointer=(axis,x,y)=>({button:0,target:{closest:()=>({dataset:{axis:String(axis)}})},clientX:x,clientY:y,pointerId:1,preventDefault(){},stopPropagation(){}});
for(const mode of ['KeyE','KeyR']){
 editor.key({code:mode});editor.begin(pointer(mode==='KeyE'?1:3,780,360));
 check('Gizmo transform origin is platform center '+mode,dist(editor.drag.origin,basic.position)<1e-10);
 editor.move({clientX:825,clientY:335,preventDefault(){}});
 check('Rotation and scale leave the platform center fixed '+mode,dist(editSettings.platforms[0].position,basic.position)<1e-10);editor.end(true);
}
editor.key({code:'KeyW'});editor.begin(pointer(0,start.x+rect.left+40,start.y+rect.top));editor.move({clientX:start.x+rect.left+100,clientY:start.y+rect.top,preventDefault(){}});
check('Gizmo drag changes preview before release',editSettings.platforms[0].position[0]>.1&&commits===0);
editor.end();check('Drag release commits one replan',commits===1);
editor.key({code:'KeyR'});check('R selects scale rather than reset',editor.mode==='scale');
const before=JSON.stringify(editSettings.platforms);editor.begin(pointer(3,780,360));editor.move({clientX:850,clientY:320,preventDefault(){}});editor.end(true);
check('Cancel restores the drag starting layout',JSON.stringify(editSettings.platforms)===before&&commits===1);
editor.key({code:'KeyE'});check('E selects rotation',editor.mode==='rotate');editor.render();check('Rotation displays three rings',(elements.platformGizmo.innerHTML.match(/data-axis=/g)||[]).length===3);
editor.key({code:'Delete'});check('Delete removes selected platform',editSettings.platforms.length===0&&editor.selected===null);
editor.add();check('Add creates and selects a platform',editSettings.platforms.length===1&&editor.selected===editSettings.platforms[0].id);
editor.key({code:'Backspace'});check('Backspace removes selected platform',editSettings.platforms.length===0);
// Undo is one completed transform per step, with no rebuild for cancelled/no-op drags.
editSettings=C.sanitize({platforms:[basic]});editor.history=[];editor.selected='block';editor.anchorLocal=[.4,.1,.2];
const snapshots=[];
for(const mode of ['KeyW','KeyE','KeyR']){
 snapshots.push({layout:JSON.stringify(editSettings.platforms),anchor:[...editor.anchorLocal]});
 editor.key({code:mode});editor.begin(pointer(mode==='KeyE'?1:3,780,360));
 editor.move({clientX:835,clientY:330,preventDefault(){}});editor.end();
}
check('Three completed transforms make three undo steps',editor.history.length===3);
const beforeUndo=commits;editSettings.supportAlpha=19;
for(let i=2;i>=0;i--){editor.undo();check('Undo restores '+['move','rotation','scale'][i],JSON.stringify(editSettings.platforms)===snapshots[i].layout&&dist(editor.anchorLocal,snapshots[i].anchor)<1e-10);}
check('Undo rebuilds once per operation and keeps tuning',commits===beforeUndo+3&&editSettings.supportAlpha===19);
editor.undo();check('Empty history does not rebuild',commits===beforeUndo+3);
editor.key({code:'KeyW'});editor.begin(pointer(3,780,360));editor.end();
check('Click without movement adds no history or rebuild',editor.history.length===0&&commits===beforeUndo+3);
editor.begin(pointer(3,780,360));editor.move({clientX:830,clientY:330,preventDefault(){}});editor.undo();
check('Undo during drag cancels preview without committing',JSON.stringify(editSettings.platforms)===snapshots[0].layout&&editor.drag===null&&editor.history.length===0&&commits===beforeUndo+3);
editor.begin(pointer(3,780,360));editor.move({clientX:830,clientY:330,preventDefault(){}});editor.end();
editor.add();const added=editor.selected;editor.undo();
check('Undo keeps subsequently added platform',editSettings.platforms.some(p=>p.id===added)&&sameRecord(editSettings.platforms.find(p=>p.id==='block'),basic));
function sameRecord(a,b){return a?.id===b?.id&&['position','rotation','size'].every(k=>dist(a[k],b[k])<1e-10);}
editor.begin(pointer(3,780,360));editor.move({clientX:830,clientY:330,preventDefault(){}});editor.end();editor.remove();const afterDelete=commits;editor.undo();
check('Undo skips transforms of deleted platforms',!editSettings.platforms.some(p=>p.id==='block')&&commits===afterDelete);
editSettings=C.sanitize({platforms:null});editor.history=[];editor.selected='floor';editor.anchorLocal=[0,0,0];
editor.begin(pointer(3,780,360));editor.move({clientX:830,clientY:330,preventDefault(){}});editor.end();editor.refresh();editor.undo();
check('First transform undo restores procedural default layout after replan',editSettings.platforms===null);
const oldSettings=C.sanitize({platforms:[moved],ramps:false,supportAlpha:7}),reset=P.restoreDefaultsOnce(oldSettings);
check('Requested reset restores floor and both ramps only',reset.platforms===null&&reset.ramps&&reset.supportAlpha===7&&S.scene(4,reset).length===3);
check('Reset is one-time and permits subsequent saved edits',P.restoreDefaultsOnce({...reset,platforms:[moved]}).platforms[0]===moved);
for(const target of [{tagName:'INPUT',type:'number'},{tagName:'INPUT',type:'text'},{tagName:'TEXTAREA'},{tagName:'DIV',isContentEditable:true},{tagName:'SELECT'}])check('Native undo retained for '+target.tagName+'/'+target.type, !P.undoShortcut({code:'KeyZ',ctrlKey:true,target}));
for(const target of [{tagName:'CANVAS'},{tagName:'BUTTON'},{tagName:'INPUT',type:'range'}])check('Global undo from '+target.tagName+'/'+target.type,P.undoShortcut({code:'KeyZ',ctrlKey:true,target}));
check('Plain Z and redo do not trigger undo',!P.undoShortcut({code:'KeyZ',target:{}})&&!P.undoShortcut({code:'KeyZ',ctrlKey:true,shiftKey:true,target:{}}));
// Visible move handles and letter shortcuts on QWERTY and AZERTY.
for(const key of [{key:'w',code:'KeyW'},{key:'w',code:'KeyZ'},{key:'W',code:'KeyZ'}]){
 editor.mode='scale';editor.key(key);
 check('Printed W shows Move gizmo '+key.key+'/'+key.code,editor.mode==='move'&&(elements.platformGizmo.innerHTML.match(/<polygon /g)||[]).length===3);
}
editor.key({key:'r',code:'KeyR'});editor.key({key:'z',code:'KeyW'});
check('AZERTY Z does not incorrectly select Move',editor.mode==='scale');
check('AZERTY Ctrl Z undoes',P.undoShortcut({key:'z',code:'KeyW',ctrlKey:true,target:{tagName:'CANVAS'}}));
check('AZERTY Ctrl W does not undo',!P.undoShortcut({key:'w',code:'KeyZ',ctrlKey:true,target:{tagName:'CANVAS'}}));
delete globalThis.document;
// Run the actual wheel/orbit handler, without a browser or WebGL context.
const app=fs.readFileSync(new URL('app.js',import.meta.url),'utf8'),part=app.slice(app.indexOf(' bindCamera(){'),app.indexOf('\n draw(data,root)'));
// Execute the real focus-transfer capture handler: dropdowns must release keyboard focus.
let focusCount=0,blurCount=0;
const focusCanvas={focus:()=>focusCount++},gizmoTarget={},focusSvg={contains:t=>t===gizmoTarget};
const focusCode=app.split('\n').find(line=>line.includes("document.addEventListener('pointerdown',e=>{const active=document.activeElement"));
const focusCallbacks={},focusDocument={activeElement:{matches:()=>false},addEventListener:(name,fn)=>focusCallbacks[name]=fn};
vm.runInNewContext(focusCode,{document:focusDocument,$:id=>id==='viewport'?focusCanvas:focusSvg});
focusCallbacks.pointerdown({target:focusCanvas});
check('Viewport click takes focus from dropdown',focusCount===1);
focusCallbacks.pointerdown({target:gizmoTarget});
check('Gizmo click takes keyboard focus',focusCount===2);
focusDocument.activeElement={matches:()=>true,blur:()=>blurCount++};
focusCallbacks.pointerdown({target:focusCanvas});
check('Viewport commits numeric editor before taking focus',focusCount===3&&blurCount===1);
focusCallbacks.pointerdown({target:focusDocument.activeElement});
check('Click within numeric editor retains editing focus',focusCount===3&&blurCount===1);
const callbacks={},canvas={addEventListener:(name,fn)=>callbacks[name]=fn,setPointerCapture(){}},state={zoom:.95,yaw:0,pitch:0,panX:0,panY:0};
const sandbox=vm.createContext({cameraState:state,settings:{mode:'space',target:[0,0,0]},platformEditor:null,clamp:(v,a,b)=>Math.max(a,Math.min(b,v)),drawAll(){},save(){},resetCamera(){}});
vm.runInContext('class Camera {'+part+'}\nglobalThis.Camera=Camera;',sandbox);const binding=new sandbox.Camera();binding.canvas=canvas;binding.bindCamera();
for(let i=0;i<100;i++)callbacks.wheel({deltaY:100,preventDefault(){}});
check('Wheel zooms far beyond old limit',state.zoom<.0001&&state.zoom>0);
callbacks.pointerdown({button:0,clientX:0,clientY:0,pointerId:1,preventDefault(){}});callbacks.pointermove({clientX:10,clientY:10});
check('Corrected orbit axes stay intact',state.yaw===-.08&&state.pitch===-.06);
// Clicking selects; dragging over a platform must reach the camera first.
callbacks.pointerup({type:'pointerup',clientX:10,clientY:10});
sandbox.settings.mode='jump';let selectedClicks=0,previews=0,cancelledPreviews=0;
let clearedSelections=0;
sandbox.platformEditor={previewSelection(){previews++;return {};},finishSelection(previous,cancel,orbit){if(orbit)clearedSelections++;if(cancel)cancelledPreviews++;else selectedClicks++;}};
const down=(x=100,y=100,extras={})=>callbacks.pointerdown({button:0,clientX:x,clientY:y,pointerId:1,preventDefault(){},...extras});
const move=(x,y)=>callbacks.pointermove({clientX:x,clientY:y});
const up=(x,y)=>callbacks.pointerup({type:'pointerup',clientX:x,clientY:y});
let yaw=state.yaw,pitch=state.pitch;down();
check('Press previews gizmo immediately without committing a click',previews===1&&selectedClicks===0&&binding.drag!==null);
move(120,110);up(120,110);
check('Left drag over platform cancels preview and orbits',selectedClicks===0&&cancelledPreviews===1&&Math.abs(state.yaw-(yaw-.16))<1e-10&&Math.abs(state.pitch-(pitch-.06))<1e-10);
check('Actual camera drag requests deselection',clearedSelections===1);
yaw=state.yaw;pitch=state.pitch;down();move(102,101);up(102,101);
check('Click tolerates original hand jitter without orbit',selectedClicks===1&&state.yaw===yaw&&state.pitch===pitch);
yaw=state.yaw;down();move(104,100);up(104,100);
check('Orbit retains original four-pixel threshold with no timer',selectedClicks===1&&Math.abs(state.yaw-(yaw-.032))<1e-10);
down();move(120,100);move(100,100);up(100,100);
check('Drag returning to start is still not a click',selectedClicks===1);
down();callbacks.pointercancel({type:'pointercancel'});
check('Cancelled pointer restores preview without selecting',selectedClicks===1&&cancelledPreviews===4&&binding.drag===null);
down();callbacks.lostpointercapture({type:'lostpointercapture'});up(100,100);
check('Lost capture clears pending click and preview',selectedClicks===1&&cancelledPreviews===5&&binding.drag===null);
down(100,100,{altKey:true});up(100,100);
check('Alt click retains camera-only behavior',selectedClicks===1);
const panX=state.panX,panY=state.panY;down(100,100,{button:1});move(110,115);up(110,115);
check('Middle drag still pans without selecting',selectedClicks===1&&state.panX===panX+10&&state.panY===panY+15);
const clearedBefore=clearedSelections;down();up(120,100);
check('Pointerup displacement clears selection even without move event',clearedSelections===clearedBefore+1);
fs.writeFileSync(new URL('platform-verification.json',import.meta.url),JSON.stringify({passed:true,browserVisualVerified:false,checks},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,browserVisualVerified:false}));
