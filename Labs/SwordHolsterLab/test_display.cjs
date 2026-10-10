// Compare the renderer against the independently validated original lab idle axes.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),R=require('./recovery.js');
const src=fs.readFileSync(__dirname+'/app.js','utf8');
const display=vm.runInNewContext('('+src.match(/function displayAxes\(q\)\{[^\n]+\}/)[0]+')',{R});
const data=JSON.parse(fs.readFileSync(__dirname+'/data/motions.json'));
const ref=JSON.parse(fs.readFileSync(__dirname+'/../AttackRecoveryLab/data/manifest.json'));
let error=0;
for(const [j,name] of data.names.entries()){
 const k=ref.names.indexOf(name);assert(k>=0);
 const actual=display(data.motions.idle.frames[0][j].slice(3)),expected=ref.sharedIdle.axes[k];
 actual.forEach((axis,a)=>axis.forEach((x,b)=>error=Math.max(error,Math.abs(x-expected[a][b]))));
}
// The original float32 FBX export differs by up to4.75e-6 on the toe bones.
assert(error<1e-5,`Renderer bone basis differs from accepted idle: ${error}`);
console.log(JSON.stringify({passed:true,bones:data.names.length,maxAxisComponentError:error}));
