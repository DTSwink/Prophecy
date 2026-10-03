import pathlib,unreal,sys
root=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics'
src=(root/'CaptureWrist230.py').read_text().replace("s['frame']>=270","s['frame']>=405")
inject=''
if len(sys.argv)>1 and sys.argv[1]=='elbow365_no_cone':
 inject="""   if clock>=300:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyArmConeLibrary')).call_method('SetArmRepellantCone',(a,False,60.,1000000.,20.,.5,.5,False,5.,50.,10.))
"""
if len(sys.argv)>1 and sys.argv[1]=='elbow365_no_inertia':
 src=src.replace('clock>=999999','clock>=330')
 inject="""   if clock>=363:
    unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyUpperBodyInertiaLibrary')).call_method('SetAttackUpperBodyInertia',(a,False,.025,0.,.5,1.,unreal.ProphecyUpperHandInertiaSpace.SPINE_LOCAL,1.))
"""
src=src.replace("exec(compile(src,'CaptureWrist230','exec'))", "src=src.replace('   r=dict(t=t',inject+'   r=dict(t=t')\nexec(compile(src,'CaptureWrist230','exec'))")
exec(compile(src,'CaptureElbow365','exec'))
