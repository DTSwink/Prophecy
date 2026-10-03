import pathlib,unreal
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/RootTrail22020261003';p.mkdir(exist_ok=True)
source=(p.parent/'CaptureHead505.py').read_text(encoding='utf-8-sig').replace('Diagnostics/Head50520261003','Diagnostics/RootTrail22020261003').replace("s['frames']>=550","s['frames']>=265")
source=source.replace("    s['rows'].append(r)","    r['actor_transform']=tr(a.get_actor_transform())\n    continuous=unreal.get_default_object(unreal.ProphecyRootPhysicsLibrary).call_method('GetContinuousLocomotionRootWindow',(a,))\n    if continuous:r['continuous']=[tr(x) for x in continuous[0]]\n    if raw:r['raw_transforms']=[tr(x) for x in raw[0]]\n    r['smoothing']=unreal.get_default_object(unreal.ProphecyNNRootWindowLibrary).call_method('GetLocomotionRootWindowSmoothing',(a,))\n    r['intent']=str(a.get_locomotion_input())\n    s['rows'].append(r)")
exec(compile(source,'CaptureRoot220.py','exec'))
