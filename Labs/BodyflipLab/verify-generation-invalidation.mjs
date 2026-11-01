import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const C=createRequire(import.meta.url)('./core.js'),source=fs.readFileSync(new URL('app.js',import.meta.url),'utf8');
const fixture={settings:{mode:'jump',jumpEvents:[{id:'first',time:68/60,flip:350},{id:'second',time:133/60,flip:-200,twist:0,attack:'slashL'}]}};
let uiCalls=0;
const ctx=vm.createContext({C,settings:C.sanitize(fixture.settings),flight:{},loadingRun:false,playWanted:false,preparingRun:null,$(){uiCalls++;throw Error('No-op entered preparation UI');}});
vm.runInContext(source.slice(source.indexOf('// View/debug changes'),source.indexOf('function total()')),ctx);
vm.runInContext('preparedMotionKey=motionKey()',ctx);
const original=vm.runInContext('motionKey()',ctx);
await ctx.prepareRun({preserveTime:true});
for(const key of ['ghost','showCone','footTargets','handTargets','bicolor','skeleton','loop','trimLoop']){ctx.settings[key]=!ctx.settings[key];await ctx.prepareRun({preserveTime:true});}
ctx.settings.playbackSpeed=.5;ctx.settings.platformTranslucency=.85;ctx.settings.trimOut+=1;
await ctx.prepareRun({preserveTime:true});
assert.equal(vm.runInContext('motionKey()',ctx),original);
ctx.settings.jumpEvents=C.sanitize({jumpEvents:ctx.settings.jumpEvents.map(e=>({...e,time:+e.time.toFixed(3)}))}).jumpEvents;
await ctx.prepareRun({preserveTime:true});
assert.equal(uiCalls,0);
for(const change of [()=>ctx.settings.target[0]+=.1,()=>ctx.settings.jumpEvents[1].twist=30,()=>ctx.settings.legFollow+=.1]){
 ctx.settings=C.sanitize(fixture.settings);change();assert.notEqual(vm.runInContext('motionKey()',ctx),original);
}
ctx.preparingRun={promise:Promise.resolve()};ctx.loadingRun=true;vm.runInContext('preparingMotionKey=motionKey()',ctx);
await ctx.prepareRun({preserveTime:true});assert.equal(uiCalls,0);
console.log(JSON.stringify({passed:true,noOpRebuilds:uiCalls,checks:'unchanged motion, display-only edits, rounded frame time, coalesced pending request; real target/spin/follow changes invalidate'}));
