/* Camera coordinates are world-space in free mode, COM-relative in follow mode. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,unit,length}=R;
const vector=v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite);
function basis(eye,target,height){
 const forward=unit(sub(target,eye));let right=unit(cross(forward,[0,1,0]));if(length(right)<1e-6)right=[1,0,0];
 return {eye,target,forward,right,up:unit(cross(right,forward)),targetDepth:Math.max(.01,length(sub(target,eye))),focalCss:(height*.5)/Math.tan(Math.PI/8)};
}
function view(state,center,height){
 if(state.free&&state.freeView){const v=state.freeView;return basis(v.eye,add(v.eye,mul(v.forward,v.distance)),height);}
 const distance=3.55/state.zoom,target=add(center,state.offset||[0,0,0]),eye=add(target,[Math.sin(state.yaw)*distance,distance*(.27-state.pitch*.55),Math.cos(state.yaw)*distance]);
 const b=basis(eye,target,height),scale=b.targetDepth/b.focalCss,shift=add(mul(b.right,-state.panX*scale),mul(b.up,state.panY*scale));
 return {...b,eye:add(eye,shift),target:add(target,shift)};
}
function toggle(state,enabled,current,center){
 if(enabled){state.freeView={eye:current.eye.slice(),forward:current.forward.slice(),distance:length(sub(current.target,current.eye))};state.free=true;}
 else {
  const delta=sub(current.eye,current.target),horizontal=Math.max(1e-9,Math.hypot(delta[0],delta[2]));
  Object.assign(state,{free:false,freeView:null,yaw:Math.atan2(delta[0],delta[2]),pitch:(.27-delta[1]/horizontal)/.55,zoom:3.55/horizontal,panX:0,panY:0,offset:null});
 }
}
function rotate(state,dx,dy){
 if(!state.free){
  // Saved pitch is a slope. Orbit in angle space, preserving viewing distance.
  const slope=.27-state.pitch*.55,radius=3.55/state.zoom*Math.hypot(1,slope);
  const elevation=Math.max(-Math.PI/2+.001,Math.min(Math.PI/2-.001,Math.atan(slope)+dy*.0033));
  state.yaw-=dx*.008;state.pitch=(.27-Math.tan(elevation))/.55;
  state.zoom=3.55/(radius*Math.cos(elevation));return;
 }
 const v=state.freeView,f=v.forward,yaw=Math.atan2(-f[0],-f[2])-dx*.008;
 const pitch=Math.max(-Math.PI/2+.001,Math.min(Math.PI/2-.001,Math.asin(Math.max(-1,Math.min(1,f[1])))-dy*.006)),c=Math.cos(pitch);
 v.forward=[-Math.sin(yaw)*c,Math.sin(pitch),-Math.cos(yaw)*c];
}
function pan(state,current,dx,dy){
 if(!state.free){state.panX+=dx;state.panY+=dy;return;}
 const shift=add(mul(current.right,-dx*current.targetDepth/current.focalCss),mul(current.up,dy*current.targetDepth/current.focalCss));
 state.freeView.eye=add(state.freeView.eye,shift);
}
function wheel(state,delta){
 const limit=state.free?state.zoom*state.freeView.distance/(3.55/3):3*Math.hypot(1,.27-state.pitch*.55);
 const zoom=Math.min(Math.max(limit,state.zoom),state.zoom*Math.exp(-delta*.001));
 if(!(zoom>0&&Number.isFinite(3.55/zoom)))return;
 if(state.free){const v=state.freeView,distance=v.distance*state.zoom/zoom;if(!Number.isFinite(distance))return;v.eye=add(v.eye,mul(v.forward,v.distance-distance));v.distance=distance;}
 state.zoom=zoom;
}
function move(state,keys,seconds){
 if(!state.free||!keys.size)return;
 const v=state.freeView,right=unit(cross(v.forward,[0,1,0]));
 const direction=add(mul(v.forward,Number(keys.has('z'))-Number(keys.has('s'))),mul(right,Number(keys.has('d'))-Number(keys.has('q'))));
 v.eye=add(v.eye,mul(unit(direction),3*seconds));
}
function restore(state,saved,defaults){
 Object.assign(state,defaults);
 if(!saved)return;
 for(const k of ['yaw','pitch','zoom','panX','panY'])if(Number.isFinite(saved[k])&&(k!=='zoom'||saved[k]>0))state[k]=saved[k];
 if(vector(saved.offset))state.offset=saved.offset.slice();
 const v=saved.freeView;
 if(saved.free===true&&v&&vector(v.eye)&&vector(v.forward)&&length(v.forward)>.001&&Number.isFinite(v.distance)&&v.distance>.001){state.free=true;state.freeView={eye:v.eye.slice(),forward:unit(v.forward),distance:v.distance};}
}
const api={view,toggle,rotate,pan,wheel,move,restore};if(typeof module!=='undefined')module.exports=api;else root.BodyflipCamera=api;
})(globalThis);
