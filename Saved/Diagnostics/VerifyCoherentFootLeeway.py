import pathlib,sys
p=pathlib.Path('C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics')
src=(p/'InvestigateAttackFootSink.py').read_text()
src='\n'.join(line for line in src.splitlines() if 'execute_console_command' not in line or 'HalfLocomotionLeeway' not in line)
if len(sys.argv)<2:sys.argv.append('fixed')
if sys.argv[1]=='matrix':
    actions='''
        if f in (30,65,85):
            assert not a.get_nn_attack_state(),'Expected idle before trigger'
            if f==30:assert a.set_attack_calf_clamp(True,5)
            p=a.get_authored_body_world_target('pelvis')[2].translation
            assert a.trigger_nn_attack('kickL' if f==65 else 'slashR',p+unreal.Vector(-30,90,30),f==85)
            s['events'].append(dict(frame=f,action='trigger',state=str(a.get_nn_attack_state())))
        if f in (35,40):
            assert a.get_nn_attack_state(),'Expected active attack before switch'
            assert a.set_nn_half_attack_enabled(f==35)
            s['events'].append(dict(frame=f,action='switch',state=str(a.get_nn_attack_state())))
        if f in (45,50,55):
            assert a.set_attack_calf_clamp(f!=50,0 if f==55 else 3)
            s['events'].append(dict(frame=f,action='calf setting',enabled=f!=50,value=0 if f==55 else 3))
        if f in (60,75,90):
            assert a.stop_nn_attack(),'Expected active attack before stop'
            if f==60:assert a.set_attack_calf_clamp(True,5)
            s['events'].append(dict(frame=f,action='stop'))
'''
    src=src.replace("        s['rows'].append(r)","        s['rows'].append(r)\n"+actions).replace('if f>=450:','if f>=110:')
exec(compile(src,str(p/'InvestigateAttackFootSink.py'),'exec'))
