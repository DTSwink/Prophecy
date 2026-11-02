'use strict';
// Constraints for a changed prospective stair course. The ordinary lab never
// enters this opt-in path. Existing material pins and the last accepted pose
// pair are boundary conditions, not targets to re-fit from future commands.
const R=require('../../Labs/FootIKLab/recovery.js');
const K=require('../../Labs/FootIKLab/footik.js');
const S=require('../../Labs/FootIKLab/support.js');
const {add,sub,mul,length,unit,cross,rotate,qinv}=R;
const copy=value=>structuredClone(value),clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function importFrame(model,index,input,names){
 if(!model?.checkpoint||!model.frames[index])throw Error('Applied Foot IK frame is outside the retained planner window');
 const frame=copy(input),pose=frame.pose,c=model.checkpoint;
 if(!pose||pose.points?.length!==26||pose.q?.length!==26||!pose.points.every(p=>p.length===3&&p.every(Number.isFinite))||!pose.q.every(q=>q.length===4&&q.every(Number.isFinite)))throw Error('Invalid applied Foot IK pose');
 pose.axes=pose.q.map(R.toAxes);frame.root=pose.points[0].slice();frame.raw??=c.base[index];
 const legs=['L','R'].map(side=>K.stableLeg(pose,names,side));
 frame.pelvisOffset??=pose.points[1][1]-c.base[index].points[1][1];
 frame.feet??=legs.map(l=>({side:l.side,state:'NN',target:pose.points[l.foot].slice(),contact:null,error:0,penetration:0}));
 if(frame.feet.length!==2)throw Error('Invalid applied Foot IK contact pair');
 c.legs[index]=legs;c.planned[index].pelvisOffset=frame.pelvisOffset;
 for(let side=0;side<2;side++){
  const leg=legs[side],p=c.plans[side],foot=frame.feet[side],rotation={footQ:pose.q[leg.foot],toeQ:pose.q[leg.toe]};
  p.targets[index]=pose.points[leg.foot].slice();p.contacts[index]=copy(foot.contact||null);p.states[index]=foot.state;
  p.rotations[index]=rotation;p.offsets[index]=K.geometry(pose,leg,rotation);
  c.planned[index].targets[side]=p.targets[index].slice();c.planned[index].planted[side]=!!foot.contact;
 }
 model.frames[index]=frame;return frame;
}
function create(model,through){
 if(!model?.checkpoint||through<1)return {capture:true};
 const old=model.checkpoint,frames=model.frames,frame=frames[through],previous=frames[through-1];
 const diagnostics={retainedPins:0,releasedPins:0,velocityConstraints:0,infeasibleVelocity:0,maxPinShiftM:0};
 function contacts(p){
  const original=old.plans[p.side],at=p.contacts[through],actual=frame.feet[p.side].contact;
  if(actual){
   if(at&&at.surface===actual.surface){
    // Anchor the recomputed heel/toe arc at its real material point. Its later
    // yaw and pivot transfers remain the canonical plan's own rigid motion.
    const delta=sub(original.contacts[through].point,at.point),id=at.stanceId;
    let end=through;while(end+1<p.contacts.length&&p.contacts[end+1]?.stanceId===id)end++;
    const leg=p.legs[through][p.side],tile=p.terrain.tiles.find(t=>t.id===actual.surface),f=S.footFrame(frame.pose,leg.foot,leg.toe,leg.side),axis=unit(cross([0,1,0],unit([f.forward[0],0,f.forward[2]])));
    const surface=tile.surface||S.rectangle(tile.id,[0,tile.y,0],[1,0,0],[0,0,1],[tile.x0,tile.x1,tile.z0,tile.z1],.1);
    const terminal={pose:frame.pose,foot:frame.pose.points[leg.foot],rotation:{footQ:frame.pose.q[leg.foot],toeQ:frame.pose.q[leg.toe]}};
    const positive=S.roll(terminal,{...leg,plant:{right:axis}},surface,140),negative=S.roll(terminal,{...leg,plant:{right:mul(axis,-1)}},surface,140);
    const join=Math.min(end,through+Math.ceil(.1*p.fps)),seconds=(join-through)/p.fps;
    const v0=(actual.angle-(previous.feet[p.side].contact?.angle??actual.angle))*p.fps;
    const angleEnd=(p.contacts[join]?.angle??at.angle)-at.angle,v1=join>through?(p.contacts[join].angle-p.contacts[join-1].angle)*p.fps:0;
    const yaw=K.createPinYaw([0,1,0],model.settings.footYawLimit);
    for(let i=through+1;i<=end;i++){
     const c=p.contacts[i];p.contacts[i]={...c,point:add(c.point,delta),local:add(c.local,delta)};p.targets[i]=add(p.targets[i],delta);
     if(seconds>0){
      const u=Math.min(1,(i-through)/(join-through)),e=u*u*(3-2*u);
      const angle=i<=join?angleEnd*e+seconds*(v0*u*(1-u)**2-v1*u*u*(1-u)):c.angle-at.angle;
      const rolled=(angle>=0?positive:negative)(Math.abs(angle)/140);
      const sample={...rolled,localPoint:rotate(qinv(rolled.rotation.footQ),sub(rolled.contact,rolled.foot))};sample.pivotKey=sample.localPoint.map(v=>Math.round(v*1e6)).join(',');
      const next=yaw(sample,p.base[i],p.legs[i][p.side],value=>p.terrain.floorFor(value.foot,K.geometry(p.raw[i],p.legs[i][p.side],value.rotation))<=value.foot[1]+1e-7);
      if(next.valid!==false){
       p.targets[i]=next.foot;p.rotations[i]=next.rotation;p.offsets[i]=K.geometry(p.raw[i],p.legs[i][p.side],next.rotation);
       p.contacts[i]={...p.contacts[i],point:next.contact,local:p.terrain.local?p.terrain.local(next.contact,tile):sub(next.contact,[0,tile.y,tile.z0]),localPoint:next.localPoint,pivotKey:next.pivotKey,angle:actual.angle+angle,yaw:next.yaw,yawError:next.yawError,pivotKind:next.pivotKind};
      }
     }
    }
    diagnostics.retainedPins++;
   }else diagnostics.releasedPins++;
  }
  for(let i=0;i<=Math.min(through,p.targets.length-1);i++)for(const key of ['targets','contacts','states','rotations','offsets','limits'])p[key][i]=copy(original[key][i]);
 }
 function trajectory(p){
  if(!p.weights.slice(through+1).some(value=>value>0))return;
  const count=p.planned.length,lo=Math.max(0,through-1),dt=1/p.fps,limit=p.settings.pelvis/100;
  // Preserve accepted pelvis height/velocity before planning the limbs. Fit a
  // new continuation inside the existing support legs' physical reach range.
  const reference=[],lower=[],upper=[],fixed=new Map();
  for(let i=lo;i<count;i++){
   reference.push(p.planned[i].pelvisOffset);let a=-limit,b=limit;
   for(let side=0;side<2;side++)if(p.planned[i].planted[side]){
    const leg=p.legs[i][side],target=p.planned[i].targets[side],hip=p.base[i].points[leg.hip],r=leg.reach*.995;
    const vertical=Math.sqrt(Math.max(0,r*r-(target[0]-hip[0])**2-(target[2]-hip[2])**2));
    a=Math.max(a,target[1]-hip[1]-vertical);b=Math.min(b,target[1]-hip[1]+vertical);
   }
   lower.push(Math.min(a,b));upper.push(b);
   if(i<=through)fixed.set(i-lo,old.planned[i].pelvisOffset);
  }
  if(through+1<count){
   const wanted=2*old.planned[through].pelvisOffset-old.planned[through-1].pelvisOffset,k=through+1-lo;
   fixed.set(k,clamp(wanted,lower[k],upper[k]));
  }
  const pelvis=p.clearanceCurve(reference,lower,fixed,(p.fps*.08)**4,upper);
  for(let i=lo;i<count;i++)p.planned[i].pelvisOffset=pelvis[i-lo];
  // Clear trajectory history is immutable. Only the prospective tail is fit;
  // the canonical corridor, shoe floor and leg reach remain hard constraints.
  for(let side=0;side<2;side++){
   for(let i=0;i<=through;i++){
    p.planned[i].targets[side]=frames[i].pose.points[p.legs[i][side].foot].slice();
    p.planned[i].planted[side]=!!frames[i].feet[side].contact;
   }
   const current=frame.pose.points[p.legs[through][side].foot],prev=previous.pose.points[p.legs[through-1][side].foot],velocity=mul(sub(current,prev),1/dt);
   for(let pass=0;pass<2;pass++)for(const axis of [0,2,1]){
    const values=[],floor=[],ceiling=[],fixed=new Map();
    for(let i=lo;i<count;i++){
     const planned=p.planned[i],target=planned.targets[side],leg=p.legs[i][side],hip=add(p.base[i].points[leg.hip],[0,planned.pelvisOffset,0]);
     const reach=planned.reaches?.[side]??leg.reach*.995;
     let r2=reach*reach;for(let j=0;j<3;j++)if(j!==axis)r2-=(target[j]-hip[j])**2;
     const r=Math.sqrt(Math.max(0,r2));let a=hip[axis]-r,b=hip[axis]+r;
     if(axis===1)a=Math.max(a,p.terrain.floorFor(target,p.plans[side].offsets[i]));
     values.push(target[axis]);floor.push(Math.min(a,b));ceiling.push(b);
     if(i<=through||planned.planted[side])fixed.set(i-lo,target[axis]);
    }
    if(through+1<count&&!p.planned[through+1].planted[side]){
     const k=through+1-lo,wanted=current[axis]+velocity[axis]*dt;
     if(wanted>=floor[k]-1e-8&&wanted<=ceiling[k]+1e-8){fixed.set(k,wanted);diagnostics.velocityConstraints++;}
     else diagnostics.infeasibleVelocity++;
    }
    const curve=p.clearanceCurve(values,floor,fixed,(p.fps*.06)**4,ceiling);
    for(let i=through+1;i<count;i++)if(!p.planned[i].planted[side])p.planned[i].targets[side][axis]=curve[i-lo];
   }
  }
 }
 return {capture:true,contacts,trajectory,diagnostics};
}
module.exports={create,importFrame};
