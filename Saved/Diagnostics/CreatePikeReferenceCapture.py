from pathlib import Path
p=Path('Saved/Diagnostics/CapturePikeReturn.py')
s=p.read_text(encoding='utf-8-sig')
s='\n'.join(l for l in s.splitlines() if 'ClearPathShortcut' not in l and "if tag=='latelegacy_variants'" not in l)+'\n'
s=s.replace("out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeReturn'", "out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeReference'")
s=s.replace("   pose=a.read_nn_future_world_pose()", "   if s['frame']==30 and a.is_player_controlled():\n    assert lib.call_method('SetAttackArmReturnPelvisLocal',(a,*(tag.startswith('pelvis') and i==6 for i in range(16))))\n    print('PIKE_REFERENCE',tag,a.get_name())\n   pose=a.read_nn_future_world_pose()")
Path('Saved/Diagnostics/CapturePikeReference.py').write_text(s,encoding='utf-8')
