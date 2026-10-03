import unreal,builtins,gc,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
for name,file in (('_calf_connection','CalfAnkleConnection-before.json'),('_kick_foot_snap','KickFootSnap-currentRotation-verified.json')):
    value=getattr(builtins,name,None)
    if isinstance(value,dict) and (p/file).exists():
        count=len(value.get('rows',[]))
        value.get('rows',[]).clear()
        print('RELEASED_COMPLETED_CAPTURE',name,count)
gc.collect()
