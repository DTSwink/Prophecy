import fs from 'node:fs';
import path from 'node:path';
import Module,{createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),S=require('./support.js');
const file=path.resolve('Labs/FootIKLab/footik.js'),original=fs.readFileSync(file,'utf8');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const rig=read('data/rig.json'),source=read('snapshots/ankle-turn-second-source.json'),settings=read('snapshots/ankle-turn-second-settings.json');
function compile(code){const m=new Module(file);m.filename=file;m.paths=Module._nodeModulePaths(path.dirname(file));m._compile(code,file);return m.exports;}
const stages=[
 ['initial',' // Small look-ahead envelope prepares the pelvis'],
 ['reach',' // Reach projection can move a swing toe'],
 ['anticipate',' // A finite tread edge can remove'],
 ['descent',' // Plan rising swings from a retained'],
 ['trajectory',' // One final constrained trajectory fit'],
 ['finalfit',' // Keep the root on its navigation ramp'],
 ['pelvis',' // A solved calf'],
];
let code=original.replace('const planned=[],metrics=','const debug=[]; const planned=[],metrics=');
for(const [stage,marker] of stages)if(code.includes(marker))code=code.replace(marker,`debug.push({stage:'${stage}',rows:planned.slice(48,65).map((p,n)=>({i:n+48,w:weights[n+48],root:base[n+48].points[0],hip:base[n+48].points[legs[n+48][0].hip],raw:base[n+48].points[legs[n+48][0].foot],p:JSON.parse(JSON.stringify(p))}))});\n${marker}`);
code=code.replace('return {frames,terrain,settings,metrics','return {debug,frames,terrain,settings,metrics');
const K=compile(code),m=K.prepare(K.decode(source,rig.parents),settings);
const deg=180/Math.PI;
function angle(p,l){return Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(R.sub(p.points[l.knee],p.points[l.hip])),R.unit(R.sub(p.points[l.foot],p.points[l.knee]))))))*deg;}
const rows=m.frames.slice(48,65).map((f,n)=>{const l=S.leg(f.raw,source.names.map?['root',...source.names]:[], 'L');return {frame:(n+48)/2,w:f.influence,hip:f.pose.points[l.hip],rawHip:f.raw.points[l.hip],target:f.feet[0].target,actual:f.pose.points[l.foot],rawFoot:f.raw.points[l.foot],bend:angle(f.pose,l),rawBend:angle(f.raw,l),rawFloor:m.terrain.floorFor(f.raw.points[l.foot],S.footPoints(f.raw,l.foot,l.toe,'L'))-f.raw.points[l.foot][1]};});
fs.writeFileSync(new URL('snapshots/yaw-knee-onset-debug.json',import.meta.url),JSON.stringify({stages:m.debug,rows},null,2));
console.log(JSON.stringify({stages:m.debug.map(s=>({stage:s.stage,row:s.rows.find(r=>r.i===52)})),rows},null,2));
