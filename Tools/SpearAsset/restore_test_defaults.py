import os,pathlib,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
cdo=unreal.get_default_object(unreal.load_class(None,'/Game/_mygame/spear/A_Spear.A_Spear_C'))
# Recover only the loaded, unsaved fixture CDO after the first test exposed a
# Python struct-reference alias. These are the recorded inherited defaults.
cdo.set_editor_property('velocity cut dampings',unreal.Vector(100,10,1))
print('Loaded fixture defaults restored; no asset saves.')
