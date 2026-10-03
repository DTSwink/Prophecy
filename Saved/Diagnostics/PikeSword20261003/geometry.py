import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeSword20261003'
m=unreal.load_asset('/Game/_mygame/sword/geometry/Sword_GL01_Training');b=m.get_bounding_box()
v=lambda x:[x.x,x.y,x.z]
out=dict(mesh=m.get_path_name(),min=v(b.min),max=v(b.max))
(p/'geometry.json').write_text(json.dumps(out,indent=2));print(out)
