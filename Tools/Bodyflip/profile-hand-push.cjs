// Bounded CPU-profile fixture; invoke with node --max-old-space-size=384 --cpu-prof.
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const directory='Saved/Diagnostics/BodyflipPort20261030/v8-parity',out=path.join(directory,'hand-profile');
fs.mkdirSync(out,{recursive:true});
const runtime=fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8'),fixture=fs.readFileSync(path.join(directory,'native-hands.js'),'utf8');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const began=performance.now(),cpu=process.cpuUsage();let output;
const context=vm.createContext({Date,readFile:p=>fs.readFileSync(p,'utf8'),print:s=>{output=JSON.parse(s);}});
vm.runInContext(runtime,context,{filename:'BodyflipRuntime.js',timeout:20000});
vm.runInContext(fixture,context,{filename:'native-hands.js',timeout:180000});
assert.deepStrictEqual(output,JSON.parse(fs.readFileSync(path.join(directory,'native-hands-expected.json'),'utf8')));
assert.equal(hash(fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8')),hash(runtime),'Runtime changed during profile');
const used=process.cpuUsage(cpu),usage=process.resourceUsage(),summary={passed:true,runtimeSha256:hash(runtime),frames:output.frames.length,cpuMs:(used.user+used.system)/1000,wallMs:performance.now()-began,peakBytes:usage.maxRSS*1024};
fs.writeFileSync(path.join(out,'baseline-frames.json'),JSON.stringify(output));
fs.writeFileSync(path.join(out,'baseline-summary.json'),JSON.stringify(summary,null,2));
console.log(JSON.stringify(summary));
