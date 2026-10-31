// Test-only module loader: current source, no Content writes or packaging.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
export function sourceRuntime(){
 const base=path.resolve('Labs/BodyflipLab'),sources=new Map(),id=p=>path.relative(path.resolve('Labs'),p).replaceAll('\\','/');
 function gather(file){file=path.resolve(file);if(sources.has(file))return;const code=fs.readFileSync(file,'utf8');sources.set(file,code);for(const m of code.matchAll(/require\(['"]([^'"]+)['"]\)/g))if(m[1].startsWith('.')&&fs.existsSync(path.resolve(path.dirname(file),m[1])))gather(path.resolve(path.dirname(file),m[1]));}
 for(const file of ['flight.js','attack-aim.js','idle.js','throw-attack.js','target-rig.js','rig-profile.js'])gather(path.join(base,file));
 const factories=[...sources].map(([file,code])=>JSON.stringify(id(file))+':function(module,exports,require){\n'+code+'\n}');
 const runtime=`globalThis.structuredClone ||= v=>{if(v===null||typeof v!=='object')return v;if(Array.isArray(v))return v.map(structuredClone);const out={};for(const k of Object.keys(v))out[k]=structuredClone(v[k]);return out;};globalThis.BodyflipRequire=(function(){const factories={${factories.join(',\n')}},cache={};function load(id){if(cache[id])return cache[id].exports;const f=factories[id];if(!f)throw Error('Unknown test module '+id);const m={exports:{}};cache[id]=m;f(m,m.exports,name=>{const p=id.split('/');p.pop();for(const q of name.split('/')){if(q==='..')p.pop();else if(q!=='.')p.push(q);}return load(p.join('/'));});return m.exports;}return load;})();`;
 return {runtime,hashes:Object.fromEntries([...sources].map(([file,code])=>[id(file),crypto.createHash('sha256').update(code).digest('hex')]))};
}
