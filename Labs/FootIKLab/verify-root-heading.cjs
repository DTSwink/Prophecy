const fs=require('fs'),path=require('path'),z=require('zlib'),assert=require('assert/strict');
const K=require('./footik.js'),F=require('./surface.js'),R=require('./recovery.js');
const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(__dirname,'data/platforms-speed-fixture.json.gz'))));
const run=K.decode(fixture.data,JSON.parse(fs.readFileSync(path.join(__dirname,'data/rig.json'))).parents);
const settings=K.sanitize({...fixture.saved.settings,pinReleaseSpeed:1}),model=F.prepare(run,settings);
const checks=[],check=(name,value)=>{assert(value,name);checks.push(name);};
const near=(a,b)=>R.length(R.sub(a,b))<1e-10;
for(const [direction,expected] of Object.entries({forward:[0,0,1],left:[-1,0,0],backward:[0,0,-1],right:[1,0,0]}))
 check(direction+' controller heading',near(K.rootHeading({direction},0),expected));
check('positive yaw turns forward toward right',near(K.rootHeading({direction:'forward'},1,{rootYawSpeed:90},2),[1,0,0]));
check('negative yaw turns forward toward left',near(K.rootHeading({direction:'forward'},1,{rootYawSpeed:-90},2),[-1,0,0]));
check('heading freezes after distance stop',near(K.rootHeading({direction:'forward'},5,{rootYawSpeed:90,rootYawStart:2,rootYawStop:4},2),[1,0,0]));
check('heading remains unchanged before distance start',near(K.rootHeading({direction:'forward'},.5,{rootYawSpeed:90,rootYawStart:2},2),[0,0,1]));
const wrap={fps:30,direction:'forward',rootYawDegrees:[350,370]};
check('interpolates unwrapped yaw through a full turn',near(K.rootHeading(wrap,1/60),[0,0,1]));
check('actual generated yaw takes precedence over changed controls',near(K.rootHeading(wrap,1/60,{rootYawSpeed:-360},2),[0,0,1]));
let maxGhostPositionError=0,maxGhostRotationError=0,maxPelvisError=0,maxHeadError=0,maxArrowTiltError=0;
const rows=[],pelvis=run.names.indexOf('pelvis'),head=run.names.indexOf('head');
for(let i=0;i<model.frames.length;i++){
 const time=i/model.fps,frame=model.frames[i],source=K.at(run,time),q=frame.surface.bodyRotation;
 for(let j=0;j<run.names.length;j++){
  const expected=R.add(frame.root,R.rotate(q,R.sub(source.points[j],source.points[0])));
  maxGhostPositionError=Math.max(maxGhostPositionError,R.length(R.sub(expected,frame.raw.points[j])));
  const expectedQ=R.qm(q,source.q[j]);
  maxGhostRotationError=Math.max(maxGhostRotationError,R.length(R.qlog(R.qm(expectedQ,R.qinv(frame.raw.q[j])))));
 }
 maxPelvisError=Math.max(maxPelvisError,R.length(R.sub(frame.pose.points[pelvis],frame.raw.points[pelvis])));
 maxHeadError=Math.max(maxHeadError,R.length(R.sub(frame.pose.points[head],frame.raw.points[head])));
 const facing=R.rotate(q,K.rootHeading(run,time,settings,model.speed));
 maxArrowTiltError=Math.max(maxArrowTiltError,Math.abs(R.dot(facing,frame.surface.bodyUp)),Math.abs(R.length(facing)-1));
 if([0,90,120,143,150,165,180,208,300].includes(i/2)){
  const nnTravel=R.rotate(q,[0,0,model.speed]),yaw=run.directionMeta.facingDegrees+fixture.data.rootYawDegrees[Math.round(time*run.fps)];
  rows.push({frame:i/2,headingDegrees:yaw,heading:facing,rootVelocity:frame.surface.velocity,nnMappedTravel:nnTravel,travelAgreement:R.dot(R.unit(nnTravel),R.unit(frame.surface.velocity)),bodyTiltDegrees:Math.acos(frame.surface.bodyUp[1])*180/Math.PI});
 }
}
check('ghost is exactly the rigidly placed source NN at all 601 samples',maxGhostPositionError<1e-12&&maxGhostRotationError<1e-12);
check('main and ghost share pelvis and upper-body placement',maxPelvisError<1e-12&&maxHeadError<1e-12);
check('root arrow follows the body alignment but not animated pelvis lean',maxArrowTiltError<1e-12);
const current=rows.find(x=>x.frame===143);
check('reported frame has downward actual root velocity',current.rootVelocity[1]<-8);
check('source NN travel opposes actual travel during the fall',current.travelAgreement<-.6);
check('finished turn commands nearly backwards facing',current.headingDegrees>180&&current.headingDegrees<190);
fs.mkdirSync(path.join(__dirname,'snapshots'),{recursive:true});
fs.writeFileSync(path.join(__dirname,'snapshots/ghost-heading-verification.json'),JSON.stringify({passed:true,checks,maxGhostPositionError,maxGhostRotationError,maxPelvisError,maxHeadError,maxArrowTiltError,rows},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,maxGhostPositionError,maxGhostRotationError,current}));
