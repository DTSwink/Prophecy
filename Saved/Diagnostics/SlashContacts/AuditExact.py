import unreal,json,pathlib,math
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SlashContacts/ExactChain'
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
manager=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(0,0,-10000),transient=True)
try:ok=manager.call_method('AuditSlashReference',args=(str(p),))
finally:actors.destroy_actor(manager)
actual=json.loads((p/'unreal_chain_audit.json').read_text())
expected=json.loads((p/'chain_audit.json').read_text())
report={'returned':ok,'steps':len(actual['outputs'])}
for key in ['outputs','teacher_outputs']:
    pos=0.;rot=0.;latches=True;pins=0.
    for a,e in zip(actual[key],expected['expected']):
        pos=max(pos,max(math.dist(a[131+3*b:134+3*b],e[131+3*b:134+3*b])*1000 for b in range(25)))
        rot=max(rot,max(abs(x-y) for x,y in zip(a[206:431],e[206:431])))
        pins=max(pins,max(abs(x-y) for x,y in zip(a[435:437],e[435:437])))
        latches &= a[431:433]==e[431:433]
    report[key]={'position_max_mm':pos,'matrix_max':rot,'pins_max':pins,'latches_match':latches}
(p/'ExactSummary.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
