"""Editor bridge entry point for the immutable 30-attack native-chain audit."""
import json
import math
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir()).resolve()
directory=root/'Saved/SlashChain'
assert unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is None
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
manager=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(0,0,-10000),transient=True)
try:
    result=manager.call_method('AuditSlashReference',args=(str(directory),))
finally:
    actors.destroy_actor(manager)
report=json.loads((directory/'unreal_chain_audit.json').read_text())
fixture=json.loads((directory/'chain_audit.json').read_text())
max_teacher_mm=0.
teacher_latches=True
for actual,expected in zip(report['teacher_outputs'],fixture['teacher_oracle']):
    max_teacher_mm=max(max_teacher_mm,max(math.sqrt(sum((actual[131+b*3+a]-expected[131+b*3+a])**2 for a in range(3)))*1000 for b in range(25)))
    teacher_latches &= actual[431:433]==expected[431:433]
hits=[]
for segment in fixture['segments']:
    hit=next((i+2 for i in range(segment['startFrame']-2,segment['finalFrame']-1) if report['outputs'][i][432]>=.5),None)
    hits.append({'attack':segment['attackIndex'],'family':segment['family'],'expected_hit':segment['hitFrame'],'unreal_hit':hit,
                 'matched':hit==segment['hitFrame']})
summary={k:v for k,v in report.items() if k not in ['frames','outputs','teacher_outputs']}
summary.update(native_teacher_max_mm=max_teacher_mm,native_teacher_latches_match=teacher_latches,
               attacks=hits,all_30_hits_match=all(h['matched'] for h in hits),
               source_step_teacher_max_mm=max(fixture['source_step_teacher_errors_m'])*1000,
               source_sha256=fixture['source_sha256'],checkpoint_sha256=fixture['checkpoint_sha256'])
(directory/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
assert result and teacher_latches and max_teacher_mm<.1, 'Native port parity failed; see Saved/SlashChain/summary.json'
