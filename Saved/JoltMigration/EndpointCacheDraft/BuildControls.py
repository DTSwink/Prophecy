from pathlib import Path
import hashlib,json
root=Path.cwd()
draft=root/'Saved/JoltMigration/EndpointCacheDraft'
changes={
'Source/GameAnimationSample3/Private/ProphecyJoltCharacterProfiling.h':[
('PhysicalSampleRead, PhysicalRawEncode, Count };','PhysicalSampleRead, PhysicalRawEncode, TargetEndpointExpand, Count };')],
'Source/GameAnimationSample3/Private/ProphecyJoltCharacterProfiling.cpp':[
('    TEXT("physical_sample_read"), TEXT("physical_raw_encode") };','    TEXT("physical_sample_read"), TEXT("physical_raw_encode"), TEXT("target_endpoint_expand") };')],
'Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp':[
('#include "ProphecyNNPoseTypes.h"','#include "ProphecyNNPoseTypes.h"\n#include "ProphecyNNPhysicalTargetPose.h"'),
('    O->SetObjectField(TEXT("query_tree_settings"), ProphecySterileBench::QueryTreeSettings());','    O->SetObjectField(TEXT("query_tree_settings"), ProphecySterileBench::QueryTreeSettings());\n    O->SetBoolField(TEXT("physical_endpoint_cache_disabled_by_commandline"), ProphecyNNPhysicalTargets::IsEndpointCacheDisabledByCommandLine());'),
('    O->SetObjectField(TEXT("query_tree_settings_at_finish"), ProphecySterileBench::QueryTreeSettings());','    O->SetObjectField(TEXT("query_tree_settings_at_finish"), ProphecySterileBench::QueryTreeSettings());\n    O->SetBoolField(TEXT("physical_endpoint_cache_disabled_by_commandline_at_finish"), ProphecyNNPhysicalTargets::IsEndpointCacheDisabledByCommandLine());')],
'Tools/NN/RunSterilePhysicsBenchmark.ps1':[
('    [switch]$SerialCompose,','    [switch]$SerialCompose,\n    [switch]$NoEndpointCache,'),
("if ($SerialCompose -and $Methods -notin @('JoltLive','JoltCrowd','NNJoltCrowd')) { throw 'SerialCompose requires an explicit live Jolt fixture.' }","if ($SerialCompose -and $Methods -notin @('JoltLive','JoltCrowd','NNJoltCrowd')) { throw 'SerialCompose requires an explicit live Jolt fixture.' }\nif ($NoEndpointCache -and $Methods -notin @('JoltCrowd','NNJoltCrowd')) { throw 'NoEndpointCache requires JoltCrowd or NNJoltCrowd.' }"),
("if ($SerialCompose) { $benchArgs+=' -ProphecyJoltSerialCompose' }","if ($SerialCompose) { $benchArgs+=' -ProphecyJoltSerialCompose' }\nif ($NoEndpointCache) { $benchArgs+=' -ProphecyNNNoEndpointCache' }")],
'Tools/Jolt/RunGameModuleSimdBenchmark.ps1':[
('    [switch]$SerialCompose,','    [switch]$SerialCompose,\n    [switch]$NoEndpointCache,'),
('        DuringPhysics = [bool]$DuringPhysics; SerialCompose = [bool]$SerialCompose','        DuringPhysics = [bool]$DuringPhysics; SerialCompose = [bool]$SerialCompose; NoEndpointCache = [bool]$NoEndpointCache')]
}
# Match the full current enum line and provenance object, keeping every existing field unchanged.
p='Source/GameAnimationSample3/Private/ProphecyJoltCharacterProfiling.h'
original=(root/p).read_text(encoding='utf-8-sig').replace('\r\n','\n')
line=next(s for s in original.splitlines() if 'PhysicalSampleRead, PhysicalRawEncode, Count };' in s)
changes[p]=[(line,line.replace('PhysicalRawEncode, Count','PhysicalRawEncode, TargetEndpointExpand, Count'))]
p='Tools/Jolt/RunGameModuleSimdBenchmark.ps1'
original=(root/p).read_text(encoding='utf-8-sig').replace('\r\n','\n')
line=next(s for s in original.splitlines() if 'requested = [ordered]@' in s)
new=line.replace('serialCompose = [bool]$SerialCompose;', 'serialCompose = [bool]$SerialCompose; noEndpointCache = [bool]$NoEndpointCache;')
assert new!=line
changes[p].append((line,new))
patch=['*** Begin Patch']; report={}
for path,edits in changes.items():
 raw=(root/path).read_bytes()
 before=raw.decode('utf-8-sig').replace('\r\n','\n');after=before
 patch.append('*** Update File: '+path)
 for old,new in edits:
  assert after.count(old)==1,(path,old,after.count(old))
  after=after.replace(old,new,1)
  patch.append('@@')
  # Context-free full-line replacements keep edits separate from concurrent nearby work.
  for s in old.splitlines(): patch.append('-'+s)
  for s in new.splitlines(): patch.append('+'+s)
 dest=draft/'ControlPreview'/path
 dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(after,encoding='utf-8',newline='\n')
 report[path]={'active_sha256':hashlib.sha256(raw).hexdigest(),'unique_hunks':len(edits)}
 assert (root/path).read_bytes()==raw
patch.append('*** End Patch')
(draft/'EndpointCacheControl.apply-patch.txt').write_text('\n'.join(patch)+'\n',encoding='utf-8')
(draft/'ControlVerification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
