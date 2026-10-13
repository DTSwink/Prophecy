const assert=require('node:assert/strict'),R=require('./recovery'),H=require('./holster'),L=require('./leeway');
const setup=require('./data/unreal-setup.json'),tip=H.bladeTip(setup);
const holster={p:[13,-7,20],q:R.qexp([.2,-.7,.1]),s:[1,1,1]},full=H.seatedSword(setup,holster),mouth=H.point(full,setup.baseBladeLocal);
const model={o:{sheathe:true,sheatheRotationTolerance:15},setup,tip};
const axis=R.unit(R.sub(setup.baseBladeLocal,tip)),u=R.unit(R.cross(axis,[0,1,0]));
function frame(tilt,roll,offset=0,scale=.8){
 const q=R.qm(full.q,R.qm(R.qexp(R.mul(u,tilt*Math.PI/180)),R.qexp(R.mul(axis,roll*Math.PI/180))));
 const s=full.s.map((x,i)=>x*(i===2?scale:1));
 return {phase:'Reach',body:{remainingDegrees:0},holster,sword:{q,s,p:R.add(R.sub(mouth,R.rotate(q,tip.map((x,i)=>x*s[i]))),[offset,0,0])}};
}
for(const tilt of [0,5,14,15,20,60,179,180])for(const roll of [0,5,15,20,90,179]){
 const f=frame(tilt,roll),before=JSON.stringify([model,f]),d=L.sample(model,f);
 assert.equal(JSON.stringify([model,f]),before,'visualization cannot mutate motion');
 assert(Math.abs(d.tipError)<1e-8);assert(Number.isFinite(d.roll));
 const expected=2*Math.acos(Math.cos(tilt*Math.PI/360)*Math.cos(roll*Math.PI/360))*180/Math.PI;
 assert(Math.abs(d.error-expected)<1e-5);assert.equal(d.rotationOK,expected<=15+1e-5);
 if(tilt<15)assert.equal(d.rotationOK,Math.abs(d.roll)<=d.rollBudget+1e-5);
 assert(d.lines.every(l=>[...l.a,...l.b].every(Number.isFinite)));
}
assert(L.sample(model,frame(0,0)).ready);
assert(!L.sample(model,frame(0,20)).rotationOK,'pure roll fails even with direction centered in cone');
assert(!L.sample(model,frame(0,0,2.01)).tipOK);assert(L.sample(model,frame(0,0,1.99)).tipOK);
assert(!L.sample(model,{...frame(0,0),body:{remainingDegrees:.1}}).ready);
assert(!L.sample({...model,o:{...model.o,sheathe:false}},frame(0,0)));
for(const phase of ['Held','Slide','FK return','Holstered'])assert(!L.sample(model,{...frame(0,0),phase}));
console.log('PASS: 48 swing/roll combinations, scaled tip, 2cm gate, body gate, phase visibility, finite geometry, no mutation.');
