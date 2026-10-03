import unreal
print('USAGE', [x for x in dir(unreal.MaterialUsage) if 'SKELETAL' in x or 'INSTANCED' in x])
print('EXISTING',unreal.EditorAssetLibrary.list_assets('/Game/_mygame/materials/base_colors',recursive=False,include_folder=False))
