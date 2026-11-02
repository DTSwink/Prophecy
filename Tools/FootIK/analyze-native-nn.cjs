'use strict';
// Read-only analysis of actual Unreal NN/solver captures. No inference process.
const fs=require('node:fs'),path=require('node:path'),R=require('../../Labs/FootIKLab/recovery.js');
const directory=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030'),file=name=>path.join(directory,name),filter=process.argv.find(a=>a.startsWith('--case='))?.slice(7);
const read=name=>JSON.parse(fs.readFileSync(name,'utf8').replace(/^\uFEFF/,'')),lines=name=>fs.readFileSync(name,'utf8').split(/\r?\n/).filter(x=>x.trim()).map(x=>JSON.parse(x.replace(/^\uFEFF/,'')));
const summary=read(file('native-nn-closed-loop-diagnostic.json')),reports=[];
const requestedOracle=process.argv.find(a=>a.startsWith('--oracle-dir='))?.slice(13),oracle=path.resolve(directory,requestedOracle||summary.oracleDirectory||'.');
const distance=(a,b)=>Math.hypot(...a.map((x,i)=>x-b[i]));
function scalarDifference(a,b,p='',out={max:0,path:'',first:null,shape:null}){
 if(typeof b==='number'){if(typeof a!=='number'){out.shape??=p;return out;}const d=Math.abs(a-b);if(d>0&&out.first===null)out.first=p;if(d>out.max){out.max=d;out.path=p;}return out;}
 if(!b||typeof b!=='object'){if(a!==b)out.shape??=p;return out;}
 if(!a||typeof a!=='object'){out.shape??=p;return out;}
 if(Array.isArray(b)&&a.length!==b.length)out.shape??=p+'.length';for(const k of Object.keys(b))scalarDifference(a[k],b[k],p+'.'+k,out);return out;
}
const key=c=>c?String(c.surface??'contact'):'none';
for(const c of summary.cases){
 if(filter&&!new RegExp(filter).test(c.name))continue;
 const suffix=c.nativeSourceInitialization?'-native-source':'-recorded-source',prefix=file('native-nn-captures/'+c.name+suffix);
 if(!fs.existsSync(prefix+'.frames.jsonl')){reports.push({name:c.name,nativeSource:c.nativeSourceInitialization,missingCapture:true});continue;}
 const expected=read(path.join(oracle,c.name+'.expected.json')),input=read(path.join(oracle,c.name+'.input.json')),names=expected.requests[0]?.names||[],parents=input.parents;
 const output={name:c.name,nativeSource:c.nativeSourceInitialization,frames:0,firstPoseChange:null,firstSemantic:null,semanticDifferences:0,maxRootM:0,maxRootRelativeM:0,maxBodyRelativeM:0,maxFootTargetM:0,maxContactPointM:0,worstBodyRelative:null,bones:names.map((name,bone)=>({bone,name,maxWorldM:0,maxBodyRelativeM:0,frame120Hz:-1})),requests:[],responses:[]};
 const semantic=(frame,field,a,b)=>{if(a===b)return;output.semanticDifferences++;output.firstSemantic??={frame120Hz:frame,field,actual:a,expected:b};};
 for(const batch of lines(prefix+'.frames.jsonl'))for(let j=0;j<batch.frames.length;j++){
  const i=batch.start+j,a=batch.frames[j],e=expected.frames[i];if(!e)throw Error('Unexpected frame '+i);output.frames++;
  output.maxRootM=Math.max(output.maxRootM,distance(a.root,e.root));
  const inverseA=R.qinv(a.surface.bodyRotation),inverseE=R.qinv(e.surface.bodyRotation);
  for(let b=0;b<e.pose.points.length;b++){
   const world=distance(a.pose.points[b],e.pose.points[b]),ra=R.sub(a.pose.points[b],a.root),re=R.sub(e.pose.points[b],e.root),relative=distance(ra,re),body=distance(R.rotate(inverseA,ra),R.rotate(inverseE,re));
   if(world>0)output.firstPoseChange??={frame120Hz:i,bone:b,name:names[b],distanceM:world};
   output.maxRootRelativeM=Math.max(output.maxRootRelativeM,relative);if(body>output.maxBodyRelativeM){output.maxBodyRelativeM=body;output.worstBodyRelative={frame120Hz:i,bone:b,name:names[b],distanceM:body};}
   const bone=output.bones[b]||={bone:b,name:String(b),maxWorldM:0,maxBodyRelativeM:0,frame120Hz:-1};bone.maxWorldM=Math.max(bone.maxWorldM,world);if(body>bone.maxBodyRelativeM){bone.maxBodyRelativeM=body;bone.frame120Hz=i;}
  }
  semantic(i,'surface.mode',a.surface.mode,e.surface.mode);semantic(i,'surface.slide',!!a.surface.slide,!!e.surface.slide);semantic(i,'feet.length',a.feet.length,e.feet.length);
  for(let side=0;side<e.feet.length;side++){
   const af=a.feet[side],ef=e.feet[side],p='feet.'+ef.side;semantic(i,p+'.state',af?.state,ef.state);if(!af)continue;
   if(af.target&&ef.target)output.maxFootTargetM=Math.max(output.maxFootTargetM,distance(af.target,ef.target));
   for(const field of['contact','slideContact']){semantic(i,p+'.'+field,key(af[field]),key(ef[field]));if(af[field]?.point&&ef[field]?.point)output.maxContactPointM=Math.max(output.maxContactPointM,distance(af[field].point,ef[field].point));}
  }
 }
 for(const call of lines(prefix+'.nn.jsonl')){
  const request=expected.requests[call.index],response=input.policySteps?.[call.index];
  output.requests.push({index:call.index,expectedPolicyFrame:expected.windows[call.index]?.frame,...(request?scalarDifference(call.request,request):{unexpected:true})});
  output.responses.push({index:call.index,...(response&&call.response?scalarDifference(call.response,response):{unavailable:true,error:call.error})});
 }
 output.semanticAgreement=output.semanticDifferences===0;reports.push(output);console.log(JSON.stringify({...output,bones:undefined,requests:undefined,responses:undefined}));
}
const report={schema:'footik-native-nn-analysis-v1',oracleDirectory:oracle,continuousToleranceAccepted:false,note:'No continuous-error acceptance threshold is inferred. Inspect exact semantic changes and the first request/response divergence.',cases:reports};
fs.writeFileSync(file(requestedOracle?'native-nn-analysis-current.json':'native-nn-analysis.json'),JSON.stringify(report,null,2));
if(reports.some(r=>r.missingCapture||!r.semanticAgreement))process.exitCode=1;
