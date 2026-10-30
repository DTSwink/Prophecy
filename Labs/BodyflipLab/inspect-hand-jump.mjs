// Offline full timeline fixtures; never reads or changes the user's saved scene.
import fs from 'node:fs';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js'),S=require('./support.js'),F=require('./flight.js'),I=require('./idle.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),reference=C.poseFromShared(m),idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),m),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const caseName=process.argv[2]||'floor',moving=['walk','run'].includes(caseName),floor=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-5,5,-5,20],.4),wall=S.rectangle('wall',[0,0,.55],[1,0,0],[0,1,0],[-2,2,0,3],.15);
const run=moving?F.decodeNN(read('data/'+caseName+'-default.json')):idle.motion(),surface=caseName==='wall'?wall:floor;
const settings=C.sanitize({mode:caseName==='run'?'jump':caseName==='walk'?'walk':'idle',ramps:false,surfaceIK:false,supportAlpha:0,platforms:[S.platformRecord(floor),...(caseName==='wall'?[S.platformRecord(wall)]:[])],jumpEvents:[{id:'hand',time:.1,pushWith:'hand'}]});
const started=performance.now(),sequence=F.sequence(run,jumps,settings,m.parents,reference),segment=sequence.segments[0];
const frames=Array.from({length:121},(_,i)=>({time:i/60,...sequence.sample(i/60)}));
fs.writeFileSync('Saved/BodyflipLab/HandJump/'+caseName+'-poses.json',JSON.stringify({names:m.names,parents:m.parents,frames,surface:{origin:surface.origin,u:surface.u,v:surface.v,bounds:surface.bounds},side:segment.supportFoot,bone:segment.supportBone,timing:{contact:segment.contactTime,jump:segment.jumpStart,release:segment.airStart}}));
console.log({caseName,ms:performance.now()-started,events:sequence.events,landings:sequence.landings});
