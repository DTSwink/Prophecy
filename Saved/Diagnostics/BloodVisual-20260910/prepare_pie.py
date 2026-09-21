import builtins,unreal,json
s=builtins._blood_visual
s['manager'].clear_runtime_paint_state(True)
saved=[]
for p in s['manager'].blood_enabled_material_pairs:
 if p.clean_material.get_path_name() in ('/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial','/Game/_mygame/sword/geometry/M_Sword.M_Sword','/Game/Characters/UEFN_Mannequin/Materials/M_UEFN_Mannequin.M_UEFN_Mannequin'):
  ok=unreal.EditorAssetLibrary.save_loaded_asset(p.blood_material,only_if_is_dirty=True)
  saved.append({'path':p.blood_material.get_path_name(),'saved':ok})
s['report']['prepared_material_saves']=saved
(s['out']/'prepared-materials.json').write_text(json.dumps(saved,indent=2))
print('PREPARED',saved)
