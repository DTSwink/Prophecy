import unreal,json,pathlib
a=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin')
r={}
for n in ['ConstraintSetup','SkeletalBodySetups']:
    try:
        items=a.get_editor_property(n); r[n]=[]
        for x in items:
            if n=='ConstraintSetup':r[n].append(str(x.get_editor_property('DefaultInstance')))
            else:r[n].append(dict(bone=str(x.get_editor_property('BoneName')),geometry=str(x.get_editor_property('AggGeom'))))
    except Exception as e:r[n]=str(e)
mesh=unreal.load_asset('/Game/_mygame/SKM_UEFN_Mannequin')
r['mesh_api']=[n for n in dir(mesh) if 'ref' in n or 'bone' in n]
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/SwordThigh/ThreeContacts/asset.json').write_text(json.dumps(r,indent=2))
print({k:len(v) if isinstance(v,list) else v for k,v in r.items()})
