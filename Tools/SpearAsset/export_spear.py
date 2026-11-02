"""Build game exports from editable authored components and audit their geometry."""
import bpy, bmesh, math, json, runpy
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
source=bpy.data.scenes['Scene']
preserve_original_shape=bool(source.get('Preserve_original_blade_shape',False))
collision_version=int(source.get('GoldDetailCollisionVersion',0))
reference_assembly=collision_version>=2
gold_rings=collision_version>=1
expected_hulls=None if reference_assembly else (11 if gold_rings else 9)
art=bpy.data.collections['SPEAR • editable components']
old_collision=bpy.data.collections['SPEAR • UCX collision']
GRIP=1.235
SURFACE_ATTRIBUTES=('_SpearExport_NX','_SpearExport_NY','_SpearExport_NZ','_SpearExport_U','_SpearExport_V')
CAVITY_COLOR='PommelCavity'

def atlas_layer(data):
    return data.uv_layers.get('UV0_SurfaceAtlas') or next((u for u in data.uv_layers if u.active_render),data.uv_layers.active)

# Validate the current editable source and construct every version2 envelope
# BEFORE clearing either the previous GAME scene or the inspection colliders.
source_meshes=[ob for ob in art.objects if ob.type=='MESH']
assert source_meshes,'No editable source meshes'
lotus_pommel=any(ob.get('PommelDesign')=='lotus_bud' for ob in source_meshes)
source_materials=set()
source_coords=[]
for ob in source_meshes:
    source_uv=atlas_layer(ob.data)
    assert source_uv is not None,('Missing authored atlas UV',ob.name)
    assert len(source_uv.data)==len(ob.data.loops) and all(math.isfinite(c) for item in source_uv.data for c in item.uv),('Invalid source UV',ob.name)
    assert abs(ob.matrix_world.to_3x3().determinant())>1e-12,('Singular source transform',ob.name)
    assert len(ob.data.corner_normals)==len(ob.data.loops) and all(corner.vector.length>.5 and all(math.isfinite(c) for c in corner.vector) for corner in ob.data.corner_normals),('Invalid source normals',ob.name)
    assert len(ob.data.materials)==1 and ob.data.materials[0] is not None,('Expected one source material',ob.name)
    source_materials.add(ob.data.materials[0])
    assert not any(mod.show_render for mod in ob.modifiers),('Apply source render modifiers before export',ob.name)
    source_coords.extend(ob.matrix_world@v.co for v in ob.data.vertices)
expected_material_names={'M_ImperialSpear_PBR'}
assert {m.name for m in source_materials}==expected_material_names,('Unexpected source materials',source_materials)
assert all(math.isfinite(c) for point in source_coords for c in point),'Nonfinite source geometry'
source_bounds={'min':[min(p[i] for p in source_coords) for i in range(3)],'max':[max(p[i] for p in source_coords) for i in range(3)]}
source_bottom=source_bounds['min'][2]
overall_length=source_bounds['max'][2]-source_bottom
assert abs(source_bounds['max'][2]-2.2)<1e-5,source_bounds
assert (-.060<source_bottom<0 if lotus_pommel else abs(source_bottom)<1e-5),source_bounds
source_material=next(m for m in source_materials if m.name=='M_ImperialSpear_PBR')
cavity_enabled=any(ob.data.color_attributes.get(CAVITY_COLOR) is not None for ob in source_meshes)
if cavity_enabled:
    assert source_material.get('PommelCavityEnabled') and source_material.node_tree.nodes.get('PommelCavity_BaseOriginal'),'Apply the cavity material before exporting'
    assert source_material.get('PommelCavityGate')=='COLOR_R_GT_0.01','Reapply corrected Color.R-gated cavity material before exporting'
    SURFACE_ATTRIBUTES+=('_SpearExport_CR','_SpearExport_CG','_SpearExport_CB','_SpearExport_CA')
for material in source_materials:
    assert material.use_nodes and material.node_tree,('Missing source PBR node tree',material.name)
# Resolve before saving to another directory; relative strings otherwise change
# meaning after the first save. Preserve auxiliary scene image paths as well.
image_paths={image:Path(bpy.path.abspath(image.filepath,library=image.library)).resolve()
             for image in bpy.data.images if image.source=='FILE' and image.filepath}
for material in source_materials:
    for node in material.node_tree.nodes:
        if node.type=='TEX_IMAGE' and node.image and node.image.source=='FILE':
            assert node.image in image_paths and image_paths[node.image].is_file(),('Missing source texture',node.image.filepath)
if reference_assembly:
    for material in source_materials:
        pre_nodes=material.node_tree.nodes;pre_links=material.node_tree.links
        pre_principled=next(n for n in pre_nodes if n.type=='BSDF_PRINCIPLED')
        pre_orm=next(n for n in pre_nodes if n.type=='TEX_IMAGE' and n.image and '_ORM' in n.image.name)
        with Path(bpy.path.abspath(pre_orm.image.filepath)).open('rb') as handle:pre_header=handle.read(26)
        assert pre_header[:8]==b'\x89PNG\r\n\x1a\n' and pre_header[25]==6,'Source ORM must be RGBA'
        assert pre_orm.image.colorspace_settings.name=='Non-Color' and pre_orm.image.alpha_mode=='CHANNEL_PACKED'
        assert any(link.from_node==pre_orm and link.from_socket.name=='Alpha' and link.to_node==pre_principled and link.to_socket.name=='Specular IOR Level' for link in pre_links),('Missing packed source specular connection',material.name)
        assert not pre_principled.inputs['Alpha'].is_linked and abs(pre_principled.inputs['Alpha'].default_value-1)<1e-6
    helpers=runpy.run_path(str(ROOT/'Tools/SpearAsset/reference_collision_specs.py'))
    specs=helpers['build_reference_collision_specs'](art,GRIP)

def carry_surface_data(copy,original):
    """Scalar corner attributes survive joining/transforms/triangulation."""
    uv=atlas_layer(original.data)
    normal_matrix=original.matrix_world.to_3x3().inverted().transposed()
    normals=[(normal_matrix@corner.vector).normalized() for corner in original.data.corner_normals]
    assert len(normals)==len(copy.data.loops)
    columns=[[normal[i] for normal in normals] for i in range(3)]
    columns.extend([[item.uv[i] for item in uv.data] for i in range(2)])
    if cavity_enabled:
        authored=original.data.color_attributes.get(CAVITY_COLOR)
        if authored:
            assert authored.domain=='CORNER' and authored.data_type=='FLOAT_COLOR',('Invalid cavity color layer',original.name)
            colors=[tuple(item.color) for item in authored.data]
        else:colors=[(1.,1.,1.,1.)]*len(original.data.loops)
        assert len(colors)==len(original.data.loops)
        assert all(.45-1e-6<=c[0]<=1+1e-6 and abs(c[3]-1)<1e-6 and max(abs(c[0]-c[i]) for i in (1,2))<1e-6 for c in colors),('Invalid cavity color values',original.name)
        color=copy.data.color_attributes.get(CAVITY_COLOR) or copy.data.color_attributes.new(name=CAVITY_COLOR,type='FLOAT_COLOR',domain='CORNER')
        color.data.foreach_set('color',[v for c in colors for v in c])
        index=copy.data.color_attributes.find(CAVITY_COLOR)
        copy.data.color_attributes.active_color_index=index;copy.data.color_attributes.render_color_index=index
        columns.extend([[c[i] for c in colors] for i in range(4)])
    for name,values in zip(SURFACE_ATTRIBUTES,columns):
        existing=copy.data.attributes.get(name)
        if existing:copy.data.attributes.remove(existing)
        attr=copy.data.attributes.new(name=name,type='FLOAT',domain='CORNER')
        attr.data.foreach_set('value',values)

def restore_surface_data(ob):
    attrs=[ob.data.attributes[name] for name in SURFACE_ATTRIBUTES]
    assert all(len(attr.data)==len(ob.data.loops) for attr in attrs),'Triangulation dropped source corner data'
    normals=[Vector(tuple(attrs[i].data[j].value for i in range(3))).normalized() for j in range(len(ob.data.loops))]
    uv=ob.data.uv_layers['UV0_SurfaceAtlas']
    max_uv_error=0.0
    for j,item in enumerate(uv.data):
        source_uv=(attrs[3].data[j].value,attrs[4].data[j].value)
        max_uv_error=max(max_uv_error,max(abs(item.uv[i]-source_uv[i]) for i in range(2)))
        item.uv=source_uv
    ob.data.normals_split_custom_set([tuple(n) for n in normals]);ob.data.update()
    minimum_dot=min(corner.vector.dot(expected) for corner,expected in zip(ob.data.corner_normals,normals))
    assert minimum_dot>=.9999,('Source shading-normal restoration failed',minimum_dot)
    cavity_report=None
    if cavity_enabled:
        colors=[tuple(attrs[i].data[j].value for i in range(5,9)) for j in range(len(ob.data.loops))]
        color=ob.data.color_attributes.get(CAVITY_COLOR) or ob.data.color_attributes.new(name=CAVITY_COLOR,type='FLOAT_COLOR',domain='CORNER')
        color.data.foreach_set('color',[v for c in colors for v in c])
        index=ob.data.color_attributes.find(CAVITY_COLOR)
        ob.data.color_attributes.active_color_index=index;ob.data.color_attributes.render_color_index=index
        error=max(abs(item.color[i]-colors[j][i]) for j,item in enumerate(color.data) for i in range(4))
        assert error<1e-6,('Cavity color restoration failed',error)
        cavity_report={'name':CAVITY_COLOR,'domain':'CORNER','type':'FLOAT_COLOR','space':'linear',
            'encoding':'neutral grayscale RGB shade multiplier; alpha1','minimum_shade':min(c[0] for c in colors),
            'maximum_shade':max(c[0] for c in colors),'darkened_corners':sum(c[0]<.99999 for c in colors),
            'maximum_restore_error':error,'unmasked_export_copies_default_white':True,'protected_source_colors_modified':False}
    for name in SURFACE_ATTRIBUTES:ob.data.attributes.remove(ob.data.attributes[name])
    return {'source_corner_attributes_restored':True,'loops':len(normals),'minimum_normal_dot':minimum_dot,
            'maximum_uv_change_before_explicit_restore':max_uv_error,'cavity_vertex_color':cavity_report}
def active(ob):
    bpy.ops.object.select_all(action='DESELECT'); ob.hide_set(False); ob.select_set(True); bpy.context.view_layer.objects.active=ob
def duplicate(ob):
    q=ob.copy(); q.data=ob.data.copy(); return q
game=bpy.data.scenes.get('GAME • Unreal export') or bpy.data.scenes.new('GAME • Unreal export')
game.unit_settings.system='METRIC'; game.unit_settings.scale_length=1
for ob in list(game.objects): bpy.data.objects.remove(ob,do_unlink=True)
for ob in list(old_collision.objects):bpy.data.objects.remove(ob,do_unlink=True)
for ob in source_meshes:
    if ob.type=='MESH':
        copy=duplicate(ob)
        carry_surface_data(copy,ob)
        # Boolean tools can insert an unused UVMap before the real atlas.
        # Normalize export copies by name, never by whichever layer is first.
        uv=copy.data.uv_layers.get('UV0_SurfaceAtlas') or next((u for u in copy.data.uv_layers if u.active_render),copy.data.uv_layers.active)
        assert uv is not None,('Missing authored atlas UV',ob.name)
        uv.name='UV0_SurfaceAtlas'
        for layer in list(copy.data.uv_layers):
            if layer.name!='UV0_SurfaceAtlas': copy.data.uv_layers.remove(layer)
        uv=copy.data.uv_layers['UV0_SurfaceAtlas'];uv.active_render=True
        copy.data.uv_layers.active_index=0
        game.collection.objects.link(copy)
bpy.context.window.scene=game
bpy.ops.object.select_all(action='SELECT'); bpy.context.view_layer.objects.active=next(ob for ob in game.objects if ob.data.materials[0]==source_material); bpy.ops.object.join()
render=bpy.context.object; render.name='SM_ImperialSpear'; render.data.name='SM_ImperialSpear_LOD0'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
assert set(render.data.materials)==source_materials,'Join changed source material slots'
for v in render.data.vertices: v.co.z-=GRIP
render['Grip_reference_m']=GRIP; render['Length_m']=overall_length
render['Source_bottom_z_m']=source_bottom;render['PommelDesign']='lotus_bud' if lotus_pommel else source.get('PommelDesign','historical')
render['CollisionVersion']=collision_version
render['PommelCavityEnabled']=cavity_enabled
render['Texture_workflow']=('Single4096 atlas; BaseColor sRGB; ORM RGBA=AO/Roughness/Metallic/Specular IOR Level; NormalDX linear for Unreal' if reference_assembly else 'Single4096 atlas; BaseColor sRGB; ORM RGB=AO/Roughness/Metallic; NormalDX linear')
if lotus_pommel:render['Texture_workflow']+='; lotus pommel uses the existing plain-gold atlas tile and shared material'
render['Note']='Pivot at grip. +Z points to blade. Not engine-validated.'
# Add a separately packed lightmap UV set, leaving the authored atlas untouched.
uv0=render.data.uv_layers['UV0_SurfaceAtlas']
uv1=render.data.uv_layers.new(name='UV1_Lightmap'); render.data.uv_layers.active_index=1
active(render); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.008,area_weight=.3,correct_aspect=True,scale_to_bounds=True)
bpy.ops.object.mode_set(mode='OBJECT'); render.data.uv_layers.active_index=0; uv0.active_render=True
mod=render.modifiers.new('Explicit game triangulation','TRIANGULATE'); mod.quad_method='BEAUTY'; mod.ngon_method='BEAUTY'
if hasattr(mod,'keep_custom_normals'):mod.keep_custom_normals=True
bpy.ops.object.modifier_apply(modifier=mod.name)
surface_preservation=restore_surface_data(render)
def convex(name,coords):
    # Build at millimetre scale so Bullet's hull merge tolerance does not
    # flatten the small chased-metal profile; store the result in metres.
    data=bpy.data.meshes.new(name); data.from_pydata([tuple(c*1000 for c in v) for v in coords],[],[])
    bm=bmesh.new(); bm.from_mesh(data); result=bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose: bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    for v in bm.verts: v.co/=1000
    bm.to_mesh(data); bm.free()
    ob=bpy.data.objects.new(name,data); game.collection.objects.link(ob); ob.display_type='WIRE'; ob.hide_render=True
    return ob
def radial(z0,r0,z1,r1,n=12):
    return [(r*math.cos(a*2*math.pi/n),r*math.sin(a*2*math.pi/n),z-GRIP) for z,r in [(z0,r0),(z1,r1)] for a in range(n)]
hulls=[]; hull_metadata={}
def add_hull(coords,role,**metadata):
    ob=convex('UCX_SM_ImperialSpear_%02d'%len(hulls),coords)
    ob['CollisionRole']=role; hulls.append(ob)
    hull_metadata[ob.name]={'role':role,**metadata}
    return ob
if reference_assembly:
    for spec in specs:
        add_hull(spec['coords'],spec['role'],**{k:v for k,v in spec.items() if k not in ('coords','role')})
else:
    for role,coords in zip(('lower_shaft','forward_grip','upper_shaft','blunt_pommel','socket'),[
        radial(.1271,.016,1.1039,.016),radial(1.104,.0205,1.3679,.0205),
        radial(1.368,.016,1.5999,.016),radial(0,.0115,.127,.018),
        radial(1.6281,.0195,1.683,.0195) if gold_rings else radial(1.60,.0215,1.7139 if preserve_original_shape else 1.6699,.024)]):
        add_hull(coords,role)
# Sample exact section endpoints rather than filling the blade's concave waist.
profile=[(1.745,.020,.020),(1.765,.028,.025),(1.79,.044,.035),(1.812,.059,.043),(1.825,.058,.052),(1.836,.045,.050),(1.850,.036,.039),(1.868,.030,.032),(1.887,.029,.030),(1.91,.034,.033),(1.94,.041,.038),(1.97,.046,.043),(2.,.046,.044),(2.03,.041,.04),(2.07,.031,.03),(2.11,.02,.019),(2.15,.0108,.0105),(2.18,.0041,.004),(2.2,.00015,.00015)]
refined=(OUT/'BladeProfile_Refined.json').exists() and not preserve_original_shape and not reference_assembly
if refined: profile=json.loads((OUT/'BladeProfile_Refined.json').read_text(encoding='utf-8'))
def width(z):
    if z<=profile[0][0]: return profile[0][1:]
    for a,b in zip(profile,profile[1:]):
        if a[0]<=z<=b[0]:
            t=(z-a[0])/(b[0]-a[0]); return tuple(a[k]*(1-t)+b[k]*t for k in [1,2])
    return profile[-1][1:]
sections=([(5,1.745,1.81),(6,1.8101,1.868),(7,1.8681,1.97),(8,1.9701,2.2)] if reference_assembly else
          ([(5,1.67,1.78),(6,1.7801,1.868),(7,1.8681,1.97),(8,1.9701,2.2)] if refined else [(5,1.714,1.81),(6,1.8101,1.868),(7,1.8681,1.97),(8,1.9701,2.2)]))
for section_index,(idx,lo,hi) in enumerate(sections):
    inside=[p[0] for p in profile if lo<p[0]<hi]
    if refined: inside=inside[::3]
    zs=[lo]+inside+[hi]
    coords=[]
    for z in zs:
        if refined and idx==5 and z<profile[0][0]: continue
        wl,wr=width(z); t=max(.00035,.0114*(2.2-z)/.46) if refined else max(.0015,.0085*min(1,(2.201-z)/.16))
        if reference_assembly:
            t=max(.00015,.0085*min(1,(2.201-z)/.16)+.0001)
        if idx==5 and not reference_assembly:
            wl,wr=max(wl,.022 if refined else .038),max(wr,.022 if refined else .038); t=.0235 if refined else .0288
        if reference_assembly:
            # Match the accepted8-point face/bevel cross-section. The legacy
            # diamond cuts inside its shoulders; separate gold hulls cover
            # raised cast ornament without inflating the blade's thickness.
            coords += [(x,y,z-GRIP) for x,y in [(-wl,0),(-wl*.72,-t*.58),(0,-t),
                       (wr*.72,-t*.58),(wr,0),(wr*.72,t*.58),(0,t),(-wl*.72,t*.58)]]
        else:
            coords += [(-wl,0,z-GRIP),(wr,0,z-GRIP),(0,-t,z-GRIP),(0,t,z-GRIP)]
    if idx==5 and not reference_assembly:
        if refined:
            # The traced body before cosmetic bevels gives a compact convex hull.
            pixels=[(538,285),(553,273),(569,266),(600,270),(613,280),(611,290),(600,291),(604,310),(623,327),(608,350),(589,342),(575,342),(564,350),(558,371),(544,351),(537,330),(536,308)]
            rim=[(((x-172)*.603-(y-9)*.798)*.00096,2.2-((x-172)*.798+(y-9)*.603)*.00096) for x,y in pixels]
            coords += [(x,y,z-GRIP) for x,z in rim for y in [-.012,.012]]
            coords += [(x*.84,y,1.729+(z-1.729)*.84-GRIP) for x,z in rim for y in [-.0228,.0228]]
        else:
            rim=[(-.038,1.710),(-.047,1.757),(-.033,1.797),(-.022,1.807),(.043,1.797),(.049,1.787),(.020,1.724),(.008,1.718)]
            coords += [(x,y,z-GRIP) for x,z in rim for y in [-.0205,.0205]]
            coords += [(.78*x,y,1.758+(z-1.758)*.78-GRIP) for x,z in rim for y in [-.029,.029]]
    add_hull(coords,('blade_root','blade_shoulder','blade_waist','blade_tip')[section_index],source_section_z_m=[lo,hi])
if gold_rings and not reference_assembly:
    # Two small convex profiles follow the broadened ring crowns independently
    # of the narrow sleeve, keeping the original shaft/blade collision intact.
    for idx,profile in [(9,[(1.60,.016),(1.613,.0254),(1.620,.0254),(1.628,.0195)]),
                        (10,[(1.6831,.0195),(1.691,.0264),(1.699,.0264),(1.7139,.0195)])]:
        coords=[(r/math.cos(math.pi/12)*math.cos(j*math.tau/12),r/math.cos(math.pi/12)*math.sin(j*math.tau/12),z-GRIP) for z,r in profile for j in range(12)]
        add_hull(coords,'legacy_lower_ring' if idx==9 else 'legacy_upper_ring')
if reference_assembly: expected_hulls=len(specs)+len(sections)
assert len(hulls)==expected_hulls
render['CollisionHullCount']=len(hulls)
render['Collision']=f'{len(hulls)} authored convex UCX hulls; tassel cosmetic; rigid single body'
game['CollisionVersion']=collision_version;game['CollisionHullCount']=len(hulls)
sockets=[]
for name,loc in [('Grip',(0,0,GRIP)),('BladeTip',(0,0,2.2)),('Pommel',(0,0,source_bottom)),('Tassel',tuple(source.get('Tassel_socket',(.044,0,1.785))))]:
    ob=bpy.data.objects.new('SOCKET_SM_ImperialSpear_'+name,None); game.collection.objects.link(ob)
    ob.location=Vector(loc)-Vector((0,0,GRIP)); ob.empty_display_type='ARROWS'; ob.empty_display_size=.03; sockets.append(ob)
def stats(ob):
    bm=bmesh.new(); bm.from_mesh(ob.data); bm.normal_update()
    violation=0
    for f in bm.faces:
        origin=f.verts[0].co
        violation=max(violation,max((v.co-origin).dot(f.normal) for v in bm.verts))
    d={'name':ob.name,'vertices':len(bm.verts),'triangles':sum(len(f.verts)-2 for f in bm.faces),
       'boundary_edges':sum(e.is_boundary for e in bm.edges),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
       'volume_m3':bm.calc_volume(signed=True),'convex_max_plane_violation_m':violation,
       'bounds_grip_relative_m':{'min':[min(v.co[i] for v in bm.verts) for i in range(3)],'max':[max(v.co[i] for v in bm.verts) for i in range(3)]},
       **hull_metadata.get(ob.name,{})}
    bm.free(); return d
render_bounds={'min':[min(v.co[i] for v in render.data.vertices) for i in range(3)],
               'max':[max(v.co[i] for v in render.data.vertices) for i in range(3)]}
assert abs(render_bounds['min'][2]-(source_bottom-GRIP))<1e-5 and abs(render_bounds['max'][2]-(2.2-GRIP))<1e-5,render_bounds
report={'axis':'+Z to blade','pivot':'centre of moved grip','overall_length_m':overall_length,'grip_from_pommel_m':GRIP-source_bottom,
        'source_bottom_z_m':source_bottom,'grip_reference_source_z_m':GRIP,'grip_span_source_z_m':[1.115,1.355],
        'grip_span_from_pommel_m':[1.115-source_bottom,1.355-source_bottom],'render_vertices':len(render.data.vertices),'render_triangles':len(render.data.polygons),
        'material_slots':len(render.data.materials),'material_names':[m.name for m in render.data.materials],'uv_layers':[uv.name for uv in render.data.uv_layers],
        'render_bounds_grip_relative_m':render_bounds,
        'source_surface_preservation':surface_preservation,
        'collision_version':collision_version,'collision_hull_count':len(hulls),
        'collision':[stats(ob) for ob in hulls],'collision_excludes':['tassel ribbons','cord','beads','knots'],
        'simple_collision_eye_aperture_filled':reference_assembly,
        'unreal_import_validated':False}
assert len(hulls)==expected_hulls
for row in report['collision']:
    assert row['vertices']<=64 and row['nonmanifold_edges']==0 and row['volume_m3']>0 and row['convex_max_plane_violation_m']<1e-6,row
# Keep the editable scene's inspection hulls identical to the export hulls.
for ob in list(old_collision.objects): bpy.data.objects.remove(ob,do_unlink=True)
for ob in hulls:
    copy=duplicate(ob); copy.name='SOURCE_'+ob.name; old_collision.objects.link(copy)
    for v in copy.data.vertices: v.co.z+=GRIP
source['Collision']=f'{expected_hulls} convex hulls. Same geometry as FBX, shifted to source coordinates.'
assert all(math.isfinite(c) for v in render.data.vertices for c in v.co)
assert all(p.area>1e-14 for p in render.data.polygons),'Degenerate render triangles'

# Keep the packed alpha contract explicit. FBX does not guarantee transfer of
# this custom channel wiring; Unreal must use the supplied maps explicitly.
texture_contract={'atlas_size':[4096,4096],'BaseColor':{'color_space':'sRGB'},
    'ORM':{'color_space':'Non-Color','channels':{'R':'Ambient Occlusion','G':'Roughness','B':'Metallic'}},
    'NormalDX':{'color_space':'Non-Color','convention':'DirectX, Unreal'},
    'NormalGL':{'color_space':'Non-Color','convention':'OpenGL, Blender/glTF'},
    'surface':'opaque','fbx_material_wiring_validated':False,'unreal_material_validated':False}
if reference_assembly:
    texture_contract['ORM']['channels']['A']='Specular IOR Level'
    texture_contract['ORM']['alpha_mode']='CHANNEL_PACKED'
    texture_contract['ORM']['specular_behavior']='Per-texel authored alpha; current handle statistics are recorded in Final_Wood_Finish.json and Final_Grip_Finish.json.'
    orm_path=OUT/'Textures/T_ImperialSpear_ORM.png'
    with orm_path.open('rb') as handle: header=handle.read(26)
    assert header[:8]==b'\x89PNG\r\n\x1a\n' and header[25]==6,'Current ORM must be RGBA PNG'
    nodes=render.data.materials[0].node_tree.nodes;links=render.data.materials[0].node_tree.links
    principled=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    orm_node=next(n for n in nodes if n.type=='TEX_IMAGE' and n.image and 'T_ImperialSpear_ORM' in n.image.name)
    assert orm_node.image.colorspace_settings.name=='Non-Color' and orm_node.image.alpha_mode=='CHANNEL_PACKED'
    assert any(link.from_node==orm_node and link.from_socket.name=='Alpha' and link.to_node==principled and link.to_socket.name=='Specular IOR Level' for link in links),'Missing packed specular connection'
    assert not principled.inputs['Alpha'].is_linked and abs(principled.inputs['Alpha'].default_value-1)<1e-6,'Render surface must remain opaque'
report['texture_contract']=texture_contract
if lotus_pommel:
    texture_contract['pommel']={'material':'M_ImperialSpear_PBR','shared_existing_atlas':True,
        'plain_gold_uv_bounds':{'U':[.5015,.7485],'V':[.7515,.9985]},'preserves_existing_atlas':True}
if cavity_enabled:
    texture_contract['cavity_color']={'attribute':CAVITY_COLOR,'encoding':'linear neutral RGB shade, alpha1',
        'fbx_colors_type':'LINEAR','unreal_wiring':'Multiply BaseColor texture RGB by VertexColor RGB; other inputs unchanged',
        'glb_color_attribute':'COLOR_0','glb_multiply_count':1,'roughness_changed':False}
def export_fbx(path,objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects: o.hide_set(False); o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH','EMPTY'},
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',global_scale=1,axis_forward='-Y',axis_up='Z',
        use_mesh_modifiers=True,mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,bake_anim=False,path_mode='RELATIVE',
        colors_type='LINEAR',prioritize_active_color=True)

def repair_invalid_lod_normals(ob):
    """Repair cancellation at decimated ribbon tips without re-shading the LOD.

    Opposed ribbon faces can share a pinched tip after collapse, producing a
    zero smooth-fan normal despite valid triangle area. Give only those invalid
    corners the geometric normal of their own face; retain all valid corners.
    """
    mesh=ob.data
    original=[corner.vector.copy() for corner in mesh.corner_normals]
    assert len(original)==len(mesh.loops),('Missing LOD corner normals',ob.name)
    invalid={index for index,normal in enumerate(original)
             if not all(math.isfinite(c) for c in normal) or normal.length<=.5}
    result={'repaired_corners':len(invalid),'affected_faces':0,
            'method':'Own geometric face normal for invalid corners only',
            'minimum_preserved_normal_dot':1.0}
    if not invalid:return result
    repaired=[normal.copy() for normal in original]
    repaired_indices=set();affected_faces=0
    for poly in mesh.polygons:
        corners=invalid.intersection(poly.loop_indices)
        if not corners:continue
        assert len(poly.vertices)==3,('Normal repair requires triangles',ob.name,poly.index)
        a,b,c=(mesh.vertices[index].co for index in poly.vertices)
        normal=(b-a).cross(c-a)
        assert all(math.isfinite(value) for value in normal) and normal.length>2e-14,('Cannot repair degenerate LOD face',ob.name,poly.index)
        normal.normalize()
        for index in corners:repaired[index]=normal.copy()
        repaired_indices.update(corners);affected_faces+=1
    assert repaired_indices==invalid,('Unmapped invalid LOD corners',ob.name)
    mesh.normals_split_custom_set([tuple(normal) for normal in repaired]);mesh.update()
    actual=[corner.vector.copy() for corner in mesh.corner_normals]
    assert len(actual)==len(original)
    assert all(all(math.isfinite(c) for c in normal) and normal.length>.5 for normal in actual),('LOD normal repair failed',ob.name)
    preserved_dot=min((normal.normalized().dot(original[index].normalized())
                       for index,normal in enumerate(actual) if index not in invalid),default=1.0)
    repaired_dot=min(actual[index].normalized().dot(repaired[index]) for index in invalid)
    assert preserved_dot>=.9999,('Normal repair altered valid LOD shading',ob.name,preserved_dot)
    assert repaired_dot>=.9999,('LOD repaired normal differs from its face',ob.name,repaired_dot)
    result.update(affected_faces=affected_faces,minimum_preserved_normal_dot=preserved_dot,
                  minimum_repaired_face_normal_dot=repaired_dot)
    return result

export_fbx(OUT/'SM_ImperialSpear.fbx',[render]+hulls+sockets)
active(render)
gltf_options={}
restore_base=None
if cavity_enabled:
    # glTF multiplies COLOR_0 into base color natively. Export the unchanged
    # original texture graph so the Blender-only Color.R presence gate is not baked or
    # interpreted as a second color factor. Restore the live shader in finally.
    nodes=source_material.node_tree.nodes;links=source_material.node_tree.links
    bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    base=bsdf.inputs['Base Color'];restore_base=base.links[0].from_socket
    links.new(nodes['PommelCavity_BaseOriginal'].outputs[0],base)
    gltf_options={'export_vertex_color':'NAME','export_vertex_color_name':CAVITY_COLOR,'export_all_vertex_colors':False}
try:
    bpy.ops.export_scene.gltf(filepath=str(OUT/'SM_ImperialSpear.glb'),export_format='GLB',use_selection=True,use_active_scene=True,export_materials='EXPORT',export_yup=True,**gltf_options)
finally:
    if restore_base is not None:links.new(restore_base,base)
# Reduced LOD meshes share exact origin/scale and the original atlas.
report['lods']=[]
for number,ratio in [(1,.55),(2,.28)]:
    ob=duplicate(render); game.collection.objects.link(ob); ob.name='SM_ImperialSpear_LOD%d'%number; active(ob)
    dec=ob.modifiers.new('Distance reduction','DECIMATE'); dec.ratio=ratio; dec.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=dec.name)
    normal_repair=repair_invalid_lod_normals(ob)
    assert 0<len(ob.data.polygons)<len(render.data.polygons),('LOD did not reduce triangles',number)
    assert all(len(poly.vertices)==3 and poly.area>1e-14 for poly in ob.data.polygons),('Invalid LOD triangles',number)
    assert [layer.name for layer in ob.data.uv_layers]==['UV0_SurfaceAtlas','UV1_Lightmap'],('LOD UV layers changed',number)
    assert all(math.isfinite(c) for vertex in ob.data.vertices for c in vertex.co),('Nonfinite LOD vertices',number)
    assert all(math.isfinite(c) for layer in ob.data.uv_layers for item in layer.data for c in item.uv),('Nonfinite LOD UVs',number)
    assert all(corner.vector.length>.5 and all(math.isfinite(c) for c in corner.vector) for corner in ob.data.corner_normals),('Invalid LOD normals',number)
    assert list(ob.data.materials)==list(render.data.materials),('LOD material slots changed',number)
    assert set(p.material_index for p in ob.data.polygons)==set(range(len(ob.data.materials))),('LOD lost a material region',number)
    if cavity_enabled:
        color=ob.data.color_attributes.get(CAVITY_COLOR)
        assert color and color.domain=='CORNER' and color.data_type=='FLOAT_COLOR',('LOD lost cavity colors',number)
        assert all(.45-1e-6<=c.color[0]<=1+1e-6 and abs(c.color[3]-1)<1e-6
                   and max(abs(c.color[0]-c.color[i]) for i in (1,2))<1e-6 for c in color.data),('Invalid LOD cavity colors',number)
    row={'level':number,'vertices':len(ob.data.vertices),'triangles':len(ob.data.polygons),
         'uv_layers':[layer.name for layer in ob.data.uv_layers],'finite_surface_attributes':True,
         'normal_repair':normal_repair}; report['lods'].append(row)
    export_fbx(OUT/('SM_ImperialSpear_LOD%d.fbx'%number),[ob]); ob.hide_render=True; ob.hide_set(True)
for o in hulls+sockets: o.hide_set(True)
active(render)
(OUT/'Asset_Report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for image,absolute_path in image_paths.items():
    image.filepath=bpy.path.relpath(str(absolute_path),start=str(OUT))
# Paths above are already relative to OUT, not the currently open work blend.
# Disable Blender's second relocation or it would reinterpret //Textures here.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ImperialSpear_Game.blend'),relative_remap=False)
bpy.context.window.scene=source
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ImperialSpear_Source.blend'),relative_remap=False)
print(json.dumps(report))
