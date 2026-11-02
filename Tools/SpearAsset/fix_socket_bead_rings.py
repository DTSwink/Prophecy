"""Flat socket seat, contained sleeve, distinct collar profiles and round bead."""
import bpy,bmesh,math,ast,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components'];blade=next(o for o in art.objects if o.name.startswith('06 •'));mat=blade.data.materials[0]
regions={'gold':(.5,.75,.75,1),'gold_etched':(.875,1,.5,1),'lacquer':(.8125,.875,.75,1)}
AX,AY=.798,.603;norm=math.hypot(AX,AY);AX/=norm;AY/=norm;S=.00096
for filename,names in [('build_spear.py',{'atlas','mesh','activate','lathe'}),('refine_cast_gold.py',{'turn'}),('rebuild_reference_gold.py',{'ref','r3','bead'})]:
 tree=ast.parse((ROOT/'Tools/SpearAsset'/filename).read_text(encoding='utf-8'))
 exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'helpers','exec'))
def replace(prefix,replacement):
 old=[o for o in art.objects if o.name.startswith(prefix) and o!=replacement]
 name=old[0].name if old else prefix
 for ob in old:bpy.data.objects.remove(ob,do_unlink=True)
 replacement.name=name
END=ref((727,426)).y;BROAD=ref((681,395)).y;SEAT=1.6684;COLLAR_BOTTOM=SEAT-.0052;SLEEVE_TOP=COLLAR_BOTTOM+.0008
profile=[(END-.002,.0161),(END+.001,.0187),(END+.006,.0192),(BROAD-.013,.0190),(BROAD+.012,.0191),(SLEEVE_TOP,.0191)]
sleeve=turn('TEMP • contained engraved sleeve',profile,'gold_etched',40)
# Preserve the existing axial motif position; shortening the hidden end must
# not rescale the visible engraving on the rest of the sleeve.
uv=sleeve.data.uv_layers.get('UV0_SurfaceAtlas')
for p in sleeve.data.polygons:
 if p.index>=(len(profile)-1)*40:continue
 for li in p.loop_indices:
  co=sleeve.data.vertices[sleeve.data.loops[li].vertex_index].co
  uv.data[li].uv.y=.503+.494*(co.z-(END-.002))/(1.6840459108352661-(END-.002))
replace('05 •',sleeve)
collar_profile=[(COLLAR_BOTTOM,.01905),(COLLAR_BOTTOM+.00010,.02435),(COLLAR_BOTTOM+.00050,.0248),
 (SEAT-.00050,.0248),(SEAT-.00010,.02435),(SEAT,.01905)]
collar=turn('TEMP • straight-sided guard collar',collar_profile,'gold',48)
replace('Socket • thin flared neck ring',collar);collar['Reference_profile']='Straight-sided 5.2mm collar; small eased edges; axis-aligned flat guard seat'
# A closed elliptical torus gives the separate middle ring a genuinely round
# section, with its bore hidden around the sleeve and no extra retaining lobe.
vs=[];fs=[];uvs=[];rings=20;sides=48;R=.0221;r=.0043;half=.0092
for k in range(rings):
 t=math.tau*k/rings;radius=R+r*math.cos(t);z=BROAD+half*math.sin(t)
 for j in range(sides):
  a=math.tau*j/sides;vs.append((radius*math.cos(a),radius*math.sin(a),z))
for k in range(rings):
 for j in range(sides):
  fs.append((k*sides+j,k*sides+(j+1)%sides,((k+1)%rings)*sides+(j+1)%sides,((k+1)%rings)*sides+j))
  uvs.append([(j/sides,k/rings),((j+1)/sides,k/rings),((j+1)/sides,(k+1)/rings),(j/sides,(k+1)/rings)])
round_ring=mesh('TEMP • rounded middle ring',vs,fs,'gold',uvs,smooth=True)
custom=[]
for p in round_ring.data.polygons:
 for li in p.loop_indices:
  k,j=divmod(round_ring.data.loops[li].vertex_index,sides);t=math.tau*k/rings;a=math.tau*j/sides
  custom.append(tuple(Vector((math.cos(t)*math.cos(a)/r,math.cos(t)*math.sin(a)/r,math.sin(t)/half)).normalized()))
round_ring.data.normals_split_custom_set(custom);replace('Socket • broad asymmetrical middle ring',round_ring)
round_ring['Reference_profile']='Closed rounded ring with elliptical section; width18.4mm; diameter52.8mm'
axis=(r3((702,316))-r3((632,295))).normalized();cross=axis.cross(Vector((0,1,0))).normalized();up=axis.cross(cross).normalized()
small=bead('TEMP • round pierced bead',(644,298),.0098,1.0);replace('Tassel • pierced small',small);small['Reference_round_bead']=True
report={'guard_seat_z_m':SEAT,'collar_z_m':[COLLAR_BOTTOM,SEAT],'sleeve_top_z_m':SLEEVE_TOP,'sleeve_clearance_below_guard_mm':(SEAT-SLEEVE_TOP)*1000,'first_bead_sphere_radius_mm':9.8,'middle_ring_section':'rounded ellipse','middle_ring_axial_width_mm':18.4,'near_guard_collar':'straight sides, 0.4mm edge ease','objects':{}}
for ob in [sleeve,collar,round_ring,small]:
 bm=bmesh.new();bm.from_mesh(ob.data);closed=all(e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True);bm.free();assert closed and volume>0,(ob.name,closed,volume)
 report['objects'][ob.name]={'closed':closed,'volume_m3':volume,'triangles':sum(len(p.vertices)-2 for p in ob.data.polygons)}
for image in bpy.data.images:
 if image.name.startswith('T_ImperialSpear_') and image.source=='FILE':
  image.filepath=str(OUT/'Textures'/(image.name.split('.png')[0]+'.png'));image.reload()
  if '_ORM' in image.name:image.alpha_mode='CHANNEL_PACKED';image.colorspace_settings.name='Non-Color'
(OUT/'Seven_Point_Fit_Corrections.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
print(json.dumps(report))
