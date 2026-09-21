import unreal
bp=unreal.load_asset('/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent')
n=unreal.find_object(None,bp.get_path_name()+':begin_f.K2Node_CallFunction_6')
print('NODE',n)
for p in ['enabled_state','function_reference','node_comment']:
 try:print(p,n.get_editor_property(p))
 except Exception as e:print(p,str(e))
print('ENUM',getattr(unreal,'NodeEnabledState',None))
print([x for x in dir(unreal.BlueprintEditorLibrary) if any(w in x for w in ['node','variable','compile'])])
