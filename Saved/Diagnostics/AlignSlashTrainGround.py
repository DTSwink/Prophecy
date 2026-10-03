import unreal,pathlib,json
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world()
p='/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent'
bp=unreal.load_asset(p);c=unreal.get_default_object(unreal.load_object(None,p+'.BP_ProphecyManualPoseAgent_C'))
values=list(c.get_editor_property('Codex Slash Train Local Targets'))
data=json.loads((pathlib.Path(unreal.Paths.project_dir())/'Tools/NN/Fixtures/SlashTrain2026092223.json').read_text())
wanted=data['rows'][0]['targetLocalCm'];print('BEFORE',values[0],'AFTER',wanted)
values[0]=unreal.Vector(*wanted)
c.set_editor_property('Codex Slash Train Local Targets',values)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
print('READBACK',c.get_editor_property('Codex Slash Train Local Targets')[0])
