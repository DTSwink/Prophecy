import pathlib,unreal
source=(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/CaptureHead505.py').read_text(encoding='utf-8-sig')
source=source.replace('Diagnostics/Head50520261003','Diagnostics/NNEntry20261003')
source=source.replace("'clavicle_l','clavicle_r','hand_l','hand_r'","'clavicle_l','clavicle_r','upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r'")
source=source.replace("   if mode=='core_off' and clock==504:",
    "   if mode=='even_entry' and clock==168 and not s.get('shifted'):\n"
    "    root=a.get_root_low_point();forward=a.get_actor_forward_vector()\n"
    "    target=unreal.Vector(root.x+150*forward.x,root.y+150*forward.y,root.z+110)\n"
    "    assert a.trigger_nn_attack('pike',target,False,None),'Even-entry trigger failed'\n"
    "    s['shifted']=True;s['rows'][-1]['attack']=str(a.get_nn_attack_state())\n"
    "   if mode=='core_off' and clock==504:")
exec(compile(source,'CaptureNNEntry.py','exec'))
