'use strict';

const $=id=>document.getElementById(id),R=Recovery,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),posAt=(d,j)=>d.points[j],axisAt=(d,j,a)=>d.axes[j][a];

let names=[],parents=[],nameToIndex=new Map(),swordMesh=null;

const cameraDefault={yaw:.45,pitch:-.12,zoom:1.25,panX:0,panY:0},cameraState={...cameraDefault};

let resetDefaults,dataset,phat,pose,solverState=Array(20).fill(0),ticks=0,playing=true,pending=false,accum=0,last=0,revision=0,ready=false,solveMs=0;

let armLengths,armLocalLower,coupledMs=0,coupledEnabled=true;
let referenceBase,checkpointBase=null;
let scenarioMotion=null;
function setBasePose(base){
 checkpointBase=base?copy(base):null;dataset.base=copy(base||referenceBase);
 armLengths=arms.map(a=>[norm(sub(dataset.base[a[2]].slice(0,3),dataset.base[a[1]].slice(0,3))),norm(sub(dataset.base[a[3]].slice(0,3),dataset.base[a[2]].slice(0,3)))]);
 armLocalLower=arms.map(a=>R.rotate(R.qinv(dataset.base[a[2]].slice(3)),sub(dataset.base[a[3]].slice(0,3),dataset.base[a[2]].slice(0,3))));
}
function advanceScenario(){
 if(!scenarioMotion)return;
 const index=ticks+1-scenarioMotion.startTick,frames=scenarioMotion.frames;
 if(index<1||index>=frames.length)return;
 const before=frames[index-1],next=frames[index];setBasePose(next.basePose);
 for(let k=0;k<2;k++){
  const h=settings.hands[k],g=grabs[k],a=before.targets[k],b=next.targets[k],oldKey=ReachGrab.key(h);
  h.target=add(h.target,sub(b.center,a.center));
  const delta=R.qm(b.rotation,R.qinv(a.rotation));
  h.rotation=rotationDegrees(R.qm(delta,rotationQ(h.rotation)));
  if(g?.active&&g.key===oldKey){g.rotation=normalize(R.qm(delta,g.rotation));g.normal=R.rotate(R.fromTo(a.normal,b.normal),g.normal);g.key=ReachGrab.key(h);}
 }
}
let fingerData,fingerModels,grabs=[null,null];

let handQ=[],returns=[null,null],wholeReturn=null,drag=null,saveTimer,lastView=0,settings;

const copy=x=>JSON.parse(JSON.stringify(x)),angle=(a,b)=>2*Math.acos(clamp(Math.abs(dot(a,b)),0,1))*180/Math.PI;

const toDisplay=p=>[p[0]*.01,p[2]*.01,p[1]*.01],fromDisplay=p=>[p[0]*100,p[2]*100,p[1]*100];

const axes=q=>[[1,0,0],[0,1,0],[0,0,1]].map((v,k)=>{const a=R.rotate(q,v);return [a[0],a[2],a[1]].map(x=>k===1?-x:x)});

const hands=[13,17],arms=[[10,11,12,13],[14,15,16,17]];

// Absolute lab-axis Euler angles: q = qZ * qY * qX. No idle-hand offset.

function rotationQ(degrees){const r=degrees.map(v=>v*Math.PI/180);return normalize(R.qm(R.qm(R.qexp([0,0,r[2]]),R.qexp([0,r[1],0])),R.qexp([r[0],0,0])));}

function rotationDegrees(q){

 const [x,y,z,w]=normalize(q),sinY=clamp(2*(w*y-z*x),-1,1);

 // At the Euler singularity choose roll=0 while preserving the orientation.

 const locked=Math.abs(sinY)>1-1e-12;

 const pitch=locked?Math.sign(sinY)*Math.PI/2:Math.asin(sinY);

 const roll=locked?0:Math.atan2(2*(w*x+y*z),1-2*(x*x+y*y));

 const yaw=locked?Math.atan2(2*(w*z-x*y),1-2*(x*x+z*z)):Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z));

 return [roll,pitch,yaw].map(v=>v*180/Math.PI);

}

function defaults(){return {schema:2,resetDefaults:copy(resetDefaults),hands:[0,1].map((k)=>({enabled:true,target:copy(resetDefaults.hands[k].target),rotation:copy(resetDefaults.hands[k].rotation),orientation:'target',grab:true,radius:3,speed:120,rotationSpeed:180})),phat:true,closure:8,grip:6,syncRotation:0,elbowDownBlend:1};}

function sanitize(s){const d=defaults();for(let k=0;k<2;k++){const h=s.hands?.[k];if(!h)continue;d.hands[k].enabled=typeof h.enabled==='boolean'?h.enabled:true;for(const field of ['target','rotation'])if(Array.isArray(h[field])&&h[field].length===3&&h[field].every(Number.isFinite))d.hands[k][field]=h[field].map(v=>clamp(v,field==='target'?-300:-180,field==='target'?300:180));if((s.schema??1)<2){const old=Array.isArray(h.rotation)&&h.rotation.length===3&&h.rotation.every(Number.isFinite)?h.rotation.map(v=>clamp(v,-180,180)):[0,0,0];d.hands[k].rotation=rotationDegrees(R.qm(rotationQ(old),dataset.base[hands[k]].slice(3)));}for(const field of ['speed','rotationSpeed'])if(Number.isFinite(h[field]))d.hands[k][field]=clamp(h[field],1,1000);d.hands[k].orientation=['natural','surface'].includes(h.orientation)?h.orientation:'target';d.hands[k].grab=h.grab!==false;d.hands[k].radius=Number.isFinite(h.radius)?clamp(h.radius,.5,15):3;if(d.hands[k].grab&&d.hands[k].orientation==='natural')d.hands[k].orientation='surface';}for(const key of ['closure','grip'])if(Number.isFinite(s[key]))d[key]=clamp(s[key],0,180);d.phat=s.phat!==false;if(Number.isFinite(s.syncRotation))d.syncRotation=clamp(s.syncRotation,0,1);if(Number.isFinite(s.elbowDownBlend))d.elbowDownBlend=clamp(s.elbowDownBlend,0,1);return d;}

async function post(path,data){const res=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json',...(desktopToken?{'X-Desktop-Session':desktopToken,'X-Client-Id':clientId}:{})},body:JSON.stringify(data)});const out=await res.json();if(!res.ok)throw Error(out.error||res.status);return out;}

function message(s){$('message').textContent=s;}

function persist(){if(!desktopToken)return;clearTimeout(saveTimer);saveTimer=setTimeout(()=>saveSettings().then(()=>message('Lab settings saved')).catch(showError),250);}

function localPose(p){return p.map((b,j)=>{const k=parents[j];return k<0?copy(b):[...R.rotate(R.qinv(p[k].slice(3)),sub(b.slice(0,3),p[k].slice(0,3))),...R.qm(R.qinv(p[k].slice(3)),b.slice(3))];});}

function blendLocal(out,from,target,ids,t){const dest=localPose(target),a=t*t*(3-2*t);for(const j of ids){const p=add(mul(from[j].slice(0,3),1-a),mul(dest[j].slice(0,3),a)),q=R.qslerp(from[j].slice(3),dest[j].slice(3),a),parent=parents[j];out[j]=parent<0?[...p,...q]:[...add(out[parent].slice(0,3),R.rotate(out[parent].slice(3),p)),...R.qm(out[parent].slice(3),q)];}}

function order(){const ids=[],visit=j=>{if(ids.includes(j))return;if(parents[j]>=0)visit(parents[j]);ids.push(j);};names.forEach((_,j)=>visit(j));return ids;}

function prepareGrabs(){for(let k=0;k<2;k++){const h=settings.hands[k];if(h.enabled&&h.grab){if(!grabs[k]?.active||grabs[k].key!==ReachGrab.key(h))grabs[k]=ReachGrab.start(fingerModels[k],h,pose[hands[k]],h.orientation==='natural'?pose[hands[k]].slice(3):rotationQ(h.rotation),pose[arms[k][1]].slice(0,3));}else if(grabs[k]?.active)ReachGrab.release(grabs[k]);}}

function wristTarget(k){const h=settings.hands[k],g=grabs[k];return h.grab&&g?.active?ReachGrab.target(g,h.target):[...h.target,...targetQ(k,pose)];}

function ballPoint(k){const g=grabs[k];return g?.gripped?g.ball.slice(0,3):settings.hands[k].target;}

function targetQ(k,raw){if(settings.hands[k].grab&&grabs[k]?.active)return grabs[k].rotation;if(settings.hands[k].orientation==='natural')return raw[hands[k]].slice(3);return rotationQ(settings.hands[k].rotation);}

function rotationFraction(k,error){
 const h=settings.hands[k],normal=error>1e-8?Math.min(1,h.rotationSpeed/60/error):1;
 const sync=settings.syncRotation||0;
 if(sync===0||(!h.grab&&h.orientation==='natural'))return normal;
 // Recompute from the displayed wrist so moving goals and resumed snapshots
 // need no timer/history. Keep the authored angular speed as the upper bound.
 const distance=norm(sub(wristTarget(k).slice(0,3),pose[hands[k]].slice(0,3)));
 const arrival=Math.min(1,(h.speed/60)/Math.max(distance,1e-8));
 return normal+(Math.min(normal,arrival)-normal)*sync;
}

function coupledAnchor(k){const h=settings.hands[k],g=grabs[k];return add(h.target,mul(g.normal,g.radius+.35));}
function bodyTarget(k,count=1){
 const g=grabs[k];if(!coupledEnabled||!settings.phat||!settings.hands[k].enabled||!g?.active||g.error)return wristTarget(k).slice(0,3);
 const wrist=wristTarget(k).slice(0,3),shoulder=pose[arms[k][1]].slice(0,3),jointKey=JSON.stringify(phat.wrists[k]),key=JSON.stringify([wrist,g.rotation,phat.wrists[k]]);
 // Body reach is cached independently of the explicit elbow posture. The blend
 // and moving shoulder update posture without changing the body approach.
 const prior=g.armPlan,route=prior?.version===8&&prior.jointKey===jointKey?prior:null;
 const input={shoulder,wrist,desired:g.rotation,joint:phat.wrists[k],localLower:armLocalLower[k],upperLength:armLengths[k][0],sign:k===0?1:-1,blend:settings.elbowDownBlend};
 const plan=route?ReachCoupled.track({...input,prior:route,sameTarget:route.key===key}):ReachCoupled.plan(input);
 const elbow=sub(wrist,R.rotate(plan.extent.forearm,armLocalLower[k]));
 // First let ordinary position reaching do its job. Only the extra shortfall
 // caused by wrist orientation can ask for more body movement.
 const positionShortfall=Math.max(0,norm(sub(wrist,shoulder))-armLengths[k][0]-armLengths[k][1]);
 const residual=norm(sub(elbow,shoulder))-armLengths[k][0]-positionShortfall+(plan.extent.cos<.99999?.35:0);
 const previousTarget=prior?.target||wrist,pursuit=solverState.slice(6+k*3,9+k*3).map(x=>x*100);
 const caughtUp=norm(sub(pursuit,previousTarget))<2;
 const change=Math.abs(residual)<.01?0:residual*(1-Math.exp(-count/12));
 const reserve=clamp((prior?.reserve||0)+(change<0||caughtUp?clamp(change,-count*.5,count*.5):0),0,armLengths[k][0]+armLengths[k][1]);
 const direction=normalize(sub(wrist,dataset.base[arms[k][1]].slice(0,3))),target=add(wrist,mul(direction,reserve));
 g.armPlan={...plan,version:8,key,jointKey,wrist,rotation:g.rotation.slice(),target,shoulder,reserve,residual};
 return target;
}
function applyFrame(raw){

 const out=copy(raw);

 if(wholeReturn){wholeReturn.tick++;blendLocal(out,wholeReturn.from,dataset.base,order(),Math.min(1,wholeReturn.tick/15));if(wholeReturn.tick>=15){wholeReturn=null;solverState=Array(20).fill(0);returns=[null,null];}}

 else for(let k=0;k<2;k++)if(returns[k]){const ret=returns[k];ret.tick++;blendLocal(out,ret.from,raw,arms[k],Math.min(1,ret.tick/15));if(ret.tick>=15)returns[k]=null;}

 for(let k=0;k<2;k++){

  if(settings.hands[k].enabled){const desired=targetQ(k,raw),a=angle(handQ[k],desired);handQ[k]=R.qslerp(handQ[k],desired,rotationFraction(k,a));out[hands[k]]=[...out[hands[k]].slice(0,3),...handQ[k]];}

  const g=grabs[k];
  if(coupledEnabled&&settings.phat&&settings.hands[k].enabled&&g?.active&&!g.error){
   const started=performance.now(),ids=arms[k].slice(1);
   const solved=ReachCoupled.solve({shoulder:out[ids[0]].slice(0,3),rawElbow:out[ids[1]].slice(0,3),previous:ids.map(j=>pose[j]),baseHand:dataset.base[ids[2]],upperLength:armLengths[k][0],lowerLength:armLengths[k][1],desired:g.rotation,command:handQ[k],anchor:coupledAnchor(k),palm:g.palm,joint:phat.wrists[k],speed:settings.hands[k].speed,forearmHint:g.armPlan?.forearm,poleHint:g.armPlan?.pole});
   out[ids[0]]=solved.upper;out[ids[1]]=solved.lower;out[ids[2]]=solved.hand;
   g.coupled={evaluations:solved.evaluations,palmError:norm(sub(add(solved.hand.slice(0,3),R.rotate(solved.hand.slice(3),g.palm)),coupledAnchor(k)))};
   coupledMs+=performance.now()-started;
  }else if(settings.phat&&(settings.hands[k].enabled||returns[k]||wholeReturn))out[hands[k]]=[...out[hands[k]].slice(0,3),...ReachWrist.constrain(phat.wrists[k],out[arms[k][2]].slice(3),out[hands[k]].slice(3))];

  handQ[k]=out[hands[k]].slice(3);

 }

 pose=out;for(let k=0;k<2;k++){
  const g=grabs[k];if(g?.active){
   ReachGrab.update(g,settings.hands[k],pose[hands[k]],settings);
  }else if(g)ReachGrab.returnStep(g);
 }ticks++;

}

function setEnabled(k,value){if(!value&&grabs[k]?.active){if(grabs[k].gripped)settings.hands[k].target=grabs[k].ball.slice(0,3);ReachGrab.release(grabs[k]);}settings.hands[k].enabled=value;revision++;if(value){wholeReturn=null;returns[k]=null;handQ[k]=pose[hands[k]].slice(3);}else{returns[k]={from:localPose(pose),tick:0};if(settings.hands.every(h=>!h.enabled))wholeReturn={from:localPose(pose),tick:0};}syncControls();persist();drawAll();}

async function step(count=1,render=true){if(!ready||pending)return;const active=settings.hands.some(h=>h.enabled);if(!active&&!wholeReturn&&!returns.some(Boolean)){if(render)drawAll();return;}

 if(scenarioMotion&&count>1){for(let i=0;i<count;i++)await step(1,false);if(render)drawAll();return;}
 advanceScenario();

 for(let k=0;k<2;k++)ReachGrab.feedback(grabs[k],settings.hands[k]);

 prepareGrabs();pending=true;const rev=revision,mode=(settings.hands[0].enabled?1:0)+(settings.hands[1].enabled?2:0);

 try{const targetStart=performance.now(),targets=[0,1].flatMap(k=>bodyTarget(k,count)),targetMs=performance.now()-targetStart;const result=await post('/step',{targets,speeds:settings.hands.map(h=>h.speed),mode,state:solverState,steps:count,elbowDownBlend:settings.elbowDownBlend,...(checkpointBase?{basePose:dataset.base}:{})});if(rev!==revision)return;solverState=result.state;solveMs=result.solveMs/count;coupledMs=targetMs;for(const p of result.poses)applyFrame(p);coupledMs/=count;$('connection').textContent='Solver ready';if(render)drawAll();}

 catch(e){playing=false;$('play').textContent='Play';$('connection').textContent='Solver unavailable';message(e.message);}finally{pending=false;}

}

const renderer=new ReachRenderer($('view'),{interactive:false,pixelRatio:Math.min(devicePixelRatio,1.5)});

new ResizeObserver(()=>{renderer.rect=$('view').getBoundingClientRect();drawAll();}).observe($('view'));

function camera(){const rect=renderer.rect,d=3.55/cameraState.zoom,target=[0,.87,0],raw=[Math.sin(cameraState.yaw)*d,.87+d*(.27-cameraState.pitch*.55),Math.cos(cameraState.yaw)*d],f=normalize(sub(target,raw)),right=normalize(cross(f,[0,1,0])),up=normalize(cross(right,f)),focal=rect.height*.5/Math.tan(Math.PI/8),depth=norm(sub(target,raw)),shift=add(mul(right,-cameraState.panX*depth/focal),mul(up,cameraState.panY*depth/focal));return {eye:add(raw,shift),f,right,up,focal};}

function projectPoint(p){const c=camera(),v=sub(p,c.eye),z=dot(v,c.f);return {x:renderer.rect.width/2+dot(v,c.right)*c.focal/z,y:renderer.rect.height/2-dot(v,c.up)*c.focal/z,z};}

function drawAll(){if(!ready)return;renderer.draw(renderData(),[0,0,0]);

 for(let k=0;k<2;k++){const p=projectPoint(toDisplay(ballPoint(k))),el=$('label'+k);el.style.left=p.x+'px';el.style.top=(p.y-16)+'px';el.style.display=p.z>0?'block':'none';el.classList.toggle('off',!settings.hands[k].enabled);const h=settings.hands[k],d=norm(sub(pose[hands[k]].slice(0,3),wristTarget(k).slice(0,3))),a=angle(pose[hands[k]].slice(3),targetQ(k,pose));$('distance'+k).textContent=d.toFixed(2)+' cm';$('angle'+k).textContent=a.toFixed(1)+'°';let status=!h.enabled?'Resting':d>3?'Reaching':a>settings.closure?'Wrist limited':a>settings.grip?'Closure angle OK':'Angle gates OK';const g=grabs[k];if(h.grab&&h.enabled&&g){status=g.error|| (g.gripped?'Held':d>=3?'Reaching':a>settings.closure?'Rotation blocked':g.close<1?'Closing '+Math.round(g.close*100)+'%':a>settings.grip?'Grip angle blocked':'Grip pending');}$('status'+k).textContent=status;$('gripInfo'+k).textContent=h.grab&&g?.active?(g.coupled?'Palm '+g.coupled.palmError.toFixed(2)+' cm · ':'')+g.contacts+'/5 fingers fitted · clearance '+(g.clearance||0).toFixed(2)+' cm':'Open fingers';$('status'+k).classList.toggle('warn',h.enabled&&(a>settings.closure||d>3));}

 $('clock').textContent='Tick '+ticks+' · '+(solveMs+coupledMs).toFixed(2)+' ms';$('bodyMetrics').innerHTML=['Drop','Shift X','Shift Y','Yaw','Pitch','Roll'].map((n,i)=>'<dt>'+n+'</dt><dd>'+(solverState[i]*(i<3?100:180/Math.PI)).toFixed(2)+(i<3?' cm':'°')+'</dd>').join('');

}

function surfaceReference(k){
 const g=grabs[k];if(!g?.active||!settings.hands[k].grab)return null;
 // The selected normal is ball-local (the ball starts with identity rotation).
 // A held ball rotates with the wrist; carry the original surface point with it.
 const normal=g.gripped?R.rotate(g.ball.slice(3),g.normal):g.normal;
 const point=add(ballPoint(k),mul(normal,g.radius));
 return {point:toDisplay(point),normal:toDisplay(mul(normal,100)),actual:toDisplay(sub(add(pose[hands[k]].slice(0,3),R.rotate(pose[hands[k]].slice(3),g.palm)),R.rotate(R.qm(pose[hands[k]].slice(3),R.qinv(g.rotation)),mul(g.normal,.35))))};
}
function renderData(){return {contacts:[0,1].map(surfaceReference),points:pose.map(p=>toDisplay(p.slice(0,3))),axes:pose.map(p=>axes(p.slice(3))),tint:[.65,.73,.78],bicolor:true,skeleton:$('skeleton').checked,hideSword:true,targets:settings.hands.map((h,k)=>({point:toDisplay(ballPoint(k)),goal:toDisplay(h.target),radius:h.radius*.01,enabled:h.enabled,gripped:!!grabs[k]?.gripped})),fingerLines:fingerModels.map((m,k)=>ReachGrab.segments(m,grabs[k]||ReachGrab.fresh(settings.hands[k].target),pose[hands[k]]).map(l=>({a:toDisplay(l.a),b:toDisplay(l.b),finger:l.finger}))),palms:fingerModels.map((m,k)=>{const q=pose[hands[k]].slice(3),base=pose[hands[k]].slice(0,3),length=norm(m.fingers[6].open.slice(0,3));return {center:toDisplay(add(base,R.rotate(q,mul(m.forward,length*.45)))),forward:toDisplay(mul(R.rotate(q,m.forward),100)),palmNormal:toDisplay(mul(R.rotate(q,m.normal),100)),side:toDisplay(mul(R.rotate(q,normalize(cross(m.forward,m.normal))),100)),dims:[length*.009,.075,.025],palmFace:1};}),showWristAxes:$('axes').checked,wristDirections:hands.map(j=>[[100,0,0],[0,100,0],[0,0,100]].map(v=>toDisplay(R.rotate(pose[j].slice(3),v))))};}

function snapshot(){return {schema:2,app:'reach-lab',...(checkpointBase?{basePose:copy(checkpointBase)}:{}),...(scenarioMotion?{motion:scenarioMotion}:{}),settings:copy(settings),pose:copy(pose),solverState:[...solverState],camera:copy(cameraState),tick:ticks,sourceSha256:dataset.sourceSha256,kernelSha256:dataset.kernelSha256,phat:copy(phat),handQ:copy(handQ),grabs:copy(grabs),fingerSource:fingerData.poseSha256,returns:copy(returns),wholeReturn:copy(wholeReturn),playing,controls:{playSpeed:Number($('playSpeed').value),skeleton:$('skeleton').checked,axes:$('axes').checked}};}

function syncControls(){$('elbowDownBlend').value=settings.elbowDownBlend;$('elbowDownBlendValue').textContent=settings.elbowDownBlend.toFixed(2);$('syncRotation').value=settings.syncRotation;$('syncRotationValue').textContent=settings.syncRotation.toFixed(2);for(let k=0;k<2;k++){const h=settings.hands[k];$('enabled'+k).checked=h.enabled;$('grab'+k).checked=h.grab;for(let i=0;i<3;i++){if(document.activeElement!==$('p'+k+i))$('p'+k+i).value=h.target[i].toFixed(1);$('r'+k+i).value=Number(h.rotation[i].toFixed(3));}$('speed'+k).value=h.speed;$('rotSpeed'+k).value=h.rotationSpeed;$('orientation'+k).querySelector('[value=natural]').disabled=h.grab;$('orientation'+k).value=h.orientation==='surface'?'target':h.orientation;$('orientationMode'+k).hidden=h.orientation==='surface';$('rotations'+k).hidden=h.orientation!=='target';}const autoCount=settings.hands.filter(h=>h.orientation==='surface').length;$('autoPalm').checked=autoCount===2;$('autoPalm').indeterminate=autoCount===1;syncBallSize();$('phat').checked=settings.phat;$('closure').value=settings.closure;$('grip').value=settings.grip;}

$('elbowDownBlend').oninput=e=>{const value=e.target.valueAsNumber;if(!Number.isFinite(value))return;settings.elbowDownBlend=clamp(value,0,1);$('elbowDownBlendValue').textContent=settings.elbowDownBlend.toFixed(2);revision++;persist();};
$('syncRotation').oninput=e=>{const value=e.target.valueAsNumber;if(!Number.isFinite(value))return;settings.syncRotation=clamp(value,0,1);$('syncRotationValue').textContent=settings.syncRotation.toFixed(2);persist();};

function syncBallSize(){const [a,b]=settings.hands.map(h=>h.radius);$('ballRadius').value=a;$('ballRadiusValue').textContent=a===b?a+' cm':a+' / '+b+' cm';}
$('ballRadius').oninput=e=>{const radius=e.target.valueAsNumber;if(!Number.isFinite(radius))return;for(const h of settings.hands)h.radius=clamp(radius,.5,15);revision++;syncBallSize();persist();drawAll();};
function setGrab(k,value){const g=grabs[k],h=settings.hands[k];if(!value&&g?.gripped)h.target=g.ball.slice(0,3);h.grab=value;if(value&&h.orientation==='natural')h.orientation='target';revision++;if(!value&&g){if(g.coupled)seedCurrentArm(k);ReachGrab.release(g);}}
function seedCurrentArm(k){
 // The body request is a virtual endpoint during coupled grabs. Never reuse it
 // as an actual wrist position when switching back to ordinary reaching.
 handQ[k]=pose[hands[k]].slice(3);
 for(let i=0;i<3;i++){solverState[6+k*3+i]=pose[hands[k]][i]*.01;solverState[12+k*3+i]=pose[arms[k][2]][i]*.01;}
 solverState[18+k]=1;
}
function restartGrabsFromCurrentPose(){
 revision++;
 for(let k=0;k<2;k++){
  const h=settings.hands[k],g=grabs[k];
  if(g?.gripped)h.target=g.ball.slice(0,3);
  if(g)ReachGrab.release(g);
  if(!h.enabled)continue;
  h.grab=true;if(h.orientation==='natural')h.orientation='target';
  seedCurrentArm(k);returns[k]=null;
 }
 if(settings.hands.some(h=>h.enabled))wholeReturn=null;
 prepareGrabs();
}
$('autoPalm').onchange=e=>{for(const h of settings.hands)h.orientation=e.target.checked?'surface':'target';revision++;syncControls();persist();drawAll();};
function resetButton(k,field){const kind=field==='target'?'translation':'rotation',side=k===0?'left':'right',values=resetDefaults.hands[k][field].join(', ');return `<button type="button" class="resetField" id="reset-${field}-${k}" aria-label="Reset ${side} ${kind}" title="Reset ${kind} to ${values}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10a8 8 0 1 1 1 7M4 4v6h6"/></svg></button>`;}

function makeControls(){for(let k=0;k<2;k++){const div=document.createElement('article');div.className='hand '+(k===0?'left':'right');div.innerHTML=`<header><h2>${k===0?'Left':'Right'} hand</h2><label><input id="enabled${k}" type="checkbox"> Reaching</label></header><div class="handBody"><div class="grabControls"><label><input id="grab${k}" type="checkbox"> Grab ball</label></div><p class="hint">XYZ = ball centre when grabbing; wrist when reach only.</p><div class="transformGroup"><div class="xyz">${['X','Y','Z'].map((n,i)=>`<label>${n} · cm<input id="p${k}${i}" type="number" step="1" min="-300" max="300"></label>`).join('')}</div>${resetButton(k,'target')}</div><label class="row">Reach speed <input id="speed${k}" type="number" min="1" max="1000" step="10"></label><label class="row" id="orientationMode${k}">Hand orientation<select id="orientation${k}"><option value="target">Absolute rotation</option><option value="natural">Follow arm</option></select></label><div id="rotations${k}" class="transformGroup"><div class="xyz">${['X','Y','Z'].map((n,i)=>`<label>${n} · world °<input id="r${k}${i}" type="number" step="5" min="-180" max="180"></label>`).join('')}</div>${resetButton(k,'rotation')}</div><label class="row">Rotation speed <input id="rotSpeed${k}" type="number" min="1" max="1000" step="30"></label><div class="metrics"><span id="distance${k}">0 cm</span><span id="angle${k}">0°</span><span id="status${k}" class="status"></span></div><p id="gripInfo${k}" class="hint"></p></div>`;$('hands').append(div);

 for(const field of ['target','rotation'])$('reset-'+field+'-'+k).onclick=()=>{settings.hands[k][field]=copy(resetDefaults.hands[k][field]);syncControls();persist();drawAll();};

 $('enabled'+k).onchange=e=>setEnabled(k,e.target.checked);

 $('grab'+k).onchange=e=>{setGrab(k,e.target.checked);syncControls();persist();drawAll();};



 for(let i=0;i<3;i++)for(const [prefix,field,lo,hi] of [['p','target',-300,300],['r','rotation',-180,180]])$(prefix+k+i).oninput=e=>{if(!Number.isFinite(e.target.valueAsNumber))return;settings.hands[k][field][i]=clamp(e.target.valueAsNumber,lo,hi);persist();drawAll();};

 for(const [prefix,field] of [['speed','speed'],['rotSpeed','rotationSpeed']])$(prefix+k).oninput=e=>{if(Number.isFinite(e.target.valueAsNumber)){settings.hands[k][field]=clamp(e.target.valueAsNumber,1,1000);persist();}};

 $('orientation'+k).onchange=e=>{settings.hands[k].orientation=e.target.value;syncControls();persist();drawAll();};

}}

const canvas=$('view');canvas.oncontextmenu=e=>e.preventDefault();

canvas.onpointerdown=e=>{if(!ready)return;const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top,c=camera();let hit=-1,best=Infinity;if(e.button===2)settings.hands.forEach((h,k)=>{const p=projectPoint(toDisplay(ballPoint(k))),d=Math.hypot(p.x-x,p.y-y),radius=Math.max(25,c.focal*(h.radius*.01+.015)/p.z);if(p.z>0&&d<radius&&d<best){best=d;hit=k;}});if(e.button===2&&hit<0){message('Right-drag one of the coloured target balls.');return;}drag={button:e.button,k:hit,x:e.clientX,y:e.clientY,start:hit>=0?[...settings.hands[hit].target]:null,camera:c,depth:hit>=0?projectPoint(toDisplay(settings.hands[hit].target)).z:0,depthMode:e.shiftKey};canvas.setPointerCapture(e.pointerId);e.preventDefault();};

canvas.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(drag.k>=0){const c=drag.camera,scale=drag.depth/c.focal,delta=drag.depthMode?mul(c.f,-dy*scale):add(mul(c.right,dx*scale),mul(c.up,-dy*scale));settings.hands[drag.k].target=add(drag.start,fromDisplay(delta)).map(v=>clamp(v,-300,300));syncControls();}else{if(drag.button===1||e.shiftKey){cameraState.panX+=dx;cameraState.panY+=dy;}else{cameraState.yaw+=dx*.008;cameraState.pitch=clamp(cameraState.pitch+dy*.006,-1.5,3.5);}drag.x=e.clientX;drag.y=e.clientY;}drawAll();};

function endDrag(){if(drag?.k>=0)persist();drag=null;}canvas.onpointerup=endDrag;canvas.onpointercancel=endDrag;canvas.onlostpointercapture=endDrag;

canvas.addEventListener('wheel',e=>{e.preventDefault();cameraState.zoom=clamp(cameraState.zoom*Math.exp(-e.deltaY*.001),.4,3);drawAll();},{passive:false});

function resetPose(){scenarioMotion=null;revision++;grabs=[null,null];solverState=Array(20).fill(0);pose=copy(dataset.base);handQ=hands.map(j=>pose[j].slice(3));returns=[null,null];wholeReturn=null;ticks=0;accum=0;drawAll();}

$('restart').onclick=async()=>{if(scenarioMotion)await restartCapturedScenario();else resetPose();setPlaying(true);};
$('reset').onclick=()=>{for(let k=0;k<2;k++)for(const field of ['target','rotation'])settings.hands[k][field]=copy(resetDefaults.hands[k][field]);resetPose();syncControls();persist();};$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'Pause':'Play';accum=0;};$('step').onclick=()=>{playing=false;$('play').textContent='Play';step(1);};$('cameraReset').onclick=()=>{Object.assign(cameraState,cameraDefault);drawAll();};

document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{Object.assign(cameraState,cameraDefault,{yaw:b.dataset.view==='side'?Math.PI/2:0,pitch:b.dataset.view==='top'?-8:.49,zoom:b.dataset.view==='top'?3.5:1.25});drawAll();});

for(const id of ['skeleton','axes'])$(id).onchange=drawAll;$('phat').onchange=()=>{settings.phat=$('phat').checked;restartGrabsFromCurrentPose();syncControls();persist();drawAll();message('Grab motion restarted from the current hand poses.');};for(const key of ['closure','grip'])$(key).oninput=e=>{if(Number.isFinite(e.target.valueAsNumber)){settings[key]=clamp(e.target.valueAsNumber,0,180);persist();drawAll();}};

window.addEventListener('keydown',e=>{if(/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;if(e.code==='KeyP'){e.preventDefault();saveSnapshot().catch(showError);}if(e.code==='Space'){e.preventDefault();$('play').click();}if(e.code==='ArrowRight'){e.preventDefault();$('step').click();}});

async function load(){try{[dataset,phat,settings,resetDefaults,fingerData]=await Promise.all(['/data.json','/phat.json','/state','/reset-defaults','/fingers.json'].map(p=>fetch(p).then(r=>r.json())));referenceBase=copy(dataset.base);fingerModels=[0,1].map(k=>ReachGrab.build(fingerData,k));armLengths=arms.map(a=>[norm(sub(dataset.base[a[2]].slice(0,3),dataset.base[a[1]].slice(0,3))),norm(sub(dataset.base[a[3]].slice(0,3),dataset.base[a[2]].slice(0,3)))]);armLocalLower=arms.map(a=>R.rotate(R.qinv(dataset.base[a[2]].slice(3)),sub(dataset.base[a[3]].slice(0,3),dataset.base[a[2]].slice(0,3))));const previousSchema=settings.schema;settings=sanitize(settings);if(desktopToken&&previousSchema!==2)await post('/state',settings);names=dataset.names;parents=dataset.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));pose=copy(dataset.base);handQ=hands.map(j=>pose[j].slice(3));makeControls();syncControls();$('phatInfo').textContent='Imported '+new Date(phat.exported).toLocaleDateString()+'. Twist / swing 2 / swing 1: L '+phat.wrists[0].limits.map(x=>x.toFixed(1)).join(' / ')+'°; R '+phat.wrists[1].limits.map(x=>x.toFixed(1)).join(' / ')+'°.';ready=true;$('connection').textContent='Solver ready';await initWorkspace();drawAll();}catch(e){message(e.message);$('connection').textContent='Unable to start';}}

function frame(now){if(last&&ready&&workspaceReady&&playing&&!document.hidden){accum+=Math.min(.1,(now-last)/1000)*Number($('playSpeed').value);if(!pending&&accum>=1/60){const n=Math.min(4,Math.floor(accum*60));accum-=n/60;step(n);}}else accum=0;last=now;requestAnimationFrame(frame);}requestAnimationFrame(frame);

window.reachLab={get ready(){return ready&&workspaceReady;},snapshot,projectTarget:k=>projectPoint(toDisplay(settings.hands[k].target)),setEnabled,step,resetPose,get playing(){return playing;}};



