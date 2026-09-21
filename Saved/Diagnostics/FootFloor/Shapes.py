import unreal,json,pathlib
out=[]
for obj in unreal.ObjectIterator():
    try:
        if obj.get_class().get_name()!='SkeletalBodySetup' or 'PA_UEFN_Mannequin.' not in obj.get_path_name(): continue
        bone=str(obj.get_editor_property('bone_name'))
        if bone not in ('foot_l','foot_r'):continue
        agg=obj.get_editor_property('agg_geom')
        row={'bone':bone,'shapes':{}}
        for kind in ('sphere_elems','box_elems','sphyl_elems','convex_elems'):
            row['shapes'][kind]=[str(e) for e in agg.get_editor_property(kind)]
        out.append(row)
    except Exception as e: pass
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/FootFloor/shapes.json'
p.write_text(json.dumps(out,indent=2))
print(out)
