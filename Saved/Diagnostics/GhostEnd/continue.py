import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'Preserve user PIE'
p=pathlib.Path(unreal.Paths.project_saved_dir(),'Diagnostics/GhostEnd')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
m=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager,unreal.Vector(0,0,-10000),transient=True)
try:
 for i in [1,2]:
  m.call_method('AuditSlashReference',(str(p/('continuation'+str(i))),))
finally:actors.destroy_actor(m)
c=unreal.get_default_object(unreal.load_class(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent_C'))
q=c.get_editor_property('sword_grip_transform').rotation
(p/'grip.json').write_text(json.dumps([q.x,q.y,q.z,q.w]))
print('GHOST_CONTINUATION_DONE')
