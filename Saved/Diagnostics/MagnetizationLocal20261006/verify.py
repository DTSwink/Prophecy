import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/MagnetizationLocal20261006'
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_game_world() is None,'Preserve user Play'
methods={}
for cls in [unreal.ProphecyPhysicalProfileLibrary,unreal.ProphecyClampProfileLibrary]:
 for name in dir(cls):
  if name.startswith('blend_') and name.endswith('_to_snapshot'):
   doc=getattr(cls,name).__doc__ or ''
   assert 'hold_out_time' in doc,(name,doc)
   methods[name]=doc.splitlines()[0]
assert len(methods)==12,methods
assert hasattr(unreal.ProphecyPhysicalProfileLibrary,'set_magnetization_mode')
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.LiveAgentTypes Inspect')
r=(p.parent/'LiveAgentTypes-Inspect.txt').read_text(encoding='utf-8-sig')
assert 'status=3' in r and 'native_properties=0 pin_types=0' in r,r
(p/'reflection.json').write_text(json.dumps({'world':ed.get_editor_world().get_path_name(),'signatures':methods,'blueprint':r},indent=2))
unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Automation RunTests Prophecy.Jolt.Servo+Prophecy.Jolt.MultiRig+Prophecy.Jolt.RigWorld.ServoHandlesAndWholeRigRemoval+Prophecy.Agent.PhysicalContext+Prophecy.PhysicalProfiles.ClampSnapshots+Prophecy.Joints.DampingProfileBlend+Prophecy.NN.AgentReset.PhysicalBaseline')
print('REFLECTION_BLUEPRINT_VERIFIED_TESTS_REQUESTED')
