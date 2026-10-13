// Read-only counterpart of Unreal's VisualizeSheathingLeeway. UE cm/axes.
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const H=typeof module!=='undefined'?require('./holster.js'):root.Holster;
const {add,sub,mul,dot,cross,unit,rotate,fromTo,length}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),deg=180/Math.PI;
const colors={cyan:[70,220,255],green:[90,255,110],red:[255,75,70],amber:[255,195,65],gray:[100,110,125]};
function sample(model,frame){
 if(!model.o.sheathe||!['Reach','Align tip'].includes(frame.phase))return null;
 const full=H.seatedSword(model.setup,frame.holster),blade=frame.sword;
 const mouth=H.point(full,model.setup.baseBladeLocal),tip=H.point(blade,model.tip);
 const localAxis=unit(sub(model.setup.baseBladeLocal,model.tip));
 // FVector::FindBestAxisVectors: same zero-roll reference as the UE dial.
 const seed=Math.abs(localAxis[2])>Math.abs(localAxis[0])&&Math.abs(localAxis[2])>Math.abs(localAxis[1])?[1,0,0]:[0,0,1];
 const localU=unit(sub(seed,mul(localAxis,dot(seed,localAxis))));
 const axis=rotate(full.q,localAxis),u=rotate(full.q,localU),v=cross(axis,u),actualAxis=rotate(blade.q,localAxis);
 const limit=model.o.sheatheRotationTolerance,error=H.angle(blade.q,full.q),tipError=length(sub(tip,mouth));
 const rotationOK=error<=limit+1e-5,tipLimit=model.o.leewayPhase?2:model.o.sheatheTipTolerance,tipOK=tipError<=tipLimit,bodyOK=(frame.body?.remainingDegrees??0)<=1e-5;
 const rotationColor=rotationOK?colors.green:colors.red,tipColor=tipOK?colors.green:colors.amber;
 const radians=limit/deg,tilt=Math.acos(clamp(dot(axis,actualAxis),-1,1));
 const dialU=rotate(fromTo(axis,actualAxis),u),dialV=cross(actualAxis,dialU),actualU=rotate(blade.q,localU);
 const roll=Math.atan2(dot(actualU,dialV),dot(actualU,dialU));
 const rollBudget=tilt<=radians?2*Math.acos(clamp(Math.cos(radians/2)/Math.max(1e-8,Math.cos(tilt/2)),0,1)):0;
 const lines=[],line=(a,b,color,width=1)=>lines.push({a,b,color,width}),size=40,radius=size*.18;
 const coneColor=rotationOK?colors.green:colors.cyan;
 const rim=t=>add(mouth,mul(add(mul(axis,Math.cos(radians)),mul(add(mul(u,Math.cos(t)),mul(v,Math.sin(t))),Math.sin(radians))),size));
 for(let i=0;i<48;i++)line(rim(2*Math.PI*i/48),rim(2*Math.PI*(i+1)/48),coneColor);
 for(let i=0;i<4;i++)line(mouth,rim(Math.PI*i/2),coneColor);
 line(mouth,add(mouth,mul(axis,size)),colors.cyan);
 line(mouth,add(mouth,mul(actualAxis,size)),rotationColor,2.5);
 // Three great circles make the configured tip gate legible from every view.
 for(let j=0;j<3;j++)for(let i=0;i<32;i++){
  const point=t=>{const p=[...mouth];p[(j+1)%3]+=tipLimit*Math.cos(t);p[(j+2)%3]+=tipLimit*Math.sin(t);return p;};
  line(point(2*Math.PI*i/32),point(2*Math.PI*(i+1)/32),tipColor);
 }
 line(tip,mouth,tipColor,1.5);
 const dial=add(add(mouth,mul(axis,size*.7)),mul(u,size*.75));
 const circle=t=>add(dial,mul(add(mul(dialU,Math.cos(t)),mul(dialV,Math.sin(t))),radius));
 for(let i=0;i<48;i++)line(circle(2*Math.PI*i/48),circle(2*Math.PI*(i+1)/48),colors.gray);
 if(rollBudget>0)for(let i=0;i<24;i++)line(circle(-rollBudget+2*rollBudget*i/24),circle(-rollBudget+2*rollBudget*(i+1)/24),colors.cyan,3);
 line(dial,circle(0),colors.cyan);line(dial,circle(roll),rotationColor,2.5);
 return {lines,tip,tipColor,error,limit,tipError,tipLimit,roll:roll*deg,rollBudget:rollBudget*deg,rotationOK,tipOK,bodyOK,ready:rotationOK&&tipOK&&bodyOK};
}
const api={sample,colors};if(typeof module!=='undefined')module.exports=api;else root.HolsterLeeway=api;
})(globalThis);
