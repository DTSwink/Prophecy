from pathlib import Path
import json,subprocess,ctypes,math
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'Saved/Diagnostics/ReachPelvisHeight';OUT.mkdir(parents=True,exist_ok=True)
s=(ROOT/'Source/GameAnimationSample3/Private/ProphecyDoubleReachAnimInstance.cpp').read_text(encoding='utf-8-sig')
core=s[s.index('namespace ProphecyDoubleReach\n'):s.index('FCompactPoseBoneIndex ResolveCompactBoneIndex')]+'}\n'
step=s[s.index('bool ProphecyNativeReach::Step('):s.index('class FProphecyDoubleReachAnimInstanceProxy')]
compat=(ROOT/'Labs/ReachLab/math_compat.h').read_text()
compat=compat.replace('double Length()const{return std::sqrt(X*X+Y*Y+Z*Z);}', 'double SizeSquared()const{return X*X+Y*Y+Z*Z;} bool ContainsNaN()const{return !(std::isfinite(X)&&std::isfinite(Y)&&std::isfinite(Z));} double Length()const{return std::sqrt(SizeSquared());}')
compat=compat.replace('namespace FMath {','namespace FMath { inline bool IsFinite(double x){return std::isfinite(x);}')
compat=compat.replace('double,double=1.0);','double,double=1.0,double=40.0,FVector=FVector::UpVector);')
(OUT/'math_compat.h').write_text(compat)
wrapper='''
extern "C" __declspec(dllexport) int run(const double* base,const double* targets,int mode,double minimum,const double* metric,double* output) {
 FTransform pose[26];for(int i=0;i<26;++i){const double* p=base+i*7;pose[i].P={p[0],p[1],p[2]};pose[i].Q={p[3],p[4],p[5],p[6]};}
 FVector request[2]={{targets[0],targets[1],targets[2]},{targets[3],targets[4],targets[5]}};float speed[2]={1000,1000};
 ProphecyNativeReach::FState st;TArray<FTransform> out;
 for(int tick=0;tick<120;++tick){
  double height=tick<60?minimum:minimum+15;
  if(!ProphecyNativeReach::Step({pose,26},static_cast<EProphecyDoubleReachMode>(mode),request,speed,st,out,1./60.,1.,height,{metric[0],metric[1],metric[2]}))return 0;
  for(int i=0;i<26;++i){auto p=out[i].P;double* d=output+(tick*26+i)*3;d[0]=p.X;d[1]=p.Y;d[2]=p.Z;}
 }
 return 1;
}
'''
(OUT/'kernel.cpp').write_text('#include <cfloat>\n#include "math_compat.h"\n'+core+step+wrapper)
vc='C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat'
(OUT/'build.cmd').write_text('@echo off\ncall "'+vc+'" >nul\nif errorlevel 1 exit /b 1\ncl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /LD kernel.cpp /Fe:height.dll /link /INCREMENTAL:NO\n')
subprocess.run(['cmd.exe','/c',str(OUT/'build.cmd')],cwd=OUT,check=True)
D=ctypes.c_double;dll=ctypes.CDLL(str(OUT/'height.dll'));dll.run.argtypes=[ctypes.POINTER(D),ctypes.POINTER(D),ctypes.c_int,D,ctypes.POINTER(D),ctypes.POINTER(D)]
data=json.loads((ROOT/'Labs/ReachLab/data.json').read_text());original=data['base'];names=data['names'];pelvis=names.index('pelvis');root=names.index('root')
results=[]
for mode in [1,2,3]:
 for minimum in [20,40,70]:
  for translated in [False,True]:
   base=[p.copy() for p in original];offset=[231,-117,305] if translated else [0,0,0]
   for p in base:
    for k in range(3):p[k]+=offset[k]
   targets=[[-30+offset[0],35+offset[1],-30+offset[2]],[30+offset[0],35+offset[1],-30+offset[2]]]
   out=(D*(120*26*3))();assert dll.run((D*(26*7))(*sum(base,[])),(D*6)(*sum(targets,[])),mode,minimum,(D*3)(0,0,1),out)
   heights=[];max_len_error=0
   for tick in range(120):
    frame=[list(out[(tick*26+i)*3:(tick*26+i+1)*3]) for i in range(26)]
    h=frame[pelvis][2]-frame[root][2];heights.append(h)
    assert h>=(minimum if tick<60 else minimum+15)-1e-7,(mode,minimum,tick,h)
    assert all(math.isfinite(v) for p in frame for v in p)
    for side in ['l','r']:
     for a,b in [('upperarm','lowerarm'),('lowerarm','hand'),('thigh','calf'),('calf','foot')]:
      ai=names.index(a+'_'+side);bi=names.index(b+'_'+side)
      err=abs(math.dist(frame[ai],frame[bi])-math.dist(base[ai][:3],base[bi][:3]));max_len_error=max(max_len_error,err)
   assert max_len_error<1e-6,max_len_error
   results.append(dict(mode=mode,minimum=minimum,translated=translated,minimum_seen=min(heights),after_live_raise=min(heights[60:]),max_bone_error=max_len_error,heights=heights))
for r in results:r.pop('heights')
for metric in [(0,0,.5),(0,0,2),(.3,.4,.866025403784)]:
 out=(D*(120*26*3))()
 assert dll.run((D*(26*7))(*sum(original,[])),(D*6)(-30,35,-30,30,35,-30),3,40,(D*3)(*metric),out)
 heights=[]
 for tick in range(120):
  h=sum((out[(tick*26+pelvis)*3+k]-out[(tick*26+root)*3+k])*metric[k] for k in range(3))
  heights.append(h)
  assert h>=(40 if tick<60 else 55)-1e-7,(metric,tick,h)
 results.append(dict(metric=metric,minimum_seen=min(heights),after_live_raise=min(heights[60:])))
(OUT/'validation.json').write_text(json.dumps(results,indent=2))
print('PASS: 21 low-target cases, 2520 frames, live height changes, translated roots, scaled/tilted world-height metrics; arm/leg lengths preserved in 18 standard cases')
