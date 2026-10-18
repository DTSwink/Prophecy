// Lab port of ProphecyReachLibrary: BuildFingers, GrabTarget, clearance,
// FingerFK/FingerContact/FitFingers and closure/acquisition gates. Units: cm.
// The lab's held ball is a kinematic fixed attachment, not a Jolt simulation.
(function(root){
'use strict';
const R=root.Recovery,{add,sub,mul,dot,cross,unit,length,rotate,qm,qinv,qslerp,fromAxes}=R;
const P=t=>t.slice(0,3),Q=t=>t.slice(3),identity=[0,0,0,1];
const compose=(a,b)=>[...add(P(a),rotate(Q(a),P(b))),...unit(qm(Q(a),Q(b)))];
const relative=(a,b)=>[...rotate(qinv(Q(b)),sub(P(a),P(b))),...unit(qm(qinv(Q(b)),Q(a)))];
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(dot(a,b))))*180/Math.PI;
const xz=(x,z)=>{x=unit(x);const y=unit(cross(z,x));return fromAxes([x,y,cross(x,y)]);};
function build(data,side){
 const suffix=side===0?'l':'r',hand='hand_'+suffix,bones=data.bones;
 const converted=n=>compose(bones[n].closed,relative(bones[n].mesh,bones[n].reference));
 const fingers=[];
 for(const finger of ['thumb','index','middle','ring','pinky'])for(let j=1;j<=3;j++){
  const name=finger+'_'+String(j).padStart(2,'0')+'_'+suffix,b=bones[name],parent=j===1?hand:b.parent;
  const open=relative(b.mesh,bones[parent].mesh),closed=relative(converted(name),converted(parent));
  fingers.push({name,parent:j===1?-1:fingers.length-1,open,closed:[...P(open),...Q(closed)]});
 }
 const normal=side===0?[0,-1,0]:[0,1,0],palm=add(mul(P(fingers[6].open),.5),mul(normal,1.2));
 return {fingers,palm,normal,forward:unit(P(fingers[6].open))};
}
function fk(model,g,wrist,alpha=g.close){
 const out=[];
 model.fingers.forEach((b,i)=>out.push(compose(b.parent<0?wrist:out[b.parent],[...P(b.open),...qslerp(Q(b.open),Q(b.closed),g.curl[i]*alpha)])));
 return out;
}
function segments(model,g,wrist,alpha=g.close){
 const poses=fk(model,g,wrist,alpha);
 return poses.map((b,i)=>({a:P(b),b:i%3<2?P(poses[i+1]):add(P(b),rotate(Q(b),mul(unit(P(model.fingers[i].open)),2))),finger:Math.floor(i/3)}));
}
function contact(model,g,wrist,center,radius,finger,first){
 const lines=segments(model,g,wrist,1);
 for(let j=first;j<3;j++){
  const s=lines[finger*3+j];
  for(let k=0;k<=4;k++)if(length(sub(add(mul(s.a,1-k*.25),mul(s.b,k*.25)),center))-radius<.65)return true;
 }
 return false;
}
function target(g,center){return [...sub(add(center,mul(g.normal,g.radius+.35)),rotate(g.rotation,g.palm)),...g.rotation];}
function fresh(center){return {active:false,gripped:false,close:0,curl:Array(15).fill(0),contacts:0,ball:[...center,...identity],returnTick:0,returnClose:0};}
function start(model,h,wrist,desired,upperArmPosition){
 const g=fresh(h.target);g.active=true;g.radius=h.radius;g.key=key(h);g.fitted=false;g.fitCount=0;
 if(h.orientation==='surface'){
  // Capture the same-side upper-arm bone origin once, not the moving palm.
  g.normal=unit(sub(upperArmPosition,h.target));
  if(length(g.normal)<1e-8)g.normal=[0,-1,0];
  let forward=sub([0,0,1],mul(g.normal,g.normal[2]));
  if(length(forward)<1e-6)forward=sub([0,1,0],mul(g.normal,g.normal[1]));
  g.rotation=unit(qm(xz(forward,mul(g.normal,-1)),qinv(xz(model.forward,model.normal))));
 }else{
  g.rotation=desired;g.normal=mul(rotate(desired,model.normal),-1);
 }
 g.palm=[...model.palm];const outward=rotate(qinv(g.rotation),g.normal);
 const clear=offset=>{g.palm=sub(model.palm,mul(outward,offset));const t=target(g,h.target);return [0,1,2,3,4].every(f=>!contact(model,g,t,h.target,h.radius,f,0));};
 g.clearance=0;
 if(!clear(0)){
  let lo=0,hi=4;
  if(!clear(hi)){g.error='Open fingers intersect ball';g.palm=[...model.palm];return g;}
  for(let i=0;i<8;i++){const mid=(lo+hi)*.5;if(clear(mid))hi=mid;else lo=mid;}
  clear(hi);g.clearance=hi;
 }
 const wristTarget=target(g,h.target);
 for(let f=0;f<5;f++){
  let touched=false;
  for(let j=0;j<3;j++){
   const i=f*3+j;let lo=0,hi=1;
   for(let step=1;step<=12;step++){g.curl[i]=step/12;if(contact(model,g,wristTarget,h.target,h.radius,f,j)){hi=g.curl[i];touched=true;break;}lo=g.curl[i];}
   if(lo<1)for(let step=0;step<6;step++){g.curl[i]=(lo+hi)*.5;if(contact(model,g,wristTarget,h.target,h.radius,f,j))hi=g.curl[i];else lo=g.curl[i];}
   g.curl[i]=lo;
  }
  g.contacts+=Number(touched);
 }
 g.fitted=true;g.fitCount=1;return g;
}
// Translation is deliberately absent: move an object without refitting fingers.
function key(h){return JSON.stringify([h.radius,h.orientation,h.orientation==='surface'?'upperarm-v1':h.rotation]);}
// Requested-frame attachment retained only for the historical feedback experiment.
// Ordinary grips again capture the achieved wrist, matching the restored native path.
function attachment(ball,wanted){return relative(ball,wanted);}
// Optional lab experiment: close the fixed-joint/observed-target feedback loop.
// This is rigid transform closure, not a Jolt force/collision simulation.
function feedback(g,h){
 if(!g?.active||!g.feedback)return;
 const f=g.feedback;
 if(f.lastCenter){const delta=sub(h.target,f.lastCenter);if(f.legacy)g.ball=[...add(P(g.ball),delta),...Q(g.ball)];f.offset=add(f.offset||[0,0,0],delta);}
 // After acquisition the authored hold remains the input. Physics/attachment
 // output must not replace it; dragging the lab target still edits that input.
 if(!f.legacy){f.lastCenter=[...h.target];return;}
 const wanted=compose(g.ball,f.goal);
 g.rotation=Q(wanted);g.normal=rotate(Q(g.ball),f.normal);
 h.target=P(g.ball);f.lastCenter=[...h.target];
}
function update(g,h,wrist,tolerance){
 if(!g.active)return;
 const wanted=target(g,h.target);g.distance=length(sub(P(wrist),P(wanted)));g.angle=angle(Q(wrist),Q(wanted));
 if(!g.gripped)g.ball=[...h.target,...identity];
 if(g.error)return;
 if(g.distance<3&&g.angle<=tolerance.closure)g.close=Math.min(1,g.close+1/12);
 // Commanded and actual hand coincide in this kinematic lab. Same native gates.
 if(!g.gripped&&g.close>=1-1e-12&&g.distance<1.25&&g.angle<=tolerance.grip&&g.distance<2){
  g.close=1;g.gripped=true;g.attachment=g.feedback&&!g.feedback.legacy?attachment(g.ball,wanted):relative(g.ball,wrist);
 }
 if(g.gripped)g.ball=compose(wrist,g.attachment);
}
function release(g){g.active=false;g.gripped=false;g.returnTick=0;g.returnClose=g.close;g.attachment=null;}
function returnStep(g){if(g.returnClose>0){g.returnTick++;g.close=g.returnClose*Math.max(0,1-g.returnTick/15);if(g.returnTick>=15)g.returnClose=0;}}
root.ReachGrab={build,fk,segments,contact,target,fresh,start,key,update,release,returnStep,compose,relative,attachment,feedback};
})(typeof globalThis!=='undefined'?globalThis:this);
