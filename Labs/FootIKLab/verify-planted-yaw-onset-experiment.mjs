import fs from 'node:fs';
import path from 'node:path';
import Module,{createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),S=require('./support.js');
const file=path.resolve('Labs/FootIKLab/footik.js'),original=fs.readFileSync(file,'utf8');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const rig=read('data/rig.json'),source=read('snapshots/ankle-turn-second-source.json'),settings=read('snapshots/ankle-turn-second-settings.json');
const candidates={
 baseline:original,
 blend:original.replace('planned[i].targets[side][axis]=curve[i-lo]','planned[i].targets[side][axis]=original[i][axis]+(curve[i-lo]-original[i][axis])*footWeight(i,side)'),
 bounded:original.replace('planned[i].targets[side][axis]=curve[i-lo]','planned[i].targets[side][axis]=clamp(original[i][axis]+(curve[i-lo]-original[i][axis])*footWeight(i,side),floor[i-lo],ceiling[i-lo])'),
 corridor:original.replace('original[i][axis]-.025','original[i][axis]-.025*footWeight(i,side)').replace('original[i][axis]+.025','original[i][axis]+.025*footWeight(i,side)'),
};
const key=process.argv[2]||'blend',code=candidates[key];
if(!code)throw Error(key);
const mod=new Module(file);mod.filename=file;mod.paths=Module._nodeModulePaths(path.dirname(file));mod._compile(code,file);require.cache[file]=mod;
const K=mod.exports,m=K.prepare(K.decode(source,rig.parents),settings),deg=180/Math.PI;
const bend=(p,l)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(R.sub(p.points[l.knee],p.points[l.hip])),R.unit(R.sub(p.points[l.foot],p.points[l.knee]))))))*deg;
const rows=m.frames.slice(48,65).map((f,n)=>{const l=S.leg(f.raw,['root',...source.names],'L');return {frame:(n+48)/2,w:f.influence,bend:bend(f.pose,l),raw:bend(f.raw,l)};});
console.log(JSON.stringify({key,metrics:m.metrics,rows}));
if(process.argv.includes('--verify')){
 const originalWrite=fs.writeFileSync;
 fs.writeFileSync=(name,...args)=>{if(String(name).endsWith('/verification.json')||String(name).endsWith('\\verification.json'))name=new URL('snapshots/yaw-knee-onset-'+key+'-verification.json',import.meta.url);return originalWrite(name,...args);};
 await import('./verify.mjs');
}
