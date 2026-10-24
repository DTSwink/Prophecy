import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('./flight.js'),C=require('./core.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),jumps=read('data/jumps.json').clips.map(F.decodeJump),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
check('Walk mode persists',C.sanitize({mode:'walk'}).mode==='walk');
for(const drawn of [false,true]){
 const data=read('data/walk-default'+(drawn?'-drawn':'')+'.json'),run=F.decodeNN(data),make=extra=>F.create(run,jumps,{...C.defaults,mode:'walk',...extra},m.parents,C.poseFromShared(m));
 const f=make({});
 check('Actual walking NN '+drawn,data.gait==='walk'&&data.source.includes('Walk July5')&&Math.abs(f.speed-2)<.001);
 check('Walk phase and moving root '+drawn,f.sample(.5).phase==='WALK'&&Math.abs(f.sample(.5).root[2]-1)<.001);
 check('Auto reaches takeoff at default foot speed '+drawn,Number.isFinite(f.jumpStart)&&f.support.terminal.distance<=.05);
 check('Finite capped fall '+drawn,f.sample(20).vy===-20&&f.sample(20).pose.points.flat().every(Number.isFinite));
 const r=make({jumpFoot:'R',supportSpeed:300});
 check('Manual right support at 300 cm/s '+drawn,r.supportFoot==='R'&&Number.isFinite(r.jumpStart)&&r.start.endsWith('Rfoot'));
 const slow=make({supportSpeed:300,supportAlpha:.03});
 check('Missed contact still aborts '+drawn,slow.jumpStart===Infinity&&slow.failureReason==='Distance growing');
 const before=JSON.stringify(f.sample(1.1));f.sample(20);f.sample(0);
 check('Arbitrary replay is deterministic '+drawn,JSON.stringify(f.sample(1.1))===before);
}
fs.writeFileSync(new URL('walk-verification.json',import.meta.url),JSON.stringify({passed:true,checks},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length}));
