'use strict';
// Capture original unbundled brace-fit calls, not native-kernel outputs. Binary
// float64 fixtures preserve signed zero and are generated only below Saved.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),assert=require('node:assert/strict');
const directory=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030');
const arg=(k,d)=>process.argv.find(x=>x.startsWith('--'+k+'='))?.slice(k.length+3)||d,name=arg('case','current-yaw-stop10'),kind=arg('kernel','arm'),entry=kind==='entry',leg=kind==='leg',finiteSlabs=process.argv.includes('--finite-slabs');
const armsPath=path.resolve(__dirname,'../../Labs/FootIKLab/'+(entry?'slide-entry.js':leg?'surface.js':'slide-arms.js')),contractPath=path.resolve(__dirname,entry?'native-entry-fit.cjs':leg?'native-leg-contact.cjs':'native-arm-fit.cjs');
let source=fs.readFileSync(armsPath,'utf8');
if(finiteSlabs){
 assert(entry||leg);const finite="a=>a.map((p,i)=>({...p,finiteSlab:true,box:{...p.box,dims:[1,i?.4:.08,1]}}))";
 if(entry){const needle=' const started=Date.now(),hip=';assert.equal(source.split(needle).length,2);source=source.replace(needle," const __originalSurfaces=surfaces,__finite="+finite+";surfaces=(...args)=>__finite(__originalSurfaces(...args));\n"+needle);}
 else{const needle='function createSlidePose(names,parents,terrain,s){';assert.equal(source.split(needle).length,2);source=source.replace(needle,needle+"\n const __originalTerrain=terrain,__finite="+finite+";terrain={...terrain,allSurfaces:__finite(terrain.allSurfaces),get surfaces(){return __finite(__originalTerrain.surfaces);},surfacesAt:t=>__finite(__originalTerrain.surfacesAt(t))};\n");}
}
const begin=entry?' let obstacleWeight=1000;':leg?'   const contactValid=p=>{':'   let best=fit(1);',end=entry?' inspect?.({nodes,evaluateGeometry,correct,project});':leg?'   targets.push({side,l,target:goal.points[l.foot],rotation:{footQ:goal.q[l.foot],toeQ:goal.q[l.toe]}});':'   // Commit history only after choosing a fit; trial candidates must not';
assert.equal(source.split(begin).length,2);assert.equal(source.split(end).length,2);
const records=[];global.__captureBraceFit=(input,output)=>records.push({input,output});
const capture=source.replace("'use strict';","'use strict';const __armContract=require("+JSON.stringify(contractPath)+");").replace(begin,entry?' const __armInput=__armContract.pack({nodes,quality,hip,knee,foot:joints.joints[l.foot],leg:l,surfaces});\n'+begin:leg?'   const __armInput=__armContract.pack({goal,l,parents,joints,rotation,point,wantedAxis,wantedPole,e,side,targetShift,previousPole,dt,plane,terrain});\n'+begin:'   const __armInput=__armContract.pack({pose,a,parents,joints,nearest,requestedPoint,n,wallUp,shoulderOut,reach,handQ});\n'+begin).replace(end,entry?' global.__captureBraceFit(__armInput,nodes.flatMap(c=>c.v));\n'+end:leg?'   global.__captureBraceFit(__armInput,__armContract.flatten(goal,l,e,side));\n'+end:'   global.__captureBraceFit(__armInput,__armContract.flatten(best,a));\n'+end);
const value=new Module(armsPath,module);value.filename=armsPath;value.paths=Module._nodeModulePaths(path.dirname(armsPath));value._compile(capture,armsPath);require.cache[armsPath]=value;
const K=require('../../Labs/FootIKLab/footik.js'),C=require('../../Labs/FootIKLab/surface-coupling.js');
async function main(){
 const input=JSON.parse(fs.readFileSync(path.join(directory,name+'.input.json'))),expected=JSON.parse(fs.readFileSync(path.join(directory,name+'.expected.json'))),run=K.decode(input.source,input.parents);
 const session=C.createSession(run,input.settings,(_,i)=>input.policySteps[i]);await session.extend(input.endTime??session.model.duration);
 const fields=f=>({pose:{points:f.pose.points,q:f.pose.q},root:f.root,feet:f.feet,surface:f.surface,slide:f.slide,pelvisOffset:f.pelvisOffset,influence:f.influence});
 assert.equal(session.model.frames.length,expected.frames.length);if(!finiteSlabs)for(let i=0;i<expected.frames.length;i++)assert.deepEqual(JSON.parse(JSON.stringify(fields(session.model.frames[i]))),JSON.parse(JSON.stringify(fields(expected.frames[i]))),'original frame'+i);session.close();
 const bytes=Buffer.alloc(16+records.reduce((n,r)=>n+(entry||leg?8:0)+(r.input.length+r.output.length)*8,0));bytes.write(entry?'FIKENT01':leg?'FIKLEG01':'FIKARM01',0,'ascii');bytes.writeUInt32LE(records.length,8);bytes.writeUInt16LE(entry||leg?0:96,12);bytes.writeUInt16LE(entry||leg?0:34,14);let at=16;
 for(const record of records){if(entry||leg){bytes.writeUInt32LE(record.input.length,at);bytes.writeUInt32LE(record.output.length,at+4);at+=8;}else{assert.equal(record.input.length,96);assert.equal(record.output.length,34);}for(const number of [...record.input,...record.output]){assert(Number.isFinite(number));bytes.writeDoubleLE(number,at);at+=8;}}
 const suffix=(finiteSlabs?'.finite-slabs':'')+(entry?'.entry-fit':leg?'.leg-contact':'.arm-fit'),file=path.join(directory,name+suffix+'.bin');fs.writeFileSync(file,bytes);const report={case:name,passed:true,finiteSlabs,originalFramesExact:!finiteSlabs,frames:expected.frames.length,records:records.length,inputDoubles:entry||leg?'variable':96,outputDoubles:entry||leg?'variable':34,bytes:bytes.length,file};fs.writeFileSync(path.join(directory,name+suffix+'.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
