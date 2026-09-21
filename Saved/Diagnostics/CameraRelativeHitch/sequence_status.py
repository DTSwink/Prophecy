import builtins,json,unreal
state=getattr(builtins,'_prophecy_mode_sequence',None)
print(json.dumps({k:state.get(k) for k in ('path','done','error','last_t','events','dirty_content','dirty_maps')},indent=2) if state else 'No sequence capture')
print('Current dirty content:',[str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()])
print('Current dirty maps:',[str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])
