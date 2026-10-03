from pathlib import Path
p=Path('Saved/Diagnostics/CaptureAttackStartInertia.py');s=p.read_text()
s=s.replace('AttackStartInertia-runtime.json','FootEntryInertia-runtime.json').replace('_attack_start_probe','_foot_entry_probe')
s=s.replace('args=(a,True,5,1.,7,1.)','args=(a,True,5,1.,7,1.,5,1.,7,1.,4,1.,6,1.)')
s=s.replace("            s['rows'].append(row)","""            row['bones']={}
            for bone in ['foot_l','foot_r','calf_l','calf_r','thigh_l','thigh_r','ball_l','ball_r']:
                bt=a.get_authored_body_world_target(bone)
                row['bones'][bone]={'target':tr(bt[2]),'physical':tr(mesh.get_socket_transform(bone,unreal.RelativeTransformSpace.RTS_WORLD))}
            s['rows'].append(row)""")
Path('Saved/Diagnostics/CaptureFootEntryInertia.py').write_text(s)
Path('Saved/Diagnostics/RunFootEntryCapture.py').write_text("from pathlib import Path\nexec(compile(Path('Saved/Diagnostics/CaptureFootEntryInertia.py').read_text(), 'CaptureFootEntryInertia.py', 'exec'), {'__name__':'foot_entry_capture'})\n")
