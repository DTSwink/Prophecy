const assert=require('node:assert/strict'),H=require('./holster.js'),R=require('./recovery.js');
const setup=require('./data/unreal-setup.json'),data=require('./data/motions.json');
const point=(t,p)=>R.add(t.p,R.rotate(t.q,p.map((v,i)=>v*t.s[i]))),dist=(a,b)=>R.length(R.sub(a,b));
const tip=setup.swordMesh.sections.flatMap(s=>s.vertices).reduce((a,b)=>a[2]>b[2]?a:b);
let maxAxialError=0;
for(const rotation of [[0,0,0,1],R.qexp([.4,-.8,.3])])for(const shrink of [0,10,35,70,99]){
 const holster={...setup.holster,p:[13,27,91],q:R.qm(rotation,setup.holster.q)},full=H.seatedSword(setup,holster),retained=1-shrink/100;
 const seat=H.seatHandAtScale(setup,full,retained),sword=H.compose(H.scaledGrip(setup,retained),seat);
 const authoredBase=point(full,setup.baseBladeLocal);
 assert(dist(point(sword,setup.baseBladeLocal),authoredBase)<1e-8,'100% shortened blade base stays at authored mouth');
 const axis=R.rotate(sword.q,[0,0,1]),clear={...sword,p:R.sub(sword.p,R.mul(axis,setup.bladeLength*retained))};
 const axialError=Math.abs(R.dot(R.sub(point(clear,tip),authoredBase),axis));maxAxialError=Math.max(maxAxialError,axialError);
 assert(axialError<.00002,'0% shortened tip meets authored mouth plane');
 assert.equal(sword.s[0],setup.assetScale[0]);assert.equal(sword.s[1],setup.assetScale[1]);
}
for(const sheathe of [true,false]){
 const m=H.prepare(data,setup,{sheathe,shrinkPercent:35}),f=m.frames[sheathe?m.plan.endTick:m.plan.slideEnd];
 assert(m.plan.arrives);const full=H.seatedSword(setup,f.holster),base=point(full,setup.baseBladeLocal),axis=R.rotate(f.sword.q,[0,0,1]);
 if(sheathe){
  assert(dist(point(f.sword,H.bladeTip(setup)),base)<=2,'S accepts tip within the existing 2cm gate');
  assert(H.angle(f.sword.q,full.q)<=m.o.sheatheRotationTolerance+1e-5,'S accepts within angular tolerance');
 }else assert(Math.abs(R.dot(R.sub(point(f.sword,tip),base),axis))<.00002,'D clear endpoint aligned');
}
console.log(JSON.stringify({passed:true,shrinkCases:10,maxAxialErrorCm:maxAxialError}));
