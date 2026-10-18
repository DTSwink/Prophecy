"""Build only the standalone reach DLL. Never builds, closes, or alters Unreal."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'bin';OUT.mkdir(exist_ok=True)
source=ROOT/'Source/GameAnimationSample3/Private/ProphecyDoubleReachAnimInstance.cpp'
s=source.read_text(encoding='utf-8-sig')
core=s[s.index('namespace ProphecyDoubleReach\n'):s.index('FCompactPoseBoneIndex ResolveCompactBoneIndex')]+'}\n'
step=s[s.index('bool ProphecyNativeReach::Step('):s.index('class FProphecyDoubleReachAnimInstanceProxy')]
parser=argparse.ArgumentParser();parser.add_argument('--import-unreal',action='store_true',help='Explicitly replace the lab solver with the current Unreal baseline');parser.add_argument('--output-dir',type=Path,help='Stage DLL and metadata without replacing the running lab');args=parser.parse_args()
if args.output_dir:OUT=args.output_dir.resolve();OUT.mkdir(parents=True,exist_ok=True)
solver=HERE/'solver.inl';origin=HERE/'origin.json'
if not solver.exists() or args.import_unreal:
 solver.write_text(core+step,encoding='utf-8')
 origin.write_text(json.dumps({'source':str(source.relative_to(ROOT)),'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'importedSolverSha256':hashlib.sha256((core+step).encode()).hexdigest()},indent=2),encoding='utf-8')
baseline=json.loads(origin.read_text(encoding='utf-8'));kernel=solver.read_text(encoding='utf-8')
# Fresh Unreal imports have no lab posture tuning; retain the lab ABI while
# leaving their original computation unchanged until an experiment adds it.
compiled_kernel=kernel.replace('TArray<FTransform>& Output, double Dt)', 'TArray<FTransform>& Output, double Dt, double ElbowDownBlend)')
code='#include "'+(HERE/'math_compat.h').as_posix()+'"\n'+compiled_kernel+'''
extern "C" __declspec(dllexport) int reach_step_blend(const double* base,const double* targets,const float* speeds,int mode,double* state,double* output,double elbowDownBlend) {
 FTransform pose[26];for(int i=0;i<26;++i){const double* p=base+i*7;pose[i].P={p[0],p[1],p[2]};pose[i].Q={p[3],p[4],p[5],p[6]};}
 ProphecyNativeReach::FState st;for(int i=0;i<6;++i)st.Body[i]=state[i];
 FVector request[2];float speed[2];for(int k=0;k<2;++k){int t=6+k*3,e=12+k*3;st.Targets[k]={state[t],state[t+1],state[t+2]};st.Elbows[k]={state[e],state[e+1],state[e+2]};st.Active[k]=state[18+k]!=0;request[k]={targets[k*3],targets[k*3+1],targets[k*3+2]};speed[k]=speeds[k];}
 TArray<FTransform> out;if(!ProphecyNativeReach::Step({pose,26},static_cast<EProphecyDoubleReachMode>(mode),request,speed,st,out,1./60.,elbowDownBlend))return 0;
 for(int i=0;i<6;++i)state[i]=st.Body[i];for(int k=0;k<2;++k){int t=6+k*3,e=12+k*3;auto v=st.Targets[k],w=st.Elbows[k];state[t]=v.X;state[t+1]=v.Y;state[t+2]=v.Z;state[e]=w.X;state[e+1]=w.Y;state[e+2]=w.Z;state[18+k]=st.Active[k];}
 for(int i=0;i<26;++i){auto p=out[i].P;auto q=out[i].Q;double* d=output+i*7;d[0]=p.X;d[1]=p.Y;d[2]=p.Z;d[3]=q.X;d[4]=q.Y;d[5]=q.Z;d[6]=q.W;}return 1;
}
extern "C" __declspec(dllexport) int reach_step(const double* base,const double* targets,const float* speeds,int mode,double* state,double* output) {
 return reach_step_blend(base,targets,speeds,mode,state,output,1.0);
}
'''
(OUT/'kernel.cpp').write_text(code,encoding='utf-8')
vc=Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
cmd=OUT/'build.cmd';cmd.write_text('@echo off\ncall "'+str(vc)+'" >nul\nif errorlevel 1 exit /b 1\ncl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /LD kernel.cpp /Fe:reach.dll /link /INCREMENTAL:NO\n',encoding='utf-8')
subprocess.run(['cmd.exe','/c',str(cmd)],cwd=OUT,check=True)
names=re.findall(r'TEXT\("([a-z0-9_]+)"\)',kernel.split('using FJointPositions')[0])
motions=json.loads((ROOT/'Labs/SwordHolsterLab/data/motions.json').read_text(encoding='utf-8'))
ids=[motions['names'].index(n) for n in names]
parents=[-1 if motions['parents'][i]<0 else names.index(motions['names'][motions['parents'][i]]) for i in ids]
base=[motions['motions']['idle']['frames'][0][i] for i in ids]
data={'names':names,'parents':parents,'base':base,'sourceAnimation':motions['motions']['idle']['asset'],'coordinates':'UE component XYZ centimetres; quaternion XYZW','sourceSha256':baseline['sourceSha256'],'kernelSha256':hashlib.sha256(kernel.encode()).hexdigest()}
((OUT if args.output_dir else HERE)/'data.json').write_text(json.dumps(data),encoding='utf-8')
(OUT/'build.json').write_text(json.dumps({'source':str(source),'sourceSha256':data['sourceSha256'],'kernelSha256':data['kernelSha256'],'matchesImportedBaseline':data['kernelSha256']==baseline['importedSolverSha256'],'method':'Lab-owned numerical core + ProphecyNativeReach::Step; standalone math compatibility types'},indent=2))
print('Standalone reach kernel built; Unreal untouched.')
