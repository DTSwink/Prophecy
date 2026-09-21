import unreal,json,pathlib
bp=unreal.load_object(None,'/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent')
result={'library':[x for x in dir(unreal.BlueprintEditorLibrary) if 'graph' in x.lower() or 'node' in x.lower()]}
for key in ['function_graphs','ubergraph_pages']:
    try:
        graphs=bp.get_editor_property(key)
        result[key]=[str(g) for g in graphs]
        for g in graphs:
            if 'debug' not in g.get_name().lower():continue
            result[g.get_name()]=[]
            for n in g.get_editor_property('nodes'):
                r={'name':n.get_name(),'class':n.get_class().get_name()}
                for prop in ['pins','function_reference','variable_reference']:
                    try:r[prop]=str(n.get_editor_property(prop))
                    except Exception as e:r[prop]=str(e)
                result[g.get_name()].append(r)
    except Exception as e:result[key]=str(e)
print(json.dumps(result,indent=2))
(pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/WideWrist/graph_properties.json').write_text(json.dumps(result,indent=2))
