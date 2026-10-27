import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createProjectileSystem} from './projectile.js';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),V=require('./vanilla.js'),S=require('./scenes.js');
const dir=path.dirname(fileURLToPath(import.meta.url)),data=JSON.parse(fs.readFileSync(path.join(dir,'data/clips.json'))),assets=JSON.parse(fs.readFileSync(path.join(dir,'data/objects.json'))),hand=data.names.indexOf('hand_l');
const near=(a,b,tol=1e-6)=>assert(R.length(R.sub(a,b))<tol,JSON.stringify({a,b}));
// Integer-only migration, collision handling and idempotence.
const legacy=[{frame:10.2,rotation:[20,40,60]},{frame:10,rotation:[5,6,7]},{frame:11.4,rotation:[40,50,60]},{frame:11.1,rotation:[10,20,30]}];
const normalized=V.wholeFrameKeys(legacy);
assert.deepEqual(normalized,[{frame:10,rotation:[5,6,7]},{frame:11,rotation:[10,20,30]}]);
assert.deepEqual(V.wholeFrameKeys(normalized),normalized);
for(const keyFrame of [0,10,68]){
 const k=[{frame:keyFrame,rotation:[20,40,60]}];assert.deepEqual(V.anglesAt(k,keyFrame),[20,40,60]);
 for(const frame of [keyFrame-1,keyFrame+1,keyFrame+10])assert.deepEqual(V.anglesAt(k,frame),[0,0,0]);
}
const sameRotation=(a,b)=>assert(Math.abs(R.dot(V.rotation(a),V.rotation(b)))>1-1e-9);
sameRotation(V.anglesAt([{frame:10,rotation:[0,0,170]},{frame:11,rotation:[0,0,-170]}],10.5),[0,0,180]);
sameRotation(V.anglesAt([{frame:10,rotation:[0,0,350]}],10.5),[0,0,-5]);
assert.deepEqual(V.anglesAt([{frame:10,rotation:[20,40,60]},{frame:20,rotation:[40,80,120]}],15.5),[0,0,0]);
// Saved problem case: one continuous shortest arc in every interval, with no
// hidden subframe targets; explicit integer poses survive migration exactly.
const oldKeys=JSON.parse(fs.readFileSync(path.join(dir,'fixtures/whole-frame-forearm-keys.json'))),newKeys=V.wholeFrameKeys(oldKeys);
assert.equal(oldKeys.length,25);assert.equal(newKeys.length,14);
for(const k of oldKeys.filter(k=>Math.abs(k.frame-Math.round(k.frame))<1e-7))assert.deepEqual(newKeys.find(n=>n.frame===Math.round(k.frame)).rotation,k.rotation);
for(let f=19;f<34;f++)for(let i=0;i<=100;i++){
 const a=V.rotation(V.anglesAt(newKeys,f)),b=V.rotation(V.anglesAt(newKeys,f+1)),q=V.rotation(V.anglesAt(newKeys,f+i/100));
 assert(Math.abs(R.dot(q,R.qslerp(a,b,i/100)))>1-1e-9);
}
for(const baseAngles of [[0,0,0],[30,-80,120]])for(const axis of [[1,0,0],[0,1,0],[0,0,1],R.unit([2,3,4])])for(const degree of [-170,-45,0,25,170]){
 const base=V.rotation(baseAngles),edited=R.qm(R.qexp(R.mul(axis,degree*Math.PI/180)),base);
 assert(Math.abs(V.axisOffsetDegrees(base,edited,axis)-degree)<1e-8);
 assert(Math.abs(V.axisOffsetDegrees(base,edited.map(v=>-v),axis)-degree)<1e-8);
}
assert.equal(V.axisOffsetDegrees([0,0,0,1],V.rotation([180,0,0]),[0,1,0]),null);
// World gizmo edits must remain world rotations with a rotated arm and near
// Euler singularities, while round-tripping through existing local key storage.
for(const baseAngles of [[0,0,0],[-50,100,15]])for(const initial of [[20,30,40],[30,90,-20],[20,-90,110],[400,120,-300],[20,89.999999,45]])for(let axis=0;axis<3;axis++){
 const base=V.rotation(baseAngles);let previous=initial;
 for(let degree=-360;degree<=360;degree+=15){const radians=degree*Math.PI/180,turn=[0,0,0];turn[axis]=radians;const edited=V.rotateWorld(base,initial,axis,radians,previous),expected=R.qm(R.qexp(turn),R.qm(base,V.rotation(initial))),actual=R.qm(base,V.rotation(edited));assert(Math.abs(R.dot(expected,actual))>1-1e-9);previous=edited;}
}

for(const raw of data.clips){
 const clip=C.decode(raw,data.parents),arm=data.names.indexOf('lowerarm_l'),parent=data.parents[arm],keys=[{frame:10,rotation:[25,-30,40]}];
 for(const f of [5.25,10.5,20.25]){
  const source=C.sample(clip,f/60,data.parents),edited=V.pose(source,data.parents,arm,keys,f,true),turn=R.qm(R.qm(source.q[parent],V.rotation(V.anglesAt(keys,f))),R.qinv(source.q[parent]));
  near(edited.points[arm],source.points[arm]);assert(Math.abs(R.dot(edited.q[arm],R.qm(turn,source.q[arm])))>1-1e-10);
  near(edited.points[hand],R.add(source.points[arm],R.rotate(turn,R.sub(source.points[hand],source.points[arm]))));
  for(let j=0;j<data.names.length;j++){let ancestor=j;while(ancestor>=0&&ancestor!==arm)ancestor=data.parents[ancestor];if(ancestor!==arm){assert.deepEqual(edited.points[j],source.points[j]);assert.deepEqual(edited.q[j],source.q[j]);}}
 }
}
const baseV=[2,3,4],baseW=[5,6,7],root=V.rotation([10,30,0]),q=V.rotation([10,0,60]),axis=R.unit([1,2,3]),controls=V.config({velocityRotation:[20,-30,5],speedScale:2,twist:-3.5});
const launch=V.launch(baseV,baseW,q,root,axis,controls),worldTurn=V.rotation([0,70,0]),turned=V.launch(R.rotate(worldTurn,baseV),R.rotate(worldTurn,baseW),R.qm(worldTurn,q),R.qm(worldTurn,root),axis,controls);
near(turned.velocity,R.rotate(worldTurn,launch.velocity));near(turned.omega,R.rotate(worldTurn,launch.omega));assert(Math.abs(R.length(launch.velocity)-2*R.length(baseV))<1e-9);near(R.cross(launch.omega,launch.axis),[0,0,0]);
const sim=await createProjectileSystem(assets,R,V),receipt={checks:['World hand rotations preserve local keys across rotated arm bases, multiple turns and Euler singularities','Frame-local rotation edits, unedited neighbors/gaps, shortest-arc interpolation without subframe targets or tail hold, root-relative velocity rotation covariance'],cases:[]};
try{
 for(const raw of data.clips)for(const kind of ['sword','bomb']){
  const clip=C.decode(raw,data.parents),releaseFrame=raw.id==='big-throw'?33.25:15.75,release=releaseFrame/60,c=V.config({armed:10.125,keys:[{frame:0,rotation:[0,0,0]},{frame:releaseFrame,rotation:[20,-15,40]}],speedScale:1.4,velocityRotation:[0,30,0],twist:2.25},clip.duration*60,releaseFrame);
  const sample=t=>V.pose(C.sample(clip,t,data.parents),data.parents,hand,c.keys,t*60),source=C.sample(clip,release,data.parents),edited=sample(release);
  near(edited.points[hand],source.points[hand]);assert(Math.abs(R.dot(edited.q[hand],R.qm(source.q[hand],V.rotation(V.anglesAt(c.keys,releaseFrame)))))>1-1e-9);
  for(let j=0;j<data.names.length;j++){let ancestor=j;while(ancestor>=0&&ancestor!==hand)ancestor=data.parents[ancestor];if(ancestor!==hand){assert.deepEqual(edited.q[j],source.q[j]);assert.deepEqual(edited.points[j],source.points[j]);}}
  const o={key:raw.id,kind,release,sample,hand,duration:clip.duration,target:[0,1.5,3],radius:.16,controls:c};
  assert.equal(sim.at(release-.00001,o).phase,'held');assert.equal(sim.diagnostics.steps,0);
  const seed=sim.preview(o);assert.equal(sim.diagnostics.steps,0);near(R.cross(seed.omega,seed.axis),[0,0,0]);assert(Math.abs(R.dot(seed.omega,seed.axis)-2.25*60*Math.PI/180)<1e-9);assert(Math.abs(R.length(seed.v)-1.4*R.length(seed.authoredVelocity))<1e-9);
  near(sim.at(release,o).p,R.add(edited.points[hand],R.rotate(edited.q[hand],assets[kind].bind?.position||[0,0,0])));const airborne=sim.at(release+.25,o);sim.at(0,o);assert.deepEqual(sim.at(release+.25,o),airborne);
  c.twist=0;near(sim.preview(o).omega,[0,0,0]);near(sim.at(release,o).omega,[0,0,0]);
  const settings=C.sanitize({clip:raw.id,releases:{[raw.id]:release},vanilla:{[raw.id]:c}}),saved={settings,playback:{time:release,playing:false}},library=S.open(saved),copy=S.copy(library,'copy','copy');
  assert.deepEqual(S.pack(copy).settings,settings);assert.equal(C.sanitize(settings).releases[raw.id]*60,releaseFrame);
  receipt.cases.push({clip:raw.id,kind,armedFrame:c.armed,releaseFrame,axis:seed.axis,twistDegreesPerFrame:seed.twist});
 }
 receipt.checks.push('Both clips/objects: fractional pose/release, hand-only edits, twist-only launch, rotated/scaled animation velocity, zero twist, cache invalidation, exact replay and scene persistence');receipt.success=true;
 fs.writeFileSync(path.resolve(dir,'../../Saved/ThrowLab/vanilla-verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt,null,2));
}finally{sim.dispose();}
