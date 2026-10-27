/* Marker editing is independent of playback and plans only on edits. */
'use strict';
class JumpTrack {
 constructor(api){
  this.api=api;this.selected=null;this.open=false;this.drag=null;this.timer=null;this.pending=null;this.serial=0;
  const el=id=>document.getElementById(id);this.el=el;
  this.fields={jumpPercent:'jumpPercent',jumpAttack:'attack',jumpAttackDelay:'attackDelay',jumpAttackIn:'attackIn',jumpAttackOut:'attackOut',jumpFlip:'flip',jumpTwist:'twist',jumpDelay:'turnDelay',jumpDuration:'turnDuration',jumpTurnIn:'turnIn',jumpTurnOut:'turnOut',jumpPoseIn:'poseIn',jumpPoseHold:'poseHold',jumpPoseOut:'poseOut',jumpAxis:'turnAxis',jumpPose:'pose'};
  for(const [id,key] of Object.entries(this.fields))el(id).onchange=()=>{
   const value=el(id).value;
   if(key==='pose'||key==='attack')this.change({[key]:value});
   else if(key==='turnAxis')this.change({[key]:value===''?null:+value});
   else if(value.trim()&&Number.isFinite(+value))this.change({[key]:+value});
   this.sync();
  };
  Object.entries(BodyflipJumpAttack.labels).forEach(([value,label])=>{const option=document.createElement('option');option.value=value;option.textContent=label;el('jumpAttack').append(option);});
  BodyflipCore.dirs.forEach((name,index)=>{const option=document.createElement('option');option.value=String(index);option.textContent=name;el('jumpAxis').append(option);});
  el('jumpHere').onclick=()=>this.add(api.get().time);
  el('jumpRemove').onclick=()=>this.commit(api.get().events.filter(e=>e.id!==this.selected));
  el('jumpTime').onchange=()=>{const value=el('jumpTime').value;if(value.trim()&&Number.isFinite(+value))this.change({time:+value});else {el('jumpTime').value=api.get().events.find(e=>e.id===this.selected)?.time.toFixed(3)||'';}};
  document.addEventListener('pointerdown',e=>{if(!el('jumpEditor').contains(e.target)&&e.target!==el('jumpHere')){if(!el('minorOptions').contains(e.target))this.commitFocused();this.open=false;this.sync();}});
  document.addEventListener('keydown',e=>{if(e.code==='Escape')this.close();});
  el('jumpLane').onpointerdown=e=>{
   if(e.button!==0)return;const marker=e.target.closest('.jump-marker');
   if(!marker)return;
   e.preventDefault();this.commitFocused();this.selected=marker.dataset.id;this.open=true;
   this.drag={id:this.selected,startX:e.clientX,startTime:api.get().events.find(x=>x.id===this.selected).time,max:api.get().max,width:el('jumpLane').getBoundingClientRect().width};
   el('jumpLane').setPointerCapture(e.pointerId);this.sync();
  };
  el('jumpLane').onpointermove=e=>{
   if(!this.drag)return;const d=this.drag,time=Math.round(Math.max(0,Math.min(600,d.startTime+(e.clientX-d.startX)*d.max/d.width))*60)/60;
   this.pending=api.get().events.map(x=>x.id===d.id?{...x,time}:x).sort((a,b)=>a.time-b.time);
   this.sync();clearTimeout(this.timer);this.timer=setTimeout(()=>this.flush(),100);
  };
  const end=()=>{if(!this.drag)return;this.drag=null;this.flush();};
  el('jumpLane').onpointerup=end;el('jumpLane').onpointercancel=end;el('jumpLane').onlostpointercapture=end;
 }
 commitFocused(){const focused=document.activeElement;if(focused===this.el('jumpTime')||Object.keys(this.fields).some(id=>focused===this.el(id))){focused.onchange?.();focused.blur?.();}}
 close(){this.commitFocused();this.open=false;this.sync();}
 flush(){clearTimeout(this.timer);this.timer=null;if(this.pending){const events=this.pending;this.pending=null;this.commit(events);}}
 commit(events){this.api.edit(events);this.sync();}
 add(time){this.commitFocused();const events=this.api.get().events;if(events.length>=32)return;time=Math.round(Math.max(0,Math.min(600,time))*60)/60;this.selected='m'+Date.now().toString(36)+'_'+this.serial++;this.open=true;this.commit([...events,{id:this.selected,time,surface:'auto'}].sort((a,b)=>a.time-b.time));}
 change(update){const events=this.api.get().events,selected=events.find(e=>e.id===this.selected);if(!selected)return;const values={...BodyflipCore.jumpDefaults,...selected};if(Object.entries(update).every(([key,value])=>values[key]===value))return;this.commit(events.map(e=>e.id===this.selected?{...e,...update}:e));}
 sync(){
  const {settings,events:stored,results,time,max}=this.api.get(),events=this.pending||stored,el=this.el;
  this.max=max;
  el('jumpEditor').hidden=el('jumpHere').hidden=false;
  if(!events.some(e=>e.id===this.selected))this.selected=null;
  const selected=events.find(e=>e.id===this.selected),index=events.indexOf(selected),result=results.find(e=>e.id===this.selected);
  el('jumpHere').disabled=events.length>=32;el('jumpPopover').hidden=!selected||!this.open;
  for(const id of ['jumpTime','jumpRemove'])el(id).disabled=!selected;
  if(document.activeElement!==el('jumpTime'))el('jumpTime').value=selected?selected.time.toFixed(3):'';
  const motion=BodyflipCore.sanitizeJump(selected);
  for(const [id,key] of Object.entries(this.fields)){
   el(id).disabled=!selected||(key.startsWith('attack')&&key!=='attack'&&motion.attack==='none')||(key.startsWith('pose')&&key!=='pose'&&motion.pose==='none');
   if(document.activeElement!==el(id))el(id).value=motion[key]===null?'':String(motion[key]);
  }
  el('jumpPoseTiming').setAttribute('aria-disabled',String(motion.pose==='none'));
  el('jumpOptionsLabel').textContent=selected?'J'+(index+1)+' · Flip / pose':'Flip / pose · Select a jump marker';
  el('jumpLabel').textContent=selected?'J'+(index+1):'—';
  el('jumpStatus').textContent=result?(result.status==='Push'?'Push '+result.pushTime.toFixed(3)+' s · '+result.surfaceId:result.status+' · '+result.reason):events.length?'Preparing…':'No jumps · run off ledge';
  el('jumpStatus').dataset.status=result?.status||'';
  const lane=el('jumpMarkers'),existing=new Map([...lane.children].map(x=>[x.dataset.id,x]));
  events.forEach((event,i)=>{
   let b=existing.get(event.id);if(b)existing.delete(event.id);else{b=document.createElement('button');b.className='jump-marker';b.dataset.id=event.id;lane.append(b);b.onclick=()=>{this.commitFocused();this.selected=event.id;this.open=true;this.sync();};}
   const r=results.find(e=>e.id===event.id);b.textContent=String(i+1);b.style.left=(100*event.time/max)+'%';b.classList.toggle('selected',event.id===this.selected);b.dataset.status=r?.status||'';
   b.title='Jump '+(i+1)+(settings.mode==='spaceGym'?' · start ':' · support ')+event.time.toFixed(3)+' s · '+(r?.status==='Push'?'push '+r.pushTime.toFixed(3)+' s on '+r.surfaceId:r?.reason||event.surface);b.setAttribute('aria-label',b.title);b.setAttribute('aria-pressed',String(event.id===this.selected));
  });
  for(const b of existing.values())b.remove();
  if(selected){const width=el('jumpPopover').getBoundingClientRect().width,left=el('jumpLane').offsetLeft+el('jumpLane').clientWidth*selected.time/max-width/2;el('jumpPopover').style.left=Math.max(0,Math.min(Math.max(0,el('jumpEditor').clientWidth-width),left))+'px';}
 }
}
