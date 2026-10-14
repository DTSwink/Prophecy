// Frozen moving-input regression cases, evaluated through the current lab.
const fs=require('fs'),path=require('path'),lab=path.resolve(__dirname,'../../Labs/SwordHolsterLab'),F=require(lab+'/fkreturn');
const out=path.resolve(__dirname,'../../Saved/Diagnostics/ElbowIKRestore20261014');fs.mkdirSync(out,{recursive:true});
const fixtures=[...require(lab+'/diagnostics/elbow-return-regressions.json'),...require(lab+'/diagnostics/elbow-ik-return-regressions.json')],cases=[];
for(const c of fixtures)for(const worldInertia of [false,true])for(const springReturn of [false,true])for(const enabled of [false,true])for(const handInertia of [false,true]){
 const profile=F.sanitize({...c.input.profile,elbowIKCorrection:enabled,elbowSoftZone:15,worldInertia,springReturn,inertia:handInertia?.5:.7});
 const input={...c.input,profile,handInertia},ret=F.prepare(input),id=cases.length;
 fs.writeFileSync(out+'/profile-'+id+'.json',JSON.stringify({parameters:{drawReturn:profile,sheatheReturn:profile}}));
 cases.push({id,input,duration:ret.timing.duration,frames:c.frames.map(f=>({time:(f.tick-c.release)/60,base:f.base,expected:F.sample(ret,f.base,(f.tick-c.release)/60)}))});
}
fs.writeFileSync(out+'/oracle.json',JSON.stringify({cases}));console.log('Exported',cases.length,'return variants');
