import unreal
folder='/Game/_mygame/materials/base_colors/'
renames=[]
for colour in ['Green','Orange','Red','Blue','Purple','White','Black','Grey']:
    for translucent in (False,True):
        old=folder+'M_Debug_'+colour+('_Translucent' if translucent else '_Opaque')
        new=folder+'M_'+colour+('_Translucent' if translucent else '')
        assert not unreal.EditorAssetLibrary.does_asset_exist(new),new
        asset=unreal.EditorAssetLibrary.load_asset(old)
        assert asset,old
        renames.append(unreal.AssetRenameData(asset,folder.rstrip('/'),new.rsplit('/',1)[1]))
assert unreal.AssetToolsHelpers.get_asset_tools().rename_assets(renames)
paths=[]
for colour in ['Green','Orange','Red','Blue','Purple','White','Black','Grey']:
    for suffix in ('','_Translucent'):
        path=folder+'M_'+colour+suffix
        assert unreal.EditorAssetLibrary.save_asset(path,only_if_is_dirty=False),path
        paths.append(path)
unreal.EditorAssetLibrary.sync_browser_to_objects(paths)
print('Renamed and saved all 16 materials:', ', '.join(p.rsplit('/',1)[1] for p in paths))
