import os,json,pathlib,unreal
out=pathlib.Path(unreal.Paths.project_dir())/'Saved/Diagnostics/SpearPike20261030'
assert os.getpid()==int((out/'editor.pid').read_text().strip())
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
mesh=unreal.load_asset('/Game/_mygame/spear/SM_ImperialSpear')
body=mesh.get_editor_property('body_setup');agg=body.get_editor_property('agg_geom')
hulls=[]
for h in agg.get_editor_property('convex_elems'):
    text=h.export_text()
    hulls.append({'text':text})
(out/'imported-collision.json').write_text(json.dumps(hulls,indent=2),encoding='utf-8')
print('hulls',len(hulls),'first',hulls[0]['text'][:300])
