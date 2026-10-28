/* Stage-by-stage diagnostic only: instrument a private in-memory module. */
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const R=require('./recovery.js'),K=require('./footik.js');
const read=name=>JSON.parse(fs.readFileSync(path.join(__dirname,name),'utf8'));
const filename=path.join(__dirname,'surface.js');let code=fs.readFileSync(filename,'utf8');
code=code.replace('let contact=null;',`const debug={captureFrom,fitted:fitted.target,captureDistance,reach,captureRadius,stance:stance[side],sourceTarget:baseline.points[l.foot],sourceHip:pose.points[l.hip],upper:l.upper,lower:l.lower,pinAt:state.pin?.id};let contact=null;`);
code=code.replace('metrics.maxRequestedReachExcess=', 'debug.beforeFilter=target;debug.rollAngle=state.pin?.angle;metrics.maxRequestedReachExcess=');
code=code.replace('let solved=solveTarget(target,rotation);','debug.afterFilter=target;let solved=solveTarget(target,rotation);');
code=code.replace('feet.push({side:l.side,','feet.push({debug,side:l.side,');
const mod=new Module(filename,module);mod.filename=filename;mod.paths=module.paths;mod._compile(code,filename);
const source=process.argv[2]==='export'?'model-viewer-walkf-source.json':'flat-rollout-corrected-source.json',run=K.decode(read('snapshots/'+source),read('data/rig.json').parents);
const model=mod.exports.prepare(run,read('snapshots/flat-rollout-current-state.json').settings);
const from=Number(process.argv[3]??104),to=Number(process.argv[4]??108),side=Number(process.argv[5]??0);
for(let tick=from*2;tick<=to*2;tick++){
 const frame=model.frames[tick],f=frame.feet[side],d=f.debug,hip=d.sourceHip;
 const dist=p=>R.length(R.sub(p,hip)),degrees=p=>Math.acos(Math.max(-1,Math.min(1,(dist(p)**2-d.upper**2-d.lower**2)/(2*d.upper*d.lower))))*180/Math.PI;
 console.log(JSON.stringify({frame:tick/2,state:f.state,vy:frame.surface.velocity[1],massY:frame.surface.mass[1],...d,
  flex:Object.fromEntries(['sourceTarget','captureFrom','fitted','beforeFilter','afterFilter'].map(k=>[k,degrees(d[k])])),
  events:model.events.filter(e=>e.frame===tick/2)}));
}
