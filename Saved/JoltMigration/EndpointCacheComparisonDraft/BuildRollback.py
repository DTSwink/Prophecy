from pathlib import Path
import hashlib,json,difflib
root=Path.cwd(); draft=root/'Saved/JoltMigration/EndpointCacheComparisonDraft'
cache=root/'Saved/JoltMigration/EndpointCacheDraft'
record=json.loads((cache/'SourceVerification.json').read_text())
files=['Source/GameAnimationSample3/Private/ProphecyAgent.cpp',
'Source/GameAnimationSample3/Private/ProphecyNNPhysicalTargetPose.h',
'Source/GameAnimationSample3/Private/ProphecyNNPhysicalTargetPose.cpp',
'Source/GameAnimationSample3/Private/ProphecyNNPhysicalTargetPoseTests.cpp',
'Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp',
'Tools/NN/RunSterilePhysicsBenchmark.ps1','Tools/Jolt/RunGameModuleSimdBenchmark.ps1']
raw={p:(root/p).read_bytes() for p in files}
old={p:b.decode('utf-8-sig').replace('\r\n','\n') for p,b in raw.items()}; new=dict(old)
def replace_once(path,a,b):
 assert new[path].count(a)==1,(path,a,new[path].count(a))
 new[path]=new[path].replace(a,b,1)
# Reverse only the three isolated Agent hunks.
p=files[0]; patch=(cache/'AgentEndpointCache.apply-patch.txt').read_text();a=[];b=[];hunks=[]
for line in patch.splitlines():
 if line.startswith('@@') or line=='*** End Patch':
  if a or b:hunks.append(('\n'.join(a)+'\n','\n'.join(b)+'\n'))
  a=[];b=[]
 elif line.startswith('-'):a.append(line[1:])
 elif line.startswith('+'):b.append(line[1:])
for before,after in hunks:replace_once(p,after,before)
p=files[1]
replace_once(p,'    friend class FEndpointCache;\n','')
start=new[p].index('// Parsed once; benchmark reports read this same selector.')
end=new[p].index('// Game-thread only. OutPrevious is intentionally not interpolated:',start)
new[p]=new[p][:start]+new[p][end:]
p=files[2]
start=new[p].index('namespace\n{\nbool CanRetainEndpoints()')
end=new[p].index('bool BuildWorldPoses(const USkeletalMesh& Mesh, const UPhysicsAsset& PhysicsAsset,',start)
new[p]=new[p][:start]+new[p][end:]
replace_once(p,'#include "Misc/CommandLine.h"\n','')
replace_once(p,'#include "Misc/Parse.h"\n','')
assert new[p].count('EPhase::TargetEndpointExpand')==1
p=files[3]
marker='namespace ProphecyNNPhysicalTargets::Tests\n{'
start=new[p].index(marker,new[p].index(marker)+len(marker))
new[p]=new[p][:start]+'#endif\n'
replace_once(p,'#include <limits>\n\n','')
# Remove controls by semantic token/line only, retaining newer root launcher fields.
p=files[4]
replace_once(p,'#include "ProphecyNNPhysicalTargetPose.h"\n','')
for line in list(new[p].splitlines()):
 if 'SetBoolField(TEXT("physical_endpoint_cache_disabled_by_commandline' in line:
  replace_once(p,line+'\n','')
for p in files[5:]:
 replace_once(p,'    [switch]$NoEndpointCache,\n','')
 for line in list(new[p].splitlines()):
  if line.startswith('if ($NoEndpointCache'):
   replace_once(p,line+'\n','')
 if p.endswith('RunGameModuleSimdBenchmark.ps1'):
  replace_once(p,'; NoEndpointCache = [bool]$NoEndpointCache','')
  replace_once(p,'; noEndpointCache = [bool]$NoEndpointCache','')
assert all('EndpointCache' not in new[p] for p in files[:4])
assert all('NoEndpointCache' not in new[p] for p in files[4:])
scope='    ProphecyJolt::CharacterProfiling::FScope EndpointTiming(ProphecyJolt::CharacterProfiling::EPhase::TargetEndpointExpand);\n'
checks={}
for p in files[1:4]:
 candidate=new[p]
 if p.endswith('ProphecyNNPhysicalTargetPose.cpp'):
  candidate=candidate.replace('#include "ProphecyJoltCharacterProfiling.h"\n','').replace(scope,'')
 expected=record['active_baseline_sha256'][p.replace('/','\\')]
 # Initial originals were UTF-8 LF; also report canonical-content equality across line-ending variants.
 hashes={hashlib.sha256(candidate.encode()).hexdigest(),hashlib.sha256(candidate.replace('\n','\r\n').encode()).hexdigest()}
 checks[p]={'matches_pre_cache_hash_after_removing_only_retained_timer':expected in hashes,'expected':expected}
 assert expected in hashes,(p,hashes,expected)
outpatch=['*** Begin Patch']; manifest={}
for p in files:
 archive=draft/'CacheSourceArchive'/p
 archive.parent.mkdir(parents=True,exist_ok=True)
 if archive.exists():assert archive.read_bytes()==raw[p]
 else:archive.write_bytes(raw[p])
 dest=draft/'Rollback'/p
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(new[p],encoding='utf-8',newline='\n')
 delta=list(difflib.unified_diff(old[p].splitlines(),new[p].splitlines(),n=3,lineterm=''))
 assert delta,p
 outpatch.append('*** Update File: '+p)
 for line in delta[2:]:outpatch.append('@@' if line.startswith('@@') else line)
 manifest[p]={'active_sha256':hashlib.sha256(raw[p]).hexdigest(),'rollback_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
 assert (root/p).read_bytes()==raw[p]
outpatch.append('*** End Patch')
(draft/'RollbackEndpointCache.apply-patch.txt').write_text('\n'.join(outpatch)+'\n',encoding='utf-8')
report={'files':manifest,'original_math_and_original_three_tests':checks,'Agent_reverse_hunks':len(hunks),'retained_profile':'TargetEndpointExpand enum/name and one Evaluate entry FScope','active_edits_or_builds':False}
(draft/'RollbackVerification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
