"""Read-only graph/profile inspection before the lateral cut-joint probe."""
import json, pathlib, unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeSlide'
out.mkdir(parents=True,exist_ok=True)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Sword.AuditCollisionGraph')
bp=unreal.load_asset('/Game/_mygame/sword/A_Sword')
t=unreal.AssetExportTask()
t.object,t.filename,t.exporter=bp,str(out/'sword.txt'),unreal.ObjectExporterT3D()
t.automated,t.prompt,t.replace_identical=True,False,True
assert unreal.Exporter.run_asset_export_task(t)
print(json.dumps({'play':bool(ed.get_game_world()),
 'constraint_methods':[x for x in dir(unreal.PhysicsConstraintComponent) if any(k in x for k in ('frame','constraint','linear','angular'))],
 'instance_methods':dir(unreal.ConstraintInstance),
 'library_methods':[x for x in dir(unreal.ConstraintInstanceBlueprintLibrary) if any(k in x for k in ('linear','angular','frame','position','orientation'))]}))
