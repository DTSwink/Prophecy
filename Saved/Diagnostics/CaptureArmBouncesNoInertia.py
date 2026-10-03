import pathlib,unreal,sys
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(root/'CaptureWrist230.py').read_text().replace("s['frame']>=270","s['frame']>=620")
inject="""   if clock>=500 and not a.get_nn_attack_state():
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary')).call_method('SetAttackUpperBodyInertia',(a,False,.025,0.,.5,1.,unreal.ProphecyUpperHandInertiaSpace.SPINE_LOCAL,1.))
"""
src=src.replace("exec(compile(src,'CaptureWrist230','exec'))", "src=src.replace('   r=dict(t=t',inject+'   r=dict(t=t')\nexec(compile(src,'CaptureWrist230','exec'))")
exec(compile(src,'CaptureArmBouncesNoInertia','exec'))
