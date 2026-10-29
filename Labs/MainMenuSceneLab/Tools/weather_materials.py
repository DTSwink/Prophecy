# Executed with the preparation helpers from prepare_materials.py.
# Stable instance seeds; fall, shear and gust work stays on the GPU.
m=material('M_RainStreak')
m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
m.set_editor_property('two_sided',True)
m.set_editor_property('max_world_position_offset_displacement',850)
LIB.set_material_usage(m,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
phase=node(m,unreal.MaterialExpressionPerInstanceCustomData,data_index=0)
active=node(m,unreal.MaterialExpressionPerInstanceCustomData,data_index=1)
center_y=node(m,unreal.MaterialExpressionPerInstanceCustomData,data_index=2)
phase_pixel=node(m,unreal.MaterialExpressionVertexInterpolator)
active_pixel=node(m,unreal.MaterialExpressionVertexInterpolator)
assert LIB.connect_material_expressions(phase,'',phase_pixel,'VS')
assert LIB.connect_material_expressions(active,'',active_pixel,'VS')
tm=scalar(m,0,'RainTime');amount=scalar(m,.45,'RainAmount');slant=scalar(m,.08,'RainSlant')
width=scalar(m,.12,'RainWidth');length=scalar(m,18,'RainLength');gust=scalar(m,.65,'RainGust')
position=node(m,unreal.MaterialExpressionWorldPosition)
camera=node(m,unreal.MaterialExpressionCameraPositionWS)
offset=custom(m,'''
// Collapse inactive quads before rasterization: the expanded capacity should
// not add transparent overdraw at the user's existing density.
if(Key>=Amount)return float3(0,CenterY-P.y,3.5-P.z);
float age=frac(T/1.6+Seed)*1.6;
float z=max(0,560*(1-age));
float dz=(P.z-3.5)*Length/7.5;
float height=max(0,z+dz);
// Shear goes to zero at the impact point shared with the surface rings.
float flow=sin(height*.002+P.x*.004+T*.7)*.65+sin(height*.005+Seed*37-T*1.2)*.35;
float side=height*.34*Slant+flow*Gust*height*.12;
// Keep physical width: distant drops must become finer, never screen-sized.
return float3(0,(P.y-CenterY)*(Width/.4-1)+side,z+dz-(P.z-3.5));
''',{'T':tm,'Seed':phase,'Key':active,'Amount':amount,'P':position,'Camera':camera,'CenterY':center_y,'Slant':slant,'Width':width,'Length':length,'Gust':gust})
prop(offset,unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
uv=node(m,unreal.MaterialExpressionTextureCoordinate)
opacity=custom(m,'''
float age=frac(T/1.6+Seed)*1.6;
float ends=smoothstep(0,.035,age)*(1-smoothstep(.96,1,age));
float vertical=pow(saturate(sin(UV.x*3.14159265)),.7);
float lateral=exp(-pow((UV.y-.5)*4.8,2));
float distance=length(P-Camera);
float depthFade=smoothstep(90,180,distance)*(1-smoothstep(900,2800,distance));
return vertical*lateral*ends*step(Key,Amount)*(.38+.28*Seed)*depthFade;
''',{'T':tm,'Seed':phase_pixel,'Key':active_pixel,'Amount':amount,'UV':uv,'P':position,'Camera':camera},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
prop(opacity,unreal.MaterialProperty.MP_OPACITY)
glint=custom(m,'float depth=smoothstep(250,2400,length(P-Camera));return lerp(float3(.55,.62,.7),float3(.14,.19,.25),depth)*Gain*(.45+.55*Seed);',{'Gain':scalar(m,2.4,'RainBrightness'),'Seed':phase_pixel,'P':position,'Camera':camera})
prop(glint,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
save(m)
print('WEATHER_MATERIALS_READY dense_gpu_rain=1')
