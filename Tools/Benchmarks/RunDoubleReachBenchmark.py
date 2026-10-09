"""Run paired CPU-only Unreal reach benchmarks in clean, hidden editor processes."""
import argparse,json,pathlib,subprocess,time,hashlib,ctypes,platform
p=pathlib.Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--counts',default='1,10,50,100')
parser.add_argument('--workloads',default='easy,balls,hard')
parser.add_argument('--parallel',default='0,1')
parser.add_argument('--frames',type=int,default=240)
parser.add_argument('--repeat',type=int,default=5)
parser.add_argument('--tag',default='main')
a=parser.parse_args()
folder=p/'Saved/Benchmarks/DoubleReach20261008'/a.tag;folder.mkdir(parents=True,exist_ok=True)
exe=pathlib.Path('C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe')
manifest={'args':vars(a),'production_source_sha256':hashlib.sha256((p/'Source/GameAnimationSample3/Private/ProphecyDoubleReachAnimInstance.cpp').read_bytes()).hexdigest(),'runs':[]}
class PowerStatus(ctypes.Structure):
 _fields_=[('ACLineStatus',ctypes.c_ubyte),('BatteryFlag',ctypes.c_ubyte),('BatteryLifePercent',ctypes.c_ubyte),('SystemStatusFlag',ctypes.c_ubyte),('BatteryLifeTime',ctypes.c_ulong),('BatteryFullLifeTime',ctypes.c_ulong)]
def power():
 s=PowerStatus();ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s));return {n:getattr(s,n) for n,_ in s._fields_}
manifest['power_start']=power();manifest['os']=platform.platform()
for workload in a.workloads.split(','):
 for count in map(int,a.counts.split(',')):
  for parallel in map(int,a.parallel.split(',')):
   name=f'{workload}_{count}_parallel{parallel}'
   output=folder/(name+'.json');log=folder/(name+'.log')
   if output.exists():raise RuntimeError(f'Refusing to overwrite {output}; use a new --tag')
   relative=output.relative_to(p).as_posix()
   command=f'Prophecy.ReachBenchmark {count} {a.frames} {a.repeat} {workload} {parallel} {relative},QUIT_EDITOR'
   args=[str(exe),str(p/'GameAnimationSample3.uproject'),'/Engine/Maps/Entry','-unattended','-nullrhi','-nosound','-NoSplash','-NoLiveCoding','-nop4',f'-abslog={log}',f'-ExecCmds={command}']
   start=time.monotonic();print('START',name,flush=True)
   with (folder/(name+'-stdout.log')).open('w') as stdout:
    result=subprocess.run(args,cwd=p,stdout=stdout,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=1200)
   entry={'name':name,'seconds':time.monotonic()-start,'exit_code':result.returncode,'command':args,'power':power()};manifest['runs'].append(entry)
   (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
   if result.returncode or not output.exists():raise RuntimeError(f'Benchmark failed; inspect {log}')
   data=json.loads(output.read_text(encoding='utf-8-sig'))
   assert data['max_position_error_cm']<=.001 and data['max_angle_error_deg']<=.001
   print('DONE',name,'direct',data['direct']['median_ms'],'rig',data['control_rig_anim_node']['median_ms'],'seconds',entry['seconds'],flush=True)
