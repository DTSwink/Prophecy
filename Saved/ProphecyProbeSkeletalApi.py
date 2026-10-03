import unreal
mesh = unreal.load_asset('/Game/Prophecy/MetaHumans/ProphecyPlaceholder/Face/SKM_MHC_ProphecyPlaceholder_FaceMesh')
print('mesh methods', [x for x in dir(mesh) if 'lod' in x.lower() or 'section' in x.lower() or 'material' in x.lower()][:200])
sub = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
print('sub', sub)
print('sub methods', [x for x in dir(sub) if 'lod' in x.lower() or 'section' in x.lower() or 'material' in x.lower()][:240])
