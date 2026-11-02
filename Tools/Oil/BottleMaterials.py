"""Authoritative oil bottle glass/cork/liquid material recipe. No scene mutations."""
import unreal as u
lib=u.MaterialEditingLibrary;assets=u.AssetToolsHelpers.get_asset_tools();root="/Game/_mygame/OilBottle"
def mat(name,folder=root+'/Materials'):
 m=u.load_asset(folder+'/'+name) or assets.create_asset(name,folder,u.Material,u.MaterialFactoryNew())
 for _ in range(32):
  if lib.get_num_material_expressions(m)==0:break
  lib.delete_all_material_expressions(m)
 assert lib.get_num_material_expressions(m)==0
 return m
def node(m,cls,**props):
 n=lib.create_material_expression(m,cls)
 for k,v in props.items():n.set_editor_property(k,v)
 return n
def scalar(m,name,value):
 n=next((o for o in u.ObjectIterator(u.MaterialExpressionScalarParameter)
         if o.get_outer()==m and str(o.get_editor_property('parameter_name'))==name),None)
 if n:n.set_editor_property('default_value',value);return n
 return node(m,u.MaterialExpressionScalarParameter,parameter_name=name,default_value=value)
def color(m,name,value):
 n=next((o for o in u.ObjectIterator(u.MaterialExpressionVectorParameter)
         if o.get_outer()==m and str(o.get_editor_property('parameter_name'))==name),None)
 if n:n.set_editor_property('default_value',u.LinearColor(*value,1));return n
 return node(m,u.MaterialExpressionVectorParameter,parameter_name=name,default_value=u.LinearColor(*value,1))
def wire(n,prop):assert lib.connect_material_property(n,'',prop)
def custom(m,code,inputs,kind=u.CustomMaterialOutputType.CMOT_FLOAT1):
 n=node(m,u.MaterialExpressionCustom,code=code,output_type=kind);entries=[]
 for name in inputs:
  e=u.CustomInput();e.set_editor_property('input_name',name);entries.append(e)
 n.set_editor_property('inputs',entries)
 for name,v in inputs.items():assert lib.connect_material_expressions(v,'',n,name)
 return n
def compile(m):lib.layout_material_expressions(m);lib.recompile_material(m)

def build_materials(overwrite=True):
    existing=[u.load_asset(root+"/Materials/"+n) for n in ["M_OilBottleGlass","M_OilBottleCork","M_OilBottleLiquid"]]
    if not overwrite and all(existing):return existing
    g=mat('M_OilBottleGlass')
    g.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
    g.set_editor_property('shading_model',u.MaterialShadingModel.MSM_THIN_TRANSLUCENT)
    g.set_editor_property('two_sided',False)
    g.set_editor_property('translucency_lighting_mode',u.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    g.set_editor_property('screen_space_reflections',False)
    g.set_editor_property('refraction_method',u.RefractionMode.RM_INDEX_OF_REFRACTION)
    wire(color(g,'Color',(1,1,1)),u.MaterialProperty.MP_BASE_COLOR)
    wire(scalar(g,'Roughness',.12),u.MaterialProperty.MP_ROUGHNESS)
    wire(scalar(g,'Specular',.5),u.MaterialProperty.MP_SPECULAR)
    wire(scalar(g,'Opacity',.02),u.MaterialProperty.MP_OPACITY)
    fade=scalar(g,'FragmentOpacity',1)
    wire(custom(g,'return 1+(IOR-1)*Strength*Fade;',{'IOR':scalar(g,'IOR',1.52),'Strength':scalar(g,'RefractionStrength',.004),'Fade':fade}),u.MaterialProperty.MP_REFRACTION)
    thin=node(g,u.MaterialExpressionThinTranslucentMaterialOutput)
    assert lib.connect_material_expressions(color(g,'Transmission',(1,1,1)),'',thin,'TransmittanceColor')
    # The original Fab render surface uses full grazing reflection coverage.
    # Keep the optional art control and shared fragment fade.
    coverage=custom(g,'float nv=abs(dot(normalize(N),normalize(V))); return Fade*lerp(Edge,1,smoothstep(.02,.22,nv));',
        {'Fade':fade,'Edge':scalar(g,'EdgeCoverage',1),'N':node(g,u.MaterialExpressionPixelNormalWS),'V':node(g,u.MaterialExpressionCameraVectorWS)})
    assert lib.connect_material_expressions(coverage,'',thin,'SurfaceCoverage')
    compile(g)
    c=mat('M_OilBottleCork')
    c.set_editor_property('blend_mode',u.BlendMode.BLEND_MASKED)
    c.set_editor_property('shading_model',u.MaterialShadingModel.MSM_DEFAULT_LIT)
    c.set_editor_property('two_sided',False);c.set_editor_property('dither_opacity_mask',True)
    wire(scalar(c,'FragmentOpacity',1),u.MaterialProperty.MP_OPACITY_MASK)
    wire(scalar(c,'Roughness',.82),u.MaterialProperty.MP_ROUGHNESS)
    wire(scalar(c,'Specular',.18),u.MaterialProperty.MP_SPECULAR)
    uv=node(c,u.MaterialExpressionTextureCoordinate)
    grain=custom(c,'''float2 p=UV*float2(38,26), cell=floor(p);
float h=frac(sin(dot(cell,float2(127.1,311.7)))*43758.5453);
float2 center=.25+.5*frac(float2(h,h*17.7));
float d=length((frac(p)-center)*float2(1,1.6));
float aa=max(.015,length(fwidth(p)));
float pore=(1-smoothstep(.10-aa,.19+aa,d))*step(.53,h);
float grain=lerp(.85,1.12,h);
return Tint*grain*lerp(1,.32,pore);''',{'UV':uv,'Tint':color(c,'Color',(.10,.048,.018))},u.CustomMaterialOutputType.CMOT_FLOAT3)
    wire(grain,u.MaterialProperty.MP_BASE_COLOR);compile(c)
    return g,c,build_liquid()

def build_liquid(liq=None):
    """Closed liquid volume: Beer absorption along a bounded refracted chord.

    The radius/base match ProphecyOilLiquid's cavity. This inexpensive optical
    approximation adds no scene capture, texture, collision or CPU update.
    """
    persistent=liq is None
    if persistent:
        liq=u.load_asset(root+'/Materials/M_OilBottleLiquid')
        if liq and u.EditorAssetLibrary.get_metadata_tag(liq,'OilLiquidOpticsVersion')=='2':return liq
        liq=liq or assets.create_asset('M_OilBottleLiquid',root+'/Materials',u.Material,u.MaterialFactoryNew())
    # Native constructor-loaded expressions can be rooted. Deleting them causes
    # an engine assertion; reconnect existing parameters/output instead. The old
    # disconnected calculation is retained once and is not evaluated at runtime.
    liq.set_editor_property('blend_mode',u.BlendMode.BLEND_TRANSLUCENT)
    liq.set_editor_property('translucency_lighting_mode',u.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    liq.set_editor_property('two_sided',False)
    wire(scalar(liq,'Opacity',0),u.MaterialProperty.MP_OPACITY)
    wire(scalar(liq,'Roughness',.035),u.MaterialProperty.MP_ROUGHNESS)
    wire(scalar(liq,'Specular',.45),u.MaterialProperty.MP_SPECULAR)
    liq.set_editor_property('refraction_method',u.RefractionMode.RM_INDEX_OF_REFRACTION)
    # UE's screen-space refraction displaces the composite as well as background
    # detail. Keep the offset small so it cannot visibly hollow out the bottle.
    wire(scalar(liq,'Refraction',1.003),u.MaterialProperty.MP_REFRACTION)
    p=node(liq,u.MaterialExpressionTransformPosition,
        transform_source_type=u.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
        transform_type=u.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    assert lib.connect_material_expressions(node(liq,u.MaterialExpressionWorldPosition),'',p,'')
    def local_vector(cls):
        n=node(liq,u.MaterialExpressionTransform,
            transform_source_type=u.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD,
            transform_type=u.MaterialVectorCoordTransform.TRANSFORM_LOCAL)
        assert lib.connect_material_expressions(node(liq,cls),'',n,'')
        return n
    lt=next((o for o in u.ObjectIterator(u.MaterialExpressionThinTranslucentMaterialOutput) if o.get_outer()==liq),None)
    lt=lt or node(liq,u.MaterialExpressionThinTranslucentMaterialOutput)
    absorption=custom(liq,'''float3 n=normalize(N),v=normalize(V);
float nv=saturate(abs(dot(n,v))+1e-5);
float3 d=refract(-v,n,1.0/1.47);
float a=max(dot(d.xy,d.xy),1e-5),b=dot(P.xy,d.xy);
float q=dot(P.xy,P.xy)-Radius*Radius;
float chord=max(0,(-b+sqrt(max(0,b*b-a*q)))/a);
float cap=d.z<-.0001 ? max(0,(.7-P.z)/d.z) : 1000;
float path=clamp(min(chord,cap)/(2*Radius),.025,2.5);
// Compensate UE's thin-sheet 1/NoV, then apply the volume's actual chord.
return pow(max(Tint,.001),path*nv*Density);''',
        {'Tint':color(liq,'Transmission',(.72,.32,.018)),'Density':scalar(liq,'Absorption',1),
         'Radius':scalar(liq,'CavityRadius',4.85),'P':p,
         'N':local_vector(u.MaterialExpressionPixelNormalWS),
         'V':local_vector(u.MaterialExpressionCameraVectorWS)},u.CustomMaterialOutputType.CMOT_FLOAT3)
    assert lib.connect_material_expressions(absorption,'',lt,'TransmittanceColor')
    liq.set_editor_property('shading_model',u.MaterialShadingModel.MSM_THIN_TRANSLUCENT);compile(liq)
    if persistent:u.EditorAssetLibrary.set_metadata_tag(liq,'OilLiquidOpticsVersion','2')
    return liq
