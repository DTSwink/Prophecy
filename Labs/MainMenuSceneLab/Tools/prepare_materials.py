"""Build ONLY this isolated lab's materials, through Unreal Python."""
import json,pathlib,unreal
assert pathlib.Path(unreal.Paths.get_project_file_path()).stem=='MainMenuSceneLab'
LIB=unreal.MaterialEditingLibrary
ROOT='/Game/MenuScene'
out=pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/'Validation'
out.mkdir(parents=True,exist_ok=True)
def material(name):
 m=unreal.load_asset(ROOT+'/'+name)
 if not m:m=unreal.AssetToolsHelpers.get_asset_tools().create_asset(name,ROOT,unreal.Material,unreal.MaterialFactoryNew())
 LIB.delete_all_material_expressions(m)
 return m
def node(m,cls,**props):
 n=LIB.create_material_expression(m,cls)
 for k,v in props.items():n.set_editor_property(k,v)
 return n
def scalar(m,v,name=None):
 return node(m,unreal.MaterialExpressionScalarParameter,parameter_name=name,default_value=v) if name else node(m,unreal.MaterialExpressionConstant,r=v)
def vector(m,v):return node(m,unreal.MaterialExpressionConstant3Vector,constant=unreal.LinearColor(*v,1))
def prop(n,p,output=''):LIB.connect_material_property(n,output,p)
def custom(m,code,inputs,output=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
 custom_inputs=[]
 for k in inputs:
  item=unreal.CustomInput();item.set_editor_property('input_name',k);custom_inputs.append(item)
 n=node(m,unreal.MaterialExpressionCustom,code=code,output_type=output,inputs=custom_inputs)
 for k,v in inputs.items():LIB.connect_material_expressions(v,'',n,k)
 return n
def save(m):
 LIB.recompile_material(m)
 assert unreal.EditorAssetLibrary.save_loaded_asset(m,only_if_is_dirty=False), 'Could not save '+m.get_path_name()+'; close the scene preview first'

noise='''
struct Noise {
 float hash(float2 p){return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453);}
 float n(float2 p){float2 i=floor(p),f=frac(p);f=f*f*(3-2*f);return lerp(lerp(hash(i),hash(i+float2(1,0)),f.x),lerp(hash(i+float2(0,1)),hash(i+1),f.x),f.y);}
 float fbm(float2 p){return .52*n(p)+.27*n(p*2.03+17)+.14*n(p*4.11-9)+.07*n(p*8.31);}
}; Noise q;
'''
m=material('M_Ground');p=node(m,unreal.MaterialExpressionWorldPosition)
m.set_editor_property('tangent_space_normal',False)
ground_inputs={'P':p,'Scale':scalar(m,1,'GroundScale'),'Shape':scalar(m,1,'GroundShape')}
ground_field=custom(m,noise+'''
float2 xy=P.xy/max(.1,Scale);
// Keep the earlier fine mineral bed available at Shape=0.
float large=q.fbm(xy*.15);
float fine=q.fbm(xy*.8+float2(large*5,large*3));
float legacy=pow(smoothstep(.32,.7,large*.65+fine*.35),2.0);
float legacyVeins=pow(saturate(1-abs(q.fbm(xy*.11)*2-1)),18);

// One transported phase field makes connected, long folds. Summing separate
// crossing waves created the rejected islands; all finer ridges follow this flow.
float2 uv=xy/38;
float2 broadWarp=float2(q.fbm(uv*.55+float2(13,5)),q.fbm(uv*.55+float2(-8,31)))-.5;
float2 flow=uv+3.2*broadWarp;
float2 fineWarp=float2(q.fbm(flow*1.7+float2(7,-4)),q.fbm(flow*1.7+float2(23,8)))-.5;
flow+=1.0*fineWarp;
float phase=6.2831853*(flow.x*.62+flow.y*.31)
            +1.9*sin(flow.y*.74+flow.x*.22)+.7*sin(flow.y*1.91-flow.x*.33);
float phaseWidth=max(abs(ddx(phase)),abs(ddy(phase)));
float wave=sin(phase)*exp(-.065*phaseWidth*phaseWidth);
float ribbon=pow(saturate(.5+.5*wave),4.0);
float strandPhase=phase*4.13+1.4*q.fbm(flow*3.2);
float strandWidth=max(abs(ddx(strandPhase)),abs(ddy(strandPhase)));
float strand=pow(saturate(.5+.5*sin(strandPhase)*exp(-.065*strandWidth*strandWidth)),7.0);
float etchPhase=phase*12.7+.8*sin(flow.y*6.1);
float etchWidth=max(abs(ddx(etchPhase)),abs(ddy(etchPhase)));
float etch=sin(etchPhase)*exp(-.09*etchWidth*etchWidth);
float broad=(.055+.44*ribbon+.32*strand)*(.86+.14*fine);
float crest=strand*(.72+.28*etch);
float pigment=lerp(legacy,broad,saturate(Shape));
float veins=lerp(legacyVeins,crest,saturate(Shape));
// Submerged etched bed, not a second large water-surface normal.
float height=(.18*wave+.012*etch)*saturate(Shape);
return float4(pigment,veins,height,0);
''',ground_inputs,unreal.CustomMaterialOutputType.CMOT_FLOAT4)
c=custom(m,'''
float mottling=pow(saturate(Field.x),max(.01,Contrast));
float3 low=lerp(float3(.019,.00022,.0005),float3(.0008,.000015,.000025),Darkness);
float3 high=lerp(float3(.46,.0011,.0022),float3(.22,.0011,.0022),Shape);
return lerp(low,high,mottling)+float3(.075,.00009,.0002)*Field.y*mottling;
''',{'Field':ground_field,'Shape':ground_inputs['Shape'],'Darkness':scalar(m,1,'GroundDarkness'),'Contrast':scalar(m,1,'GroundContrast')})
bed_normal=custom(m,'''
// Derive a world-space normal from the very same field used for pigment. Screen
// derivatives resolve the low-poly bed without inventing disconnected bump noise.
float2 dx=ddx(P.xy),dy=ddy(P.xy);
float det=dx.x*dy.y-dx.y*dy.x;
if(abs(det)<.000001)return float3(0,0,1);
float hx=ddx(Field.z),hy=ddy(Field.z);
float2 slope=float2(hx*dy.y-hy*dx.y,hy*dx.x-hx*dy.x)/det;
return normalize(float3(-slope,1));
''',{'P':p,'Field':ground_field})
prop(bed_normal,unreal.MaterialProperty.MP_NORMAL)
prop(c,unreal.MaterialProperty.MP_BASE_COLOR);prop(scalar(m,1),unreal.MaterialProperty.MP_ROUGHNESS)
prop(scalar(m,0),unreal.MaterialProperty.MP_SPECULAR)
e=custom(m,'return C * Gain;',{'C':c,'Gain':scalar(m,.32,'BedGlow')});prop(e,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
save(m)

m=material('M_Water')
m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
m.set_editor_property('translucency_lighting_mode',unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
m.set_editor_property('use_planar_forward_reflections',True)
m.set_editor_property('tangent_space_normal',False)
m.set_editor_property('two_sided',True)
m.set_editor_property('refraction_method',unreal.RefractionMode.RM_2D_OFFSET)
p=node(m,unreal.MaterialExpressionWorldPosition)
t=scalar(m,0,'SceneTime')
origin=node(m,unreal.MaterialExpressionVectorParameter,parameter_name='FieldOrigin',default_value=unreal.LinearColor(0,140,0,0))
texture=node(m,unreal.MaterialExpressionTextureObjectParameter,parameter_name='WaterField',texture=unreal.load_asset('/Engine/EngineResources/Black'))
uv_a=custom(m,'return P.xy/145 + float2(T*.007,T*.003);',{'P':p,'T':t},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
uv_b=custom(m,'return float2(dot(P.xy,float2(.6,.8)),dot(P.xy,float2(-.8,.6)))/53 + float2(-T*.009,T*.012);',{'P':p,'T':t},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
normal_texture=unreal.load_asset('/Water/Textures/Normals/T_Water_TilingNormal_With_Height_02_Softened')
a=node(m,unreal.MaterialExpressionTextureSample,texture=normal_texture,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
b=node(m,unreal.MaterialExpressionTextureSample,texture=normal_texture,sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
LIB.connect_material_expressions(uv_a,'',a,'Coordinates');LIB.connect_material_expressions(uv_b,'',b,'Coordinates')
rain_common=(pathlib.Path(__file__).parent/'rain_common.ush').read_text()
water_code=rain_common+'''
float2 uv=(P.xy-Origin.xy)/1000+.5;
float edge=saturate(min(min(uv.x,uv.y),min(1-uv.x,1-uv.y))*30);
// Epic's normal stage outputs signed world XYZ and foam in alpha (not height).
float3 sim=Texture2DSampleLevel(Field,FieldSampler,clamp(uv,.002,.998),0).xyz;
float2 live=sim.xy/max(.25,sim.z)*edge*Interaction;
float2 bn=B.xy*2-1;
float2 fine=float2(.6*bn.x-.8*bn.y,.8*bn.x+.6*bn.y);
// Almost flat between events; slow broad ocean normals hid the actual impacts.
float2 slope=live+((A.xy*2-1)*.55+fine*.3)*Wind*.02;
// Deterministic visual rain layer. The live Niagara collision field stays independent.
[branch] if(RainAmount>.0001 && RainStrength>.0001){
 SceneRain rain;int2 cell=int2(floor(P.xy/22));
 int reach=min(3,max(1,(int)ceil(32*RainSize/22)));
 float2 pixelDX=ddx(P.xy),pixelDY=ddy(P.xy);
 // Only visit occupied layers: legacy saved amounts <=1 retain their cost/look.
 [loop] for(uint layer=0;layer<(uint)min(4,ceil(RainAmount));++layer){
 [loop] for(int y=-reach;y<=reach;y++) [loop] for(int x=-reach;x<=reach;x++){
  int2 c=cell+int2(x,y);
  if(layer+rain.hash(c,5+97*layer)<RainAmount){
   // Continue the previous impact while the next drop falls. Shared seed/time
   // still puts age0 exactly at the corresponding streak's ground contact.
   float age=rain.age(c,RainTime-1.0,layer);
   if(age<1.05){
    float2 delta=P.xy-rain.center(c,layer);float radius=length(delta);
    float front=(.7+28*age)*RainSize;
    float intrinsicWidth=(1.25+1.1*age)*RainSize;
    // Filter along the ring gradient: grazing depth must not erase its
    // well-resolved left/right arcs.
    float2 radial=delta/max(radius,.1);
    float footprint=abs(dot(radial,pixelDX))+abs(dot(radial,pixelDY));
    float width=sqrt(intrinsicWidth*intrinsicWidth+.32*footprint*footprint);
    float d=radius-front;
    if(abs(d)<width*3){
     float packet=(d/width)*exp(-d*d/(width*width));
     float fade=exp(-2.2*age)*smoothstep(0,.035,age)*(1-smoothstep(.8,1.05,age));
     float energy=intrinsicWidth/max(width,.1);
     slope+=radial*packet*fade*energy*.38*RainStrength;
    }
   }
  }
 }
 }
}
'''
water_inputs={'P':p,'T':t,'Origin':origin,'Field':texture,'A':a,'B':b,'Wind':scalar(m,1,'WindStrength'),'Interaction':scalar(m,1,'InteractionStrength'),'RainAmount':scalar(m,.35,'RainAmount'),'RainTime':scalar(m,0,'RainTime'),'RainStrength':scalar(m,.35,'RainStrength'),'RainSize':scalar(m,1,'RainSize')}
n=custom(m,water_code+'return normalize(float3(slope,1));',water_inputs)
prop(n,unreal.MaterialProperty.MP_NORMAL)
depth=node(m,unreal.MaterialExpressionSceneDepth)
pixel_depth=node(m,unreal.MaterialExpressionPixelDepth)
refract=custom(m,'return float2(N.y,N.x)*.03*saturate((D-PD)/20)*saturate(650/max(PD,1));',{'N':n,'D':depth,'PD':pixel_depth},unreal.CustomMaterialOutputType.CMOT_FLOAT2)
prop(refract,unreal.MaterialProperty.MP_REFRACTION)
prop(vector(m,(.016,.0003,.00065)),unreal.MaterialProperty.MP_BASE_COLOR)
prop(scalar(m,.115,'WaterRoughness'),unreal.MaterialProperty.MP_ROUGHNESS)
prop(scalar(m,.255),unreal.MaterialProperty.MP_SPECULAR)
prop(scalar(m,0),unreal.MaterialProperty.MP_METALLIC)
f=node(m,unreal.MaterialExpressionFresnel,exponent=5,base_reflect_fraction=.0204)
alpha=custom(m,'return .07 + .86*F;',{'F':f},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
prop(alpha,unreal.MaterialProperty.MP_OPACITY)
save(m)

m=material('M_Mannequin')
LIB.set_material_usage(m,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
tex=node(m,unreal.MaterialExpressionTextureSample,texture=unreal.load_asset('/Game/Characters/UEFN_Mannequin/Textures/T_UEFN_Mannequin_N'),sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
prop(tex,unreal.MaterialProperty.MP_NORMAL,'RGB')
prop(vector(m,(.12,.112,.105)),unreal.MaterialProperty.MP_BASE_COLOR)
prop(scalar(m,.48),unreal.MaterialProperty.MP_METALLIC)
prop(scalar(m,.3,'BodyRoughness'),unreal.MaterialProperty.MP_ROUGHNESS)
prop(scalar(m,.5),unreal.MaterialProperty.MP_SPECULAR)
save(m)

m=material('M_Softbox');m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT);m.set_editor_property('two_sided',True)
m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_MASKED)
m.set_editor_property('opacity_mask_clip_value',.025)
LIB.set_material_usage(m,unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH)
uv=node(m,unreal.MaterialExpressionTextureCoordinate)
glow=custom(m,'float end=pow(smoothstep(0,.065,UV.x),1.5)*smoothstep(0,.04,1-UV.x);float width=lerp(.055,.46,smoothstep(0,.3,UV.x));float edge=1-smoothstep(.05,1,abs(UV.y-.5)/width);return float3(2.2,2.05,1.9)*end*edge;',{'UV':uv})
prop(glow,unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mask=custom(m,'return C.r/2.2;',{'C':glow},unreal.CustomMaterialOutputType.CMOT_FLOAT1)
prop(mask,unreal.MaterialProperty.MP_OPACITY_MASK);save(m)
exec((pathlib.Path(__file__).parent/'weather_materials.py').read_text(),globals())
exec((pathlib.Path(__file__).parent/'wet_material.py').read_text(),globals())
exec((pathlib.Path(__file__).parent/'smoke_material.py').read_text(),globals())
(out/'materials.json').write_text(json.dumps({'created':['M_Ground','M_Water','M_Mannequin','M_Softbox'],'water':'surface forward translucency with planar reflections, Epic Niagara signed world normals and two authored water-normal texture layers','scope':'/Game/MenuScene inside MainMenuSceneLab only'},indent=2),encoding='utf-8')
print('MENU_SCENE_MATERIALS_READY')
