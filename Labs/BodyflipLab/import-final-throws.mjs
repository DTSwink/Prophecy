// Import the user's final unaimed bake without editing live lab settings.
import fs from 'node:fs';import crypto from 'node:crypto';import assert from 'node:assert/strict';
const base=new URL('../../Exports/Throws/FinalNoAim/',import.meta.url),read=url=>JSON.parse(fs.readFileSync(url)),path=new URL('data/throws.json',import.meta.url),pkg=read(path),manifest=read(new URL('manifest.json',base)),clips=read(new URL('clips.json',base)),objects=read(new URL('../ThrowLab/data/objects.json',import.meta.url));
assert.deepEqual(clips.names,pkg.names);assert.deepEqual(clips.parents,pkg.parents);
for(const kind of ['spear','bomb'])assert(JSON.stringify(objects[kind])===JSON.stringify(pkg.assets[kind]),'geometry/physical package must match');
const sha256=Object.fromEntries(['clips.json','manifest.json'].map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(new URL(n,base))).digest('hex')]));pkg.finalNoAim={manifest,clips,sha256};pkg.sourceHash=sha256['clips.json'];fs.writeFileSync(path,JSON.stringify(pkg));console.log({imported:'Exports/Throws/FinalNoAim',sha256});
