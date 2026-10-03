import unreal
from pathlib import Path
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
manager=actors.spawn_actor_from_class(unreal.ProphecyNNLocomotionManager, unreal.Vector(0,0,0), transient=True)
try:
    result=manager.call_method('AuditSlashReference',args=(str(Path(unreal.Paths.project_saved_dir()).resolve()/'Slash123793'),))
    print('SLASH123793_AUDIT', result)
finally:
    actors.destroy_actor(manager)
unreal.SystemLibrary.execute_console_command(world,'Automation RunTests Prophecy.NN.PhysicalTargets.AttackLegClamps')
