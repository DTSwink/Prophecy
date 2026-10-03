import unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
print('PLAY',bool(ed.get_game_world()))
ar=unreal.AssetRegistryHelpers.get_asset_registry()
assets=ar.get_assets_by_class(unreal.TopLevelAssetPath('/Script/Engine','AnimSequence'),True)
print('SEQUENCES',len(assets))
for a in assets:
 if any(x in str(a.asset_name).lower() for x in ('slash','punch','hook','jab','attack','pike')):print(a.package_name)
if assets:print('FALLBACK',[str(a.package_name) for a in assets[:8]])
