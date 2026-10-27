'use strict';
// Editor overlay only: no animation loop or work when both widgets are hidden.
class ThrowGizmos {
 constructor(svg,{begin,change,end}){
  this.svg=svg;this.callbacks={begin,change,end};this.widgets={};this.active=null;
  this.leftControl=false;
  // Registered before the app's active-drag shortcut guard, so precision can
  // change during a drag. Track the physical side; Right Ctrl stays normal.
  window.addEventListener('keydown',e=>{if(e.code==='ControlLeft')this.leftControl=true;},true);
  window.addEventListener('keyup',e=>{if(e.code==='ControlLeft')this.leftControl=false;},true);
  window.addEventListener('blur',()=>{this.leftControl=false;});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)this.leftControl=false;});
  const node=(tag,attrs,parent)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);parent.append(n);return n;};
  for(const kind of ['hand','forearm','velocity','weapon','move']){
   const group=node('g',{'data-gizmo':kind},svg),label=node('text',{class:'gizmo-label'},group),labelText=node('tspan',{},label),arrow=node('path',{class:'gizmo-arrow'},group),rings=[];
   for(let axis=0;axis<3;axis++){
    const g=node('g',{'data-axis':axis},group),color=['#ff706b','#7de497','#70acff'][axis],line=node('path',{class:'gizmo-ring',stroke:color},g),hit=node('path',{class:'gizmo-hit','data-kind':kind,'data-axis':axis,'aria-label':kind+' rotation '+['X','Y','Z'][axis]},g);
    hit.addEventListener('pointerdown',e=>this.down(e));
    hit.addEventListener('dblclick',e=>e.stopPropagation());rings.push({line,hit});
   }
   this.widgets[kind]={group,label,labelText,arrow,rings};
  }
  const group=node('g',{'data-scale-widget':'weapon'},svg),handles=[];
  this.scaleWidget={group,handles};
  for(let axis=0;axis<3;axis++){
   const color=['#ff706b','#7de497','#70acff'][axis],line=node('path',{class:'gizmo-ring',stroke:color},group),handle=node('rect',{class:'gizmo-scale',stroke:color,width:12,height:12,'data-scale-axis':axis,'aria-label':'Weapon local '+['X','Y','Z'][axis]+' scale'},group),label=node('text',{class:'gizmo-label'},group);
   node('title',{},handle).textContent='Local '+['X','Y','Z'][axis]+': drag toward the grip to shrink; away to enlarge';
   const item={line,handle,label};handles.push(item);
   handle.addEventListener('pointerdown',e=>{if(e.button!==0||this.active)return;e.preventDefault();e.stopPropagation();this.callbacks.begin('scale');this.active={kind:'scale',axis,pointer:e.pointerId,startPoint:this.pointer(e),direction:item.direction.slice(),scale:this.scaleWidget.value.slice(),target:svg};svg.setPointerCapture(e.pointerId);});
  }
  const text=node('tspan',{id:'rotationReadout','pointer-events':'none'},this.widgets.hand.label);
  text.style.display='none';this.readout={group:text,text};this.pointerPosition=null;
  svg.addEventListener('pointermove',e=>this.move(e));
  svg.addEventListener('pointerleave',()=>{if(!this.active){this.pointerPosition=null;this.hover(null);}});
  for(const name of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(name,e=>this.finish(e));
 }
 project(p){const R=Recovery,v=R.sub(p,this.view.eye),z=R.dot(v,this.view.forward);if(z<.02)return null;return [this.width/2+R.dot(v,this.view.right)*this.view.focalCss/z,this.height/2-R.dot(v,this.view.up)*this.view.focalCss/z];}
 axes(base,a){const R=Recovery,qx=ThrowVanilla.rotation([a[0],0,0]),qxy=ThrowVanilla.rotation([a[0],a[1],0]);return [R.rotate(base,[1,0,0]),R.rotate(R.qm(base,qx),[0,1,0]),R.rotate(R.qm(base,qxy),[0,0,1])];}
 point(ring,angle){const R=Recovery;return R.add(ring.center,R.mul(R.add(R.mul(ring.u,Math.cos(angle)),R.mul(ring.v,Math.sin(angle))),ring.radius));}
 draw(view,models){
  this.models=models;
  this.scaleWidget.group.style.display='none';
  if(!Object.values(models).some(Boolean)){for(const w of Object.values(this.widgets))w.group.style.display='none';this.updateReadout();return;}
  this.view=view;const rect=this.svg.getBoundingClientRect();this.width=rect.width;this.height=rect.height;this.svg.setAttribute('viewBox',`0 0 ${this.width} ${this.height}`);
  const R=Recovery;
  for(const [kind,w] of Object.entries(this.widgets)){
   const model=models[kind],center=model&&this.project(model.center);w.group.style.display=center?'':'none';if(!center)continue;
   const pixels=kind==='hand'?52:kind==='weapon'?66:kind==='move'?105:82,radius=R.dot(R.sub(model.center,view.eye),view.forward)*pixels/view.focalCss;
   const axes=model.world?[[1,0,0],[0,1,0],[0,0,1]]:kind==='forearm'?model.axes:kind!=='velocity'?R.toAxes(R.qm(model.base,ThrowVanilla.rotation(model.angles))):this.axes(model.base,model.angles);
   w.label.setAttribute('x',center[0]+pixels+8);w.label.setAttribute('y',center[1]+(kind==='weapon'?16:-8));w.labelText.textContent=kind==='hand'?'HAND - '+(model.world?'WORLD':'LOCAL')+' [L]':kind==='forearm'?'FOREARM - LOCAL':kind==='weapon'?'GRIP - LOCAL':kind==='move'?'':'VELOCITY';
   w.arrow.setAttribute('d','');if(model.direction&&R.length(model.direction)>1e-9){const tip=this.project(R.add(model.center,R.mul(R.unit(model.direction),radius*1.65)));if(tip){const d=[tip[0]-center[0],tip[1]-center[1]],len=Math.hypot(...d);if(len>1){const u=d.map(x=>x/len),back=[tip[0]-u[0]*11,tip[1]-u[1]*11];w.arrow.setAttribute('d',`M${center} L${tip} M${[back[0]-u[1]*5,back[1]+u[0]*5]} L${tip} L${[back[0]+u[1]*5,back[1]-u[0]*5]}`);}}}
   w.rings.forEach((ring,axis)=>{
    const text=(kind==='hand'?'Hand - '+(model.world?'world':'local')+' - L to switch':kind==='velocity'?'Velocity':kind==='forearm'?'Forearm - local':'Weapon grip - local')+' - '+['X','Y','Z'][axis]+(kind==='move'?' position':' rotation');ring.hit.setAttribute('aria-label',text);
    const normal=axes[axis],u=R.unit(R.cross(normal,Math.abs(normal[1])<.9?[0,1,0]:[1,0,0])),v=R.cross(normal,u);
    Object.assign(ring,{center:model.center.slice(),normal,u,v,radius,angles:model.angles.slice(),position:model.position?.slice(),world:!!model.world,base:model.base.slice()});
    const points=kind==='move'?[this.project(R.add(ring.center,R.mul(normal,radius*.15))),this.project(R.add(ring.center,R.mul(normal,radius)))]:Array.from({length:97},(_,i)=>this.project(this.point(ring,i*Math.PI/48)));ring.screenPoints=points;
    let d=points.every(Boolean)?'M'+points.map(p=>p.join(',')).join(' L')+(kind==='move'?'':' Z'):'';
    if(kind==='move'&&d){const [a,b]=points,dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(len>8){const x=dx/len,y=dy/len;d+=` M${b[0]-x*10-y*5},${b[1]-y*10+x*5} L${b} L${b[0]-x*10+y*5},${b[1]-y*10-x*5}`;}}
    ring.line.setAttribute('d',d);ring.hit.setAttribute('d',d);
    ring.line.classList.toggle('dragging',this.active?.kind===kind&&this.active?.axis===axis);
   });
  }
  const scale=models.scale,center=scale&&this.project(scale.center);
  if(center){
   const w=this.scaleWidget,axes=R.toAxes(scale.q),radius=R.dot(R.sub(scale.center,view.eye),view.forward)*135/view.focalCss;w.group.style.display='';w.value=scale.scale;
   w.handles.forEach((h,i)=>{const tip=this.project(R.add(scale.center,R.mul(axes[i],radius)));if(!tip)return;const dx=tip[0]-center[0],dy=tip[1]-center[1],length=Math.hypot(dx,dy);h.direction=length>1?[dx/length,dy/length]:[1,0];h.line.setAttribute('d',`M${center} L${tip}`);h.handle.setAttribute('x',tip[0]-6);h.handle.setAttribute('y',tip[1]-6);h.label.setAttribute('x',tip[0]+10);h.label.setAttribute('y',tip[1]+3);h.label.textContent=['X','Y','Z'][i]+' '+Math.round(scale.scale[i]*100)+'%';});
  }
  this.updateReadout();
 }
 pointer(e){const r=this.svg.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top];}
 pick(point){
  let best=null,distance=9;
  for(const [kind,w] of Object.entries(this.widgets)){if(w.group.style.display==='none')continue;w.rings.forEach((ring,axis)=>{const points=ring.screenPoints||[];for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];if(!a||!b)continue;const dx=b[0]-a[0],dy=b[1]-a[1],u=Math.max(0,Math.min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy||1))),d=Math.hypot(point[0]-a[0]-u*dx,point[1]-a[1]-u*dy);if(d<distance){distance=d;best={kind,axis};}}});}
  return best;
 }
 hover(pick){for(const [kind,w] of Object.entries(this.widgets))w.rings.forEach((ring,axis)=>ring.line.classList.toggle('hovered',pick?.kind===kind&&pick?.axis===axis));this.updateReadout(pick);}
 updateReadout(pick){
  const target=this.active||(pick===undefined&&this.pointerPosition?this.pick(this.pointerPosition):pick),w=this.readout;
  const model=target&&this.models?.[target.kind],point=this.pointerPosition;
  if(!point||!model||!['hand','forearm'].includes(target.kind)){w.group.style.display='none';return;}
  const normal=this.active?.ring?.normal||this.widgets[target.kind].rings[target.axis].normal,value=ThrowVanilla.axisOffsetDegrees(model.defaultQ,model.currentQ,normal),rounded=value===null?null:Math.round(value*10)/10;
  const formatted=rounded===null?'undefined':(rounded>0?'+':'')+(Object.is(rounded,-0)?0:rounded).toFixed(1)+'°';
  w.text.textContent=' · '+['X','Y','Z'][target.axis]+' '+formatted;w.text.setAttribute('fill',['#ff706b','#7de497','#70acff'][target.axis]);
  w.group.dataset.kind=target.kind;w.group.dataset.axis=target.axis;w.group.dataset.degrees=value===null?'':String(value);
  this.widgets[target.kind].label.append(w.text);w.group.style.display='';
 }
 planeVector(point,ring){const R=Recovery,dir=R.unit(R.add(this.view.forward,R.add(R.mul(this.view.right,(point[0]-this.width/2)/this.view.focalCss),R.mul(this.view.up,-(point[1]-this.height/2)/this.view.focalCss)))),den=R.dot(dir,ring.normal);if(Math.abs(den)<.15)return null;const t=R.dot(R.sub(ring.center,this.view.eye),ring.normal)/den;if(t<=0)return null;const v=R.sub(R.add(this.view.eye,R.mul(dir,t)),ring.center);return R.length(v)>1e-8?R.unit(v):null;}
 axisParameter(point,ring){
  const R=Recovery,ray=R.unit(R.add(this.view.forward,R.add(R.mul(this.view.right,(point[0]-this.width/2)/this.view.focalCss),R.mul(this.view.up,-(point[1]-this.height/2)/this.view.focalCss)))),c=R.dot(ray,ring.normal),den=1-c*c;
  if(den<.002)return null;const w=R.sub(this.view.eye,ring.center);return (R.dot(w,ring.normal)-c*R.dot(w,ray))/den;
 }
 down(e){
  this.pointerPosition=this.pointer(e);
  if(e.button!==0||this.active)return;const picked=this.pick(this.pointer(e));if(!picked)return;const {kind,axis}=picked;e.preventDefault();e.stopPropagation();this.callbacks.begin(kind);this.hover(picked);
  const ring=this.widgets[kind].rings[axis],point=this.pointer(e);let angle=0,best=Infinity;
  for(let i=0;i<192;i++){const a=i*Math.PI/96,p=this.project(this.point(ring,a));if(!p)continue;const d=Math.hypot(p[0]-point[0],p[1]-point[1]);if(d<best){best=d;angle=a;}}
  this.active={kind,axis,ring:{...ring},pointer:e.pointerId,point,startPoint:point.slice(),startParameter:this.axisParameter(point,ring),angle,total:0,previous:this.planeVector(point,ring),target:this.svg};
  this.svg.setPointerCapture(e.pointerId);this.widgets[kind].group.classList.add('dragging');
  this.updateReadout();
 }
 move(e){
  this.pointerPosition=this.pointer(e);
  const a=this.active;if(!a){this.hover(this.pick(this.pointer(e)));return;}if(a.pointer!==e.pointerId)return;e.preventDefault();e.stopPropagation();const R=Recovery,p=this.pointer(e);
  if(a.kind==='scale'){const delta=(p[0]-a.startPoint[0])*a.direction[0]+(p[1]-a.startPoint[1])*a.direction[1],value=a.scale.slice();value[a.axis]=Math.max(.1,Math.min(2,value[a.axis]*Math.exp(delta/120)));this.callbacks.change('scale',value);return;}
  if(a.kind==='move'){
   const next=this.axisParameter(p,a.ring);if(next===null||a.startParameter===null)return;
   a.total=next-a.startParameter;
   const local=R.rotate(R.qinv(a.ring.base),R.mul(a.ring.normal,a.total));
   this.callbacks.change('move',R.add(a.ring.position,local));return;
  }
  const next=this.planeVector(p,a.ring);let delta;
  if(next&&a.previous)delta=Math.atan2(R.dot(a.ring.normal,R.cross(a.previous,next)),R.dot(a.previous,next));
  else {const p0=this.project(this.point(a.ring,a.angle)),p1=this.project(this.point(a.ring,a.angle+.01));if(!p0||!p1)return;const tangent=[(p1[0]-p0[0])*100,(p1[1]-p0[1])*100],den=Math.max(24**2,tangent[0]**2+tangent[1]**2);delta=((p[0]-a.point[0])*tangent[0]+(p[1]-a.point[1])*tangent[1])/den;}
  // Scale each incremental rotation, keeping raw pointer geometry continuous
  // when Ctrl is pressed or released midway through a drag.
  a.total+=delta*(this.leftControl && e.ctrlKey ? .3 : 1);a.angle+=delta;a.point=p;a.previous=next;
  const angles=a.kind!=='velocity'?ThrowVanilla.rotateAxis(a.ring.base,a.ring.angles,a.ring.normal,a.total,a.lastAngles||a.ring.angles):a.ring.angles.slice();
  if(a.kind==='velocity')angles[a.axis]+=a.total*180/Math.PI;a.lastAngles=angles;this.callbacks.change(a.kind,angles);
 }
 finish(e){const a=this.active;if(!a||a.pointer!==e.pointerId)return;this.active=null;this.widgets[a.kind]?.group.classList.remove('dragging');if(a.target.hasPointerCapture(e.pointerId))a.target.releasePointerCapture(e.pointerId);this.callbacks.end();}
}
