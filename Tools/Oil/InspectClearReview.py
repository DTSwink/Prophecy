import json
from pathlib import Path
import unreal as u
assert '-ProphecyOilClearReview' in u.SystemLibrary.get_command_line()
ed=u.get_editor_subsystem(u.UnrealEditorSubsystem);assert not ed.get_game_world()
lib=u.MaterialEditingLibrary
rows=[]
for name in ['Materials/M_OilBottleGlass','Materials/M_OilBottleCork','VFX/M_OilDroplet']:
    m=u.load_asset('/Game/_mygame/OilBottle/'+name);row={'material':name,'blend':str(m.get_editor_property('blend_mode')),'lighting':str(m.get_editor_property('translucency_lighting_mode')),'two_sided':m.get_editor_property('two_sided'),'nodes':[]};seen=set()
    def walk(n):
        if not n or n.get_path_name() in seen:return
        seen.add(n.get_path_name());r={'class':n.get_class().get_name()}
        for prop in ['constant','parameter_name','default_value','code','exponent','base_reflect_fraction']:
            try:r[prop]=str(n.get_editor_property(prop))
            except Exception:pass
        row['nodes'].append(r)
        for x in lib.get_inputs_for_material_expression(m,n):walk(x)
    for prop in [u.MaterialProperty.MP_BASE_COLOR,u.MaterialProperty.MP_EMISSIVE_COLOR,u.MaterialProperty.MP_OPACITY,u.MaterialProperty.MP_ROUGHNESS]:walk(lib.get_material_property_input_node(m,prop))
    rows.append(row)
cvars={}
for n in ['r.MaterialQualityLevel','sg.EffectsQuality','r.TranslucencyLightingVolumeDim','r.TranslucentLightingVolume','r.SupportStationarySkylight','r.SeparateTranslucency']:
    cvars[n]=u.SystemLibrary.get_console_variable_int_value(n)
(Path(u.Paths.project_saved_dir())/'Diagnostics/Oil/Bottle/Clear/inspection.json').write_text(json.dumps({'materials':rows,'cvars':cvars},indent=2))
print('INSPECTED')
