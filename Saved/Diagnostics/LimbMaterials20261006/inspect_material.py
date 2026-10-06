import unreal,json,pathlib
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/LimbMaterials20261006'
rows=[]
for name in ['M_UEFN_Mannequin','M_UEFN_Mannequin_Masked_Bicolor']:
 m=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Materials/'+name)
 d={'name':name}
 for typ in ['scalar','vector','texture']:
  names=getattr(unreal.MaterialEditingLibrary,'get_'+typ+'_parameter_names')(m)
  d[typ]=[str(x) for x in names]
 rows.append(d)
(p/'material_parameters.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
