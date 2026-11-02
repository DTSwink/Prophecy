// Protocol/lifecycle test. The callback is a deterministic stub, not NN parity.
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),path=require('path');
const fixture=process.argv[2]||'Saved/Diagnostics/FootIKPort20261030-smoke/walk-flat.input.json';
const input=JSON.parse(fs.readFileSync(fixture,'utf8')),context=vm.createContext({Date});
vm.runInContext(fs.readFileSync('Content/FootIKLab/Runtime.js','utf8'),context);
const K=context.FootIKRequire('footik.js'),R=context.FootIKRequire('recovery.js'),run=K.decode(input.source,input.parents),call=value=>JSON.parse(context.FootIKNative.command(JSON.stringify(value)));
const checks=[],check=(name,value)=>{assert(value,name);checks.push(name);};
const floor={id:'unreal-floor',origin:[0,0,0],normal:[0,1,0],tangent:[1,0,0],bounds:[-100,100,-100,100]};
let calls=0;context.__footikNN=()=>{calls++;throw Error('External pose mode cannot infer');};
call({op:'init',source:input.source,parents:input.parents,settings:{...input.settings,terrain:'flat',enabled:true,slideEnabled:false},policy:false,root:{position:[12,0,-5],velocity:[2,0,0],normal:[0,1,0],yaw:90},surfaces:[floor]});
let result;for(let i=0;i<120;i++)result=call({op:'tick',pose:K.yawPose(K.at(run,i/120),90),ticks:1,travelVelocity:[2,0,0]});
check('external pose path performs no inference',calls===0);
check('arbitrary root origin is preserved',result.frame.root[0]>13.5&&Math.abs(result.frame.root[2]+5)<1e-8);
check('external live poses are finite',result.frame.pose.points.flat().every(Number.isFinite));
check('live history storage is bounded',call({op:'frames'}).length===8&&call({op:'status'}).frames===120);
call({op:'tick',pose:K.at(run,1),surfaces:[],surfaceRevision:1});
check('surface removal releases all material pins',call({op:'frames'}).at(-1).feet.every(f=>f.contact===null));
call({op:'close'});check('close removes the entire live session',call({op:'status'}).enabled===false);
const requests=[];let seed=run.poses[0];
context.__footikNN=json=>{const request=JSON.parse(json);requests.push(request);seed=request.seeds?.at(-1)||seed;const origin=seed.points[0],destination=request.roots[2];seed={points:seed.points.map(v=>R.add(destination,R.sub(v,origin))),axes:seed.axes};return JSON.stringify({pose:seed,pins:[0,0]});};
call({op:'init',source:input.source,parents:input.parents,settings:{...input.settings,terrain:'flat',enabled:true,slideEnabled:false},root:{position:[0,0,0],velocity:[0,0,2],normal:[0,1,0],yaw:0},surfaces:[floor]});
for(let i=0;i<60;i++){const time=i/120;result=call({op:'tick',travelVelocity:[0,0,2],futureRoots:Array.from({length:10},(_,j)=>({position:[0,0,(time+(j-1)/30)*2],yaw:(time+(j-1)/30)*60}))});}
check('native coupling invokes policy every4substeps',requests.length===14);
check('native coupling passes eight future yaw samples',requests.every(r=>r.rootYawDegrees.length>=10)&&requests.some(r=>Math.abs(r.rootYawDegrees[9]-r.rootYawDegrees[1])>5));
check('native policy receives actual root motion history',requests.every(r=>r.roots.length>=10)&&requests.some(r=>Math.abs(r.roots[1][2]-r.roots[0][2])>.01));
check('coupled live frame ring remains bounded',call({op:'frames'}).length===8&&call({op:'windows'}).length===10);
call({op:'close'});
const report={passed:true,checks,policyRequests:requests.length,finalRoot:result.frame.root};
const output='Saved/Diagnostics/FootIKPort20261030/live-adapter.json';fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
