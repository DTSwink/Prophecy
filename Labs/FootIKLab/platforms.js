/* Bodyflip's finite slab editor, with Foot IK-owned scene/persistence adapters.
 * No frame-time work without a selection. Bodyflip's source is left untouched. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery,S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qexp}=R,axes=[[1,0,0],[0,1,0],[0,0,1]],colors=['#ff7777','#82e8a2','#82b7ff'];
const clone=p=>({...p,position:p.position.slice(),rotation:p.rotation.slice(),size:p.size.slice()});
const copyLayout=list=>list?.map(clone)??null;
const sameTransform=(a,b)=>a&&b&&['position','rotation','size'].every(k=>a[k].every((v,i)=>Math.abs(v-b[k][i])<1e-10));
// Letter shortcuts follow the printed key, including AZERTY's W/Z positions.
function shortcutLetter(e){return (e.key&&e.key!=='Unidentified'?e.key:(e.code||'').replace(/^Key/,'')).toLowerCase();}
function undoShortcut(e){const el=e.target;return shortcutLetter(e)==='z'&&(e.ctrlKey||e.metaKey)&&!e.altKey&&!e.shiftKey&&!el?.isContentEditable&&el?.tagName!=='TEXTAREA'&&el?.tagName!=='SELECT'&&!(el?.tagName==='INPUT'&&!['range','checkbox','radio','button','submit','reset','file','image','color','hidden'].includes(el.type));}
function ray(camera,rect,x,y){return {origin:camera.eye,direction:unit(add(camera.forward,add(mul(camera.right,(x-rect.left-rect.width/2)/camera.focalCss),mul(camera.up,-(y-rect.top-rect.height/2)/camera.focalCss))))};}
function hitBox(ray,p){
 const inv=qinv(p.rotation),o=rotate(inv,sub(ray.origin,p.position)),d=rotate(inv,ray.direction);let near=0,far=Infinity;
 for(let i=0;i<3;i++){const half=p.size[i]/2;if(Math.abs(d[i])<1e-10){if(Math.abs(o[i])>half)return null;continue;}let a=(-half-o[i])/d[i],b=(half-o[i])/d[i];if(a>b)[a,b]=[b,a];near=Math.max(near,a);far=Math.min(far,b);if(near>far)return null;}
 return far>=0?{distance:near,point:add(ray.origin,mul(ray.direction,near))}:null;
}
function pick(ray,surfaces){let best=null;for(const surface of surfaces){const hit=hitBox(ray,S.platformRecord(surface));if(hit&&(!best||hit.distance<best.distance))best={...hit,id:surface.id};}return best;}
function project(p,camera,rect){const d=sub(p,camera.eye),z=dot(d,camera.forward);return {x:rect.width/2+dot(d,camera.right)*camera.focalCss/z,y:rect.height/2-dot(d,camera.up)*camera.focalCss/z,z};}
function axisParameter(ray,origin,axis){const b=dot(ray.direction,axis),w=sub(ray.origin,origin),den=1-b*b;return den>1e-6?(dot(axis,w)-b*dot(ray.direction,w))/den:null;}
function planePoint(ray,origin,normal){const d=dot(ray.direction,normal);if(Math.abs(d)<1e-7)return null;const t=dot(sub(origin,ray.origin),normal)/d;return t>=0?add(ray.origin,mul(ray.direction,t)):null;}
function transformed(start,mode,index,amount,axis){const p=clone(start);if(mode==='move')p.position=add(start.position,mul(axis,amount));else if(mode==='rotate')p.rotation=qm(qexp(mul(axis,amount)),start.rotation);else if(index===3)p.size=start.size.map(v=>Math.max(.02,Math.min(1000,v*amount)));else p.size[index]=Math.max(.02,Math.min(1000,start.size[index]*amount));return p;}
class Editor {
 constructor(api){
  this.api=api;this.selected=null;this.mode='move';this.drag=null;this.history=[];this.preview=null;this.cachedSurfaces=api.get().surfaces;this.anchorLocal=[0,0,0];
  this.svg=document.getElementById('platformGizmo');this.hint=document.getElementById('platformMode');
  this.svg.addEventListener('pointerdown',e=>this.begin(e));
  this.svg.addEventListener('pointermove',e=>this.move(e));
  this.svg.addEventListener('pointerup',()=>this.end());
  this.svg.addEventListener('pointercancel',()=>this.end(true));
  this.svg.addEventListener('lostpointercapture',()=>this.end());
 }
 records(){return this.api.records();}
 surfaces(){return this.preview||this.api.get().surfaces;}
 select(x,y,{preview=false}={}){const {camera,rect}=this.api.get();if(!camera)return false;const hit=pick(ray(camera,rect,x,y),this.surfaces());this.selected=hit?.id||null;this.anchorLocal=[0,0,0];this.render();if(!preview){if(hit)this.api.pause();else this.api.draw();}return !!hit;}
 previewSelection(x,y){const previous={selected:this.selected,anchorLocal:this.anchorLocal.slice()};this.select(x,y,{preview:true});return previous;}
 finishSelection(previous,cancel=false,orbit=false){if(orbit){this.selected=null;this.anchorLocal=[0,0,0];this.render();}else if(cancel){this.selected=previous.selected;this.anchorLocal=previous.anchorLocal;this.render();}else if(this.selected)this.api.pause();else this.api.draw();}
 add(){
  this.end();this.api.pause();const state=this.api.get(),list=this.records().map(clone);if(list.length>=128)return;
  // Place it within reach, below the character and in front of the current view.
  let forward=unit([state.camera.forward[0],0,state.camera.forward[2]]);if(length(forward)<.5)forward=[0,0,1];
  const center=add(state.center,add([0,-1,0],mul(forward,1.5))),id='p'+Date.now().toString(36);
  list.push({id,position:center,rotation:[0,0,0,1],size:[2,.15,2]});this.selected=id;this.anchorLocal=[0,0,0];
  this.api.change(list);this.preview=this.api.build(list);this.render();this.api.draw();this.api.commit();
 }
 remove(){if(!this.selected)return;this.end(true);const list=this.records().filter(p=>p.id!==this.selected);this.selected=null;this.api.pause();this.api.change(list);const state=this.api.get();this.preview=this.api.build(this.records());this.render();this.api.draw();this.api.commit();}
 key(e){
  if(e.code==='Escape'){if(this.drag)this.end(true);else this.selected=null;this.render();this.api.draw();return true;}
  const letter=shortcutLetter(e);
  if(['w','e','r'].includes(letter)){this.end();this.mode={w:'move',e:'rotate',r:'scale'}[letter];this.render();return true;}
  if(this.selected&&['Delete','Backspace'].includes(e.code)){this.remove();return true;}return false;
 }
 undo(){
  if(this.drag){this.end(true);return;}
  // Transform history never resurrects a deleted platform or removes later additions.
  let entry;while(this.history.length){const candidate=this.history.pop();if(this.records().some(p=>p.id===candidate.start.id)){entry=candidate;break;}}
  if(!entry)return;
  this.api.pause();const current=this.api.get().settings.platforms;
  const list=JSON.stringify(current)===entry.after?copyLayout(entry.original):this.records().map(p=>p.id===entry.start.id?clone(entry.start):p);
  this.selected=entry.start.id;this.anchorLocal=entry.anchorLocal.slice();this.api.change(list);
  const state=this.api.get();this.preview=this.api.build(this.records());this.api.draw();this.api.commit();
 }
 begin(e){
  const handle=e.target.closest('[data-axis]');if(e.button!==0||!handle||!this.selected)return;
  e.preventDefault();e.stopPropagation();this.api.pause();
  const state=this.api.get(),start=clone(this.records().find(p=>p.id===this.selected)),index=+handle.dataset.axis;
  const axis=index<3?(this.mode==='scale'?rotate(start.rotation,axes[index]):axes[index]):null,origin=add(start.position,rotate(start.rotation,this.anchorLocal));
  const screen=project(origin,state.camera,state.rect),scale=Math.max(.001,screen.z)*80/state.camera.focalCss,r=ray(state.camera,state.rect,e.clientX,e.clientY);
  this.drag={original:copyLayout(state.settings.platforms),anchorLocal:this.anchorLocal.slice(),start,index,axis,origin,scale,x:e.clientX,y:e.clientY,camera:state.camera,rect:state.rect,parameter:axis?axisParameter(r,origin,axis):null,point:axis?planePoint(r,origin,axis):null,screen};
  this.svg.setPointerCapture(e.pointerId);
 }
 move(e){
  const d=this.drag;if(!d)return;e.preventDefault();const dx=e.clientX-d.x,dy=e.clientY-d.y,r=ray(d.camera,d.rect,e.clientX,e.clientY);let p;
  if(this.mode==='move'&&d.index===3){p=clone(d.start);p.position=add(p.position,add(mul(d.camera.right,dx*d.scale/80),mul(d.camera.up,-dy*d.scale/80)));}
  else if(this.mode==='rotate'){
   const point=planePoint(r,d.origin,d.axis);let angle;
   if(d.point&&point&&length(sub(d.point,d.origin))>1e-7&&length(sub(point,d.origin))>1e-7){const a=unit(sub(d.point,d.origin)),b=unit(sub(point,d.origin));angle=Math.atan2(dot(d.axis,cross(a,b)),dot(a,b));}
   else angle=(dx-dy)*.01;
   if(e.shiftKey)angle=Math.round(angle/(Math.PI/12))*Math.PI/12;p=transformed(d.start,this.mode,d.index,angle,d.axis);
  }else if(this.mode==='scale'&&d.index===3)p=transformed(d.start,'scale',3,Math.exp((dx-dy)/150));
  else {
   const current=axisParameter(r,d.origin,d.axis),end=project(add(d.origin,mul(d.axis,d.scale)),d.camera,d.rect),sx=end.x-d.screen.x,sy=end.y-d.screen.y,den=sx*sx+sy*sy;
   const delta=d.parameter!==null&&current!==null?current-d.parameter:den>4?(dx*sx+dy*sy)/den*d.scale:(dx-dy)*d.scale/80;
   p=transformed(d.start,this.mode,d.index,this.mode==='scale'?Math.exp(delta/d.scale):delta,d.axis);
  }
  // Transform around the platform center; local scaling retains its rotated axes.
  if(this.mode==='rotate')p.position=add(d.origin,rotate(qm(p.rotation,qinv(d.start.rotation)),sub(d.start.position,d.origin)));
  if(this.mode==='scale'){const factors=p.size.map((v,i)=>v/d.start.size[i]),offset=rotate(qinv(d.start.rotation),sub(d.start.position,d.origin));p.position=add(d.origin,rotate(d.start.rotation,offset.map((v,i)=>v*factors[i])));this.anchorLocal=d.anchorLocal.map((v,i)=>v*factors[i]);}
  const list=this.records().map(v=>v.id===this.selected?p:v);this.api.change(list);const state=this.api.get();this.preview=this.api.build(this.records());this.api.draw();
 }
 end(cancel=false){
  const d=this.drag;if(!d)return;this.drag=null;
  if(cancel||sameTransform(d.start,this.records().find(p=>p.id===d.start.id))){this.anchorLocal=d.anchorLocal;this.api.change(d.original);const state=this.api.get();this.preview=this.api.build(this.records());this.api.draw();}
  else {this.history.push({start:d.start,original:d.original,anchorLocal:d.anchorLocal,after:JSON.stringify(this.api.get().settings.platforms)});if(this.history.length>100)this.history.shift();this.api.commit();}
 }
 refresh(){this.cachedSurfaces=this.api.get().surfaces;this.preview=null;if(!this.surfaces().some(p=>p.id===this.selected))this.selected=null;this.render();}
 render(){
  if(!this.selected){this.hint.hidden=true;if(this.svg.childNodes.length)this.svg.replaceChildren();return;}
  const state=this.api.get(),p=this.records().find(p=>p.id===this.selected);
  this.hint.hidden=!p;this.hint.textContent=this.mode[0].toUpperCase()+this.mode.slice(1)+' · W / E / R';
  if(!p||!state.camera){if(this.svg.childNodes.length)this.svg.replaceChildren();return;}
  const {camera,rect}=state,origin=add(p.position,rotate(p.rotation,this.anchorLocal)),center=project(origin,camera,rect);if(center.z<=.01){this.svg.replaceChildren();return;}
  this.svg.setAttribute('viewBox',`0 0 ${rect.width} ${rect.height}`);
  const size=center.z*80/camera.focalCss,xy=v=>`${v.x.toFixed(2)},${v.y.toFixed(2)}`,parts=[];
  const path=(d,i,color)=>{parts.push(`<path d="${d}" stroke="transparent" stroke-width="16" fill="none" pointer-events="stroke" data-axis="${i}"/><path d="${d}" stroke="${color}" stroke-width="2.5" fill="none" pointer-events="none"/>`);};
  for(let i=0;i<3;i++){
   const axis=this.mode==='scale'?rotate(p.rotation,axes[i]):axes[i];
   if(this.mode==='rotate'){
    const a=axes[(i+1)%3],b=axes[(i+2)%3],points=[];
    for(let j=0;j<=64;j++){const t=j*Math.PI/32;points.push(project(add(origin,add(mul(a,Math.cos(t)*size),mul(b,Math.sin(t)*size))),camera,rect));}
    if(points.every(v=>v.z>.01))path(points.map((v,j)=>(j?'L':'M')+xy(v)).join(' '),i,colors[i]);
   }else{
    const end=project(add(origin,mul(axis,size)),camera,rect);if(end.z<=.01)continue;
    path('M'+xy(center)+' L'+xy(end),i,colors[i]);
    if(this.mode==='scale')parts.push(`<rect x="${end.x-6}" y="${end.y-6}" width="12" height="12" fill="${colors[i]}" stroke="#172130" stroke-width="1.5" data-axis="${i}" pointer-events="all"/>`);
    else {
     const dx=end.x-center.x,dy=end.y-center.y,len=Math.hypot(dx,dy),ux=len>1e-5?dx/len:0,uy=len>1e-5?dy/len:-1;
     const base={x:end.x-ux*17,y:end.y-uy*17};
     parts.push(`<polygon points="${xy(end)} ${xy({x:base.x-uy*7,y:base.y+ux*7})} ${xy({x:base.x+uy*7,y:base.y-ux*7})}" fill="${colors[i]}" data-axis="${i}" pointer-events="all"/>`);
    }
    parts.push(`<text x="${end.x+8}" y="${end.y+4}" fill="${colors[i]}" font-size="12" pointer-events="none">${'XYZ'[i]}</text>`);
   }
  }
  if(this.mode==='move')parts.push(`<circle cx="${center.x}" cy="${center.y}" r="6" fill="#f0edff" stroke="#33405a" data-axis="3" pointer-events="all"/>`);
  else if(this.mode==='scale')parts.push(`<rect x="${center.x-6}" y="${center.y-6}" width="12" height="12" fill="#f0edff" stroke="#33405a" data-axis="3" pointer-events="all"/>`);
  this.svg.innerHTML=parts.join('');
 }
}
const api={ray,hitBox,pick,project,axisParameter,planePoint,transformed,undoShortcut,Editor};if(typeof module!=='undefined')module.exports=api;else root.FootPlatforms=api;
})(globalThis);
