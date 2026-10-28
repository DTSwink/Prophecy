/* Offline motion measurements. Scores identify review intervals, never certify animation quality. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const angle=(a,b)=>2*Math.acos(clamp(Math.abs(dot(a,b)),-1,1))*180/Math.PI;
const vectorAngle=(a,b)=>Math.acos(clamp(dot(unit(a),unit(b)),-1,1))*180/Math.PI;
const boxFaces=[[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]];
const round=(v,n=6)=>Number.isFinite(v)?+v.toFixed(n):null;
const compact=v=>Array.isArray(v)?v.map(compact):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).map(([k,x])=>[k,compact(x)])):typeof v==='number'?round(v):v;
function pose(p){return p.axes?p:{...p,axes:p.q.map(R.toAxes)};}
function clip(poly,axis,bound,sign){
 const out=[];if(!poly.length)return out;
 let a=poly.at(-1),da=sign*(a[axis]-bound);
 for(const b of poly){const db=sign*(b[axis]-bound);if((da>=0)!==(db>=0))out.push(add(a,mul(sub(b,a),da/(da-db))));if(db>=0)out.push(b);a=b;da=db;}return out;
}
function surfaceData(s){
 if(s.origin&&s.u&&s.v&&s.bounds)return {id:s.id,origin:s.origin,u:s.u,v:s.v,normal:s.normal||unit(cross(s.v,s.u)),bounds:s.bounds};
 if(Number.isFinite(s.y))return {id:s.id,origin:[0,s.y,0],u:[1,0,0],v:[0,0,1],normal:[0,1,0],bounds:[s.x0,s.x1,s.z0,s.z1]};
 return null;
}
function signedShoeGap(corners,surfaces){
 let gap=Infinity,normal=null,surface=null;
 for(const s of surfaces){
  const local=corners.map(p=>{const d=sub(p,s.origin);return [dot(d,s.u),dot(d,s.normal),dot(d,s.v)];});
  for(let b=0;b<local.length;b+=8){
   const box=local.slice(b,b+8),[xmin,xmax,zmin,zmax]=s.bounds;
   if(Math.max(...box.map(p=>p[0]))<xmin||Math.min(...box.map(p=>p[0]))>xmax||Math.max(...box.map(p=>p[2]))<zmin||Math.min(...box.map(p=>p[2]))>zmax)continue;
   for(const face of boxFaces){let poly=face.map(i=>box[i]);for(const cut of [[0,xmin,1],[0,xmax,-1],[2,zmin,1],[2,zmax,-1]])poly=clip(poly,...cut);
    for(const p of poly)if(p[1]<gap){gap=p[1];normal=s.normal;surface=s.id;}
   }
  }
 }
 return {gap:Number.isFinite(gap)?gap:null,normal,surface};
}
function knee(p,ids){
 const a=p.points[ids.hip],b=p.points[ids.knee],c=p.points[ids.foot],axis=unit(sub(c,a));
 const bend=sub(sub(b,a),mul(axis,dot(sub(b,a),axis)));
 return {pole:rotate(qinv(p.q[ids.pelvis]),unit(bend)),bend:length(bend),flex:vectorAngle(sub(b,a),sub(c,b)),reach:length(sub(c,a))/(length(sub(b,a))+length(sub(c,b)))};
}
function intervals(rows,key,side,predicate,fps,minimum=0){
 const out=[];let start=-1;
 const finish=i=>{if(start<0)return;const span=rows.slice(start,i),values=span.map(r=>side===null?r[key]:r.feet[side][key]),at=values.reduce((best,v,j)=>Math.abs(v??0)>Math.abs(values[best]??0)?j:best,0),duration=(i-start)/fps;
  if(duration>=minimum)out.push({metric:key,side:side===null?null:['L','R'][side],start:rows[start].frame,end:rows[i-1].frame,duration,peakFrame:span[at].frame,peak:values[at]});start=-1;};
 for(let i=0;i<rows.length;i++){if(predicate(rows[i],i)){if(start<0)start=i;}else finish(i);}finish(rows.length);return out;
}
function peak(rows,key,side){
 let item=null;for(const r of rows){const v=side===null?r[key]:r.feet[side][key];if(Number.isFinite(v)&&(!item||(key.endsWith('Extra')?v>item.value:Math.abs(v)>Math.abs(item.value))))item={value:v,frame:r.frame,time:r.time};}return item;
}
function audit({run,model,options={}}){
 if(!run?.names||!run?.parents||!model?.frames?.length)throw Error('audit requires run.names/parents and model.frames');
 const fps=model.fps||120,userFps=options.userFps||60,frames=model.frames,names=run.names,parents=run.parents;
 const pelvis=names.indexOf('pelvis'),ids=['l','r'].map(s=>({side:s.toUpperCase(),pelvis,...Object.fromEntries([['hip','thigh'],['knee','calf'],['foot','foot'],['toe','ball']].map(([k,b])=>[k,names.indexOf(b+'_'+s)]))}));
 if(ids.some(l=>Object.values(l).some(v=>typeof v==='number'&&v<0)))throw Error('audit needs pelvis, thigh/calf/foot/ball for both legs');
 const surfaces=(model.terrain?.surfaces||model.terrain?.tiles||options.surfaces||[]).map(surfaceData).filter(Boolean),rows=[],geometry=[];
 let previous=null;
 for(let i=0;i<frames.length;i++){
  const f=frames[i],p=pose(f.pose),raw=pose(f.raw||options.rawAt?.(i/fps)||f.pose),root=p.points[0],prevRoot=i?frames[i-1].pose.points[0]:root;
  const rootV=i?mul(sub(root,prevRoot),fps):mul(sub(frames[Math.min(1,frames.length-1)].pose.points[0],root),fps),normal=f.normal||f.surfaceNormal||[0,1,0];
  const supplied=options.travelAxis?.(f,i),velocity=i?rootV:mul(sub(frames[Math.min(1,frames.length-1)].pose.points[0],root),fps);
  const travel=unit(supplied||sub(velocity,mul(normal,dot(velocity,normal))));
  const fallback=length(travel)>1e-6?travel:rotate(p.q[pelvis],[0,-1,0]);
  const row={frame:i*userFps/fps,time:i/fps,rootSpeed:length(rootV),rootVerticalSpeed:rootV[1],rootAcceleration:previous?length(mul(sub(rootV,previous.rootV),fps)):0,
   rootNNError:length(sub(root,raw.points[0])),pelvisNNError:length(sub(p.points[pelvis],raw.points[pelvis])),boneLengthError:0,boneLengthBone:null,nonfinite:0,feet:[]};
  for(let j=0;j<names.length;j++){
   if(![...p.points[j],...p.q[j]].every(Number.isFinite))row.nonfinite++;
   // Root-to-pelvis is the authored root/pelvis translation, not a rigid bone.
   if(parents[j]<0||j===pelvis)continue;const error=Math.abs(length(sub(p.points[j],p.points[parents[j]]))-length(sub(raw.points[j],raw.points[parents[j]])));
   if(error>row.boneLengthError){row.boneLengthError=error;row.boneLengthBone=names[j];}
  }
  const geo={points:p.points,raw:raw.points,shoes:[],rawShoes:[],contacts:[]},internals=[];
  for(let side=0;side<2;side++){
   const l=ids[side],foot=f.feet?.[side]||{},contact=foot.contact,ankle=p.points[l.foot],rawAnkle=raw.points[l.foot];
   const corners=S.footPoints(p,l.foot,l.toe,l.side).map(v=>add(ankle,v)),rawCorners=S.footPoints(raw,l.foot,l.toe,l.side).map(v=>add(rawAnkle,v));
   let clearance=signedShoeGap(corners,surfaces),rawClearance=signedShoeGap(rawCorners,surfaces);
   if(options.shoeGap){clearance=options.shoeGap(corners,{frame:f,index:i,side:l.side,raw:false})||clearance;rawClearance=options.shoeGap(rawCorners,{frame:f,index:i,side:l.side,raw:true})||rawClearance;}
   const n=unit(contact?.normal||clearance.normal||normal),v=i?mul(sub(ankle,previous.p.points[l.foot]),fps):[0,0,0],nv=i?mul(sub(rawAnkle,previous.raw.points[l.foot]),fps):[0,0,0];
   const a=i>1?mul(sub(v,previous.feet[side].v),fps):[0,0,0],na=i>1?mul(sub(nv,previous.feet[side].nv),fps):[0,0,0];
   const k=knee(p,l),nk=knee(raw,l),local=rotate(qinv(p.q[pelvis]),sub(ankle,p.points[pelvis])),rawLocal=rotate(qinv(raw.q[pelvis]),sub(rawAnkle,raw.points[pelvis]));
   const localAxis=rotate(qinv(p.q[pelvis]),fallback),rawAxis=rotate(qinv(raw.q[pelvis]),fallback);
   const progress=i?dot(sub(local,previous.feet[side].local),localAxis)*fps:0,rawProgress=i?dot(sub(rawLocal,previous.feet[side].rawLocal),rawAxis)*fps:0;
   const material=contact?.localPoint?add(ankle,rotate(p.q[l.foot],contact.localPoint)):null;
   const destination=contact?(options.contactPoint?.(contact,f,i)||contact.point):null;
   const pinError=material&&destination?length(sub(material,destination)):null;
   // Different material pivots during heel-toe roll are legitimate. Measure
   // each pivot against its own intended surface point, never ankle movement.
   const samePivot=contact&&previous?.feet[side].contact&&contact.surface===previous.feet[side].contact.surface&&contact.stanceId===previous.feet[side].contact.stanceId&&contact.localPoint&&previous.feet[side].contact.localPoint&&length(sub(contact.localPoint,previous.feet[side].contact.localPoint))<1e-6;
   const pinSlip=samePivot&&material&&destination&&previous.feet[side].material&&previous.feet[side].destination?length(sub(sub(material,previous.feet[side].material),sub(destination,previous.feet[side].destination)))*fps:null;
   const kneeStep=i&&k.bend>.008&&previous.feet[side].k.bend>.008?vectorAngle(k.pole,previous.feet[side].k.pole):null;
   const nnKneeStep=i&&nk.bend>.008&&previous.feet[side].nk.bend>.008?vectorAngle(nk.pole,previous.feet[side].nk.pole):null;
   const footStep=i?angle(p.q[l.foot],previous.p.q[l.foot]):0,nnFootStep=i?angle(raw.q[l.foot],previous.raw.q[l.foot]):0;
   const out={state:foot.state||'unknown',contact:!!contact,pinError,pinSlip,soleGap:clearance.gap,nnSoleGap:rawClearance.gap,penetration:Math.max(0,-(clearance.gap??0)),penetrationExtra:Math.max(0,-(clearance.gap??0))-Math.max(0,-(rawClearance.gap??0)),
    speed:length(v),nnSpeed:length(nv),speedExtra:length(v)-length(nv),acceleration:length(a),nnAcceleration:length(na),accelerationExtra:length(sub(a,na)),
    tangentSpeed:length(sub(v,mul(n,dot(v,n)))),normalSpeed:dot(v,n),pelvisProgress:progress,nnPelvisProgress:rawProgress,
    kneePoleStep:kneeStep,nnKneePoleStep:nnKneeStep,kneePoleExtra:kneeStep===null||nnKneeStep===null?null:kneeStep-nnKneeStep,kneeBend:k.bend,kneeFlex:k.flex,reach:k.reach,
    ankleNNError:angle(qm(qinv(p.q[l.knee]),p.q[l.foot]),qm(qinv(raw.q[l.knee]),raw.q[l.foot])),footStep,nnFootStep,footStepExtra:footStep-nnFootStep,
    footNNDistance:length(sub(ankle,rawAnkle)),targetError:foot.target?length(sub(ankle,foot.target)):null};
   row.feet.push(out);internals.push({v,nv,local,rawLocal,k,nk,contact,material,destination});
   geo.shoes.push(corners);geo.rawShoes.push(rawCorners);geo.contacts.push(destination||null);
  }
  rows.push(row);geometry.push(geo);previous={p,raw,rootV,feet:internals};
 }
 const warnings=[],summary={};
 const metrics=['pinError','pinSlip','penetration','penetrationExtra','speed','speedExtra','acceleration','accelerationExtra','kneePoleStep','kneePoleExtra','ankleNNError','footStep','footStepExtra','footNNDistance','targetError','reach'];
 for(let side=0;side<2;side++){
  summary[ids[side].side]=Object.fromEntries(metrics.map(key=>[key,peak(rows,key,side)]));
  for(const [key,threshold,minimum] of [['pinError',.002,0],['pinSlip',.04,.02],['penetrationExtra',.005,0],['kneePoleExtra',12,0],['footStepExtra',10,0],['accelerationExtra',80,0],['ankleNNError',55,.05]]){
   warnings.push(...intervals(rows,key,side,r=>r.feet[side][key]>threshold,fps,minimum).map(w=>({...w,threshold,kind:'review'})));
  }
  warnings.push(...intervals(rows,'pelvisProgress',side,r=>r.feet[side].state==='SWING'&&!r.feet[side].contact&&r.rootSpeed>.3&&r.feet[side].pelvisProgress<.05,fps,.07).map(w=>({...w,kind:'possible-swing-stall',note:'Can be valid rear-leg folding; compare NN trace and subsequent travel.'})));
 }
 summary.root=Object.fromEntries(['rootSpeed','rootVerticalSpeed','rootAcceleration','rootNNError','pelvisNNError','boneLengthError','nonfinite'].map(key=>[key,peak(rows,key,null)]));
 warnings.sort((a,b)=>(Math.abs(b.peak)/(b.threshold||1))-(Math.abs(a.peak)/(a.threshold||1)));
 const report={version:1,units:{length:'m',time:'s',angle:'deg',speed:'m/s',acceleration:'m/s²',step:'per native sample',frame:userFps+'Hz'},
  metadata:{source:run.source||null,settings:model.settings||null,frames:frames.length,fps,userFps,rawReference:'model.frames[i].raw (same directional source; its provenance is supplied by the caller)',
   surfaceCoverage:options.shoeGap?'custom full-shoe callback':surfaces.length?'finite surface face clipping':'none; penetration is unverified',limitations:['Thresholds rank review intervals; they are not quality pass/fail judgments.','Knee pole angles are omitted below8mm bend to avoid straight-knee numerical ambiguity.','Bone lengths compare against same-frame source; root-to-pelvis translation is excluded.','Derivatives use native sample differences;30Hz policy key boundaries may be present in both traces.','Slope normals depend on supplied surface metadata.','Surface gaps treat finite top rectangles as solid below their plane; thin platform undersides require a custom shoeGap callback.']},summary,worstIntervals:warnings.slice(0,options.maxIntervals||36),rows};
 if(options.geometry!==false)report.geometry={names,parents,surfaces,frames:geometry};
 return compact(report);
}
const api={audit,signedShoeGap,surfaceData,boxFaces};if(typeof module!=='undefined')module.exports=api;else root.MotionAudit=api;
})(globalThis);
