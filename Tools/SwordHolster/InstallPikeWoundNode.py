"""Targeted native-node build/install; preserve all existing authored graph pins."""
import hashlib,json,pathlib,re,shutil,sys,unreal
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not ed.get_game_world(),'User Play left untouched; stop before patch/install'
out=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/PikeWoundNode'
out.mkdir(parents=True,exist_ok=True)
bp=unreal.load_asset('/Game/_mygame/sword/A_Sword')
def export(name):
    task=unreal.AssetExportTask()
    task.object,task.filename,task.exporter=bp,str(out/name),unreal.ObjectExporterT3D()
    task.automated,task.prompt,task.replace_identical=True,False,True
    assert unreal.Exporter.run_asset_export_task(task)
def pins(name):
    text=(out/name).read_text(encoding='utf-8-sig')
    graphs=set(re.findall(r'^   (?:FunctionGraphs|UbergraphPages|MacroGraphs)\(\d+\)="[^\'\n]+\'([^\']+)\'"',text,re.M))
    stack,result=[],{}
    for line in text.splitlines():
        if re.match(r'\s*Begin Object ',line):stack.append(re.search(r'\bName="([^"]+)"',line).group(1))
        elif line.strip()=='End Object':stack.pop()
        elif 'CustomProperties Pin ' in line and len(stack)>1 and stack[1] in graphs:
            result[tuple(stack[1:])+(re.search(r'PinId=(\w+)',line).group(1),)]=line.strip()
    return graphs,result
if '--build' in sys.argv:
    export('before-build.txt')
    unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'LiveCoding.Compile')
    print('Pike wound node build dispatched; assets untouched')
else:
    fn=unreal.find_object(None,'/Script/GameAnimationSample3.ProphecyPhysicsConstraintBlueprintLibrary:SetPikeWoundCorrection')
    assert fn,'Native node is not loaded'
    if '--install' in sys.argv:
        export('before.txt')
        backup=out/'A_Sword.before.uasset'
        if not backup.exists():shutil.copy2(pathlib.Path(unreal.Paths.project_dir())/'Content/_mygame/sword/A_Sword.uasset',backup)
        unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.Editor.RefreshHolsterGripPins PikeWoundCorrection')
        export('after.txt')
        graphs,before=pins('before.txt');after_graphs,after=pins('after.txt')
        assert graphs==after_graphs and not before.keys()-after.keys()
        allowed={('K2Node_CallFunction_50','then'),('K2Node_IfThenElse_1','execute'),
                 ('K2Node_AddComponent_0','ReturnValue'),('K2Node_VariableGet_22','temp pike')}
        changed=[]
        for key,old in before.items():
            new=after[key]
            if old==new:continue
            name=re.search(r'PinName="([^"]+)"',old).group(1)
            assert key[0]=='EventGraph' and (key[-2],name) in allowed,(key,name)
            strip=lambda s:re.sub(r'LinkedTo=\([^)]*\),','',s)
            assert strip(old)==strip(new),(key,name,'non-link change')
            changed.append([key[-2],name])
        added=sorted({key[-2] for key in after.keys()-before.keys()})
        assert added==['ProphecyPikeCorrectionGate','ProphecyPikeWoundCorrection'],added
        # Switch off the broad Python preview only after the native opt-in is wired.
        if 'pike_wound_demo' in globals() and pike_wound_demo.handle is not None:
            pike_wound_demo.finish('Replaced by native per-constraint node')
        result=dict(graphs=len(graphs),preserved_pins=len(before),changed_links=changed,added_nodes=added,
                    saved=False,python_preview_removed=True)
        (out/'graph-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
    print('Loaded: '+unreal.EditorAssetLibrary.get_metadata_tag(fn,'DisplayName'))
