"""One closed crown casting, with explicit narrow chamfer and buried guard foot.

Pure geometry generation: no Blender calls or changes to the live scene.
The cast volume replaces the two separated front/back relief slabs.
"""
from collections import defaultdict, deque
from pathlib import Path
import importlib.util
import json
import math
import numpy as np
import mapbox_earcut
from shapely.geometry import Polygon, Point
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points
from shapely import constrained_delaunay_triangles

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'Saved/Diagnostics/ImperialSpear/UnifiedCrownMesh.json'
spec=importlib.util.spec_from_file_location('casting_outline',ROOT/'Tools/SpearAsset/generate_clean_casting_mesh.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)

STALK=[(466,218),(474,227),(487,232),(494,233),(496,225),(498,234),(509,235),(519,241),(525,252),(520,258),(515,246),(508,241),(498,239),(493,243),(492,238),(479,235),(470,229)]
SEGMENTS=[
 ((558,245),(568,251),(569,261)),((570,273),(558,283),(547,285)),((532,288),(521,279),(520,267)),
 ((518,258),(522,252),(531,252)),((537,251),(543,256),(543,262)),((543,267),(538,269),(534,266)),
 ((531,264),(532,261),(534,260)),((535,260),(536,261),(537,262)),((535,262),(535,264),(537,264)),
 ((540,265),(540,260),(537,258)),((532,254),(526,256),(526,263)),((528,267),(533,270),(541,270)),
 ((549,271),(554,266),(554,260)),((556,255),(553,251),(548,249))]

def bezier_chain(start,segments,step=1.6):
 result=[np.asarray(start,dtype=float)];a=result[0]
 for c1,c2,end in segments:
  b,c,d=[np.asarray(v,dtype=float) for v in (c1,c2,end)]
  count=max(4,math.ceil((np.linalg.norm(b-a)+np.linalg.norm(c-b)+np.linalg.norm(d-c))/step))
  for j in range(1,count+1):
   t=j/count;result.append((1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d)
  a=d
 return result

def components(shape):
 if shape.is_empty:return []
 if shape.geom_type=='Polygon':return [orient(shape,sign=1)]
 if shape.geom_type=='MultiPolygon':return [orient(p,sign=1) for p in shape.geoms]
 raise ValueError(('Unexpected polygon type',shape.geom_type))

def smooth_stalk():
 return reference.smooth_polygon(STALK,sharp=(0,4,9,13),samples=3)

def rounded_key(p):return tuple(round(float(v),11) for v in p)

def build():
 stalk=Polygon(smooth_stalk()).buffer(0)
 spiral=Polygon([reference.ref(p) for p in bezier_chain((548,249),SEGMENTS)[:-1]]).buffer(0)
 footprint=stalk.union(spiral).buffer(0)
 guard=Polygon(reference.smooth_polygon(reference.OUTLINE)).buffer(0)
 untrimmed_area=footprint.area
 # Carry the casting far enough under the broad housing bevel to hide its
 # terminal wall. A 0.4 mm overlap ended before the housing rose above the
 # steel; pushing that shallow joint down exposed a silver wedge.
 footprint=footprint.difference(guard.buffer(-.0018,quad_segs=12)).buffer(0)
 assert footprint.is_valid and footprint.geom_type=='Polygon',('Crown disconnected by trim',footprint.geom_type)
 assert footprint.area>0
 insets=[0,.0006,.0007]
 half_depths=[.0106,.0112,.0113]
 shapes=[footprint]+[footprint.buffer(-v,quad_segs=8).buffer(0) for v in insets[1:]]
 for a,b in zip(shapes,shapes[1:]):assert b.difference(a).area<1e-14
 vertices=[];faces=[];regions=[];lookup={};side_level={};boundary_lookup={}
 for side in (-1,1):
  for k,shape in enumerate(shapes):
   for poly in components(shape):
    for ring in [poly.exterior,*poly.interiors]:
     for p in list(ring.coords)[:-1]:
      key=rounded_key(p);full=(side,k,key)
      if full not in side_level:
       index=len(vertices);vertices.append((float(p[0]),side*half_depths[k],float(p[1])))
       side_level[full]=index
      boundary_lookup[(k,key)]=p

 def id_at(point,side,levels):
  key=rounded_key(point)
  found=[side_level[(side,k,key)] for k in levels if (side,k,key) in side_level]
  assert len(found)==1,('Missing/ambiguous boundary point',point,levels,len(found))
  return found[0]

 def triangulate_region(poly,side,levels,label):
  rings=[list(poly.exterior.coords)[:-1]]+[list(r.coords)[:-1] for r in poly.interiors]
  points=[p for ring in rings for p in ring]
  ends=np.cumsum([len(r) for r in rings],dtype=np.uint32)
  coordinates=np.asarray(points,dtype=np.float64)
  if label.startswith('cap_'):
   triangles=mapbox_earcut.triangulate_float64(coordinates,ends).reshape(-1,3)
  else:
   point_index={tuple(p):i for i,p in enumerate(coordinates)}
   triangles=np.asarray([[point_index[tuple(p)] for p in list(t.exterior.coords)[:3]]
                        for t in constrained_delaunay_triangles(poly).geoms],dtype=np.uint32)
  ids=[id_at(p,side,levels) for p in points]
  if label.startswith('chamfer_'):
   # Even constrained Delaunay can retain a short same-height chord across a
   # narrow tip. Flip internal diagonals only when projected coverage stays
   # identical and the actual 3D chamfer inclination becomes closer to45deg.
   xyz=np.asarray([vertices[i] for i in ids],dtype=float)
   triangles=[list(map(int,t)) for t in triangles]
   def projected_area(tri):
    a,b,c=coordinates[tri];u,v=b-a,c-a;return abs(float(u[0]*v[1]-u[1]*v[0]))*.5
   def cost(tri):
    a,b,c=xyz[tri];normal=np.cross(b-a,c-a);length=np.linalg.norm(normal)
    if length<1e-15:return float('inf')
    angle=math.degrees(math.acos(min(1,max(0,abs(normal[1])/length))))
    return projected_area(tri)*(angle-45)**2
   for _ in range(6):
    connections=defaultdict(list)
    for ti,tri in enumerate(triangles):
     for a,b in zip(tri,tri[1:]+tri[:1]):connections[tuple(sorted((a,b)))].append(ti)
    changed=False;claimed=set()
    for (a,b),pair in connections.items():
     if len(pair)!=2 or any(i in claimed for i in pair):continue
     i,j=pair;c=next(v for v in triangles[i] if v not in (a,b));d=next(v for v in triangles[j] if v not in (a,b))
     if c==d:continue
     proposal=[[c,d,a],[d,c,b]]
     old_area=projected_area(triangles[i])+projected_area(triangles[j])
     areas=[projected_area(t) for t in proposal]
     if min(areas)<1e-16 or abs(sum(areas)-old_area)>max(1e-15,old_area*1e-7):continue
     before=cost(triangles[i])+cost(triangles[j]);after=sum(cost(t) for t in proposal)
     if after<before-1e-13:
      triangles[i],triangles[j]=proposal;claimed.update(pair);changed=True
    if not changed:break
   triangles=np.asarray(triangles,dtype=np.uint32)
  area=0
  for tri in triangles:
   polygon=Polygon(coordinates[tri]);assert polygon.area>1e-16
   assert polygon.difference(poly).area<1e-14,('Crossed bevel strip',label)
   area+=polygon.area;faces.append([ids[int(i)] for i in tri]);regions.append(label)
  assert abs(area-poly.area)<max(1e-13,poly.area*1e-8)

 for side in (-1,1):
  for k in range(len(shapes)-1):
   for poly in components(shapes[k].difference(shapes[k+1])):
    triangulate_region(poly,side,(k,k+1),f'chamfer_{side}_{k}')
  for poly in components(shapes[-1]):triangulate_region(poly,side,(len(shapes)-1,),f'cap_{side}')
 # Same original footprint perimeter on front/back; close every outer/hole wall.
 for poly in components(footprint):
  for ring in [poly.exterior,*poly.interiors]:
   points=list(ring.coords)[:-1]
   for a,b in zip(points,points[1:]+points[:1]):
    ia,ib=id_at(a,-1,(0,)),id_at(b,-1,(0,));ja,jb=id_at(a,1,(0,)),id_at(b,1,(0,))
    faces.extend([[ia,ib,jb],[ia,jb,ja]]);regions.extend(['wall','wall'])

 # Drop vertices earcut removed as collinear only if they are unused globally.
 used=sorted({v for f in faces for v in f});remap={old:new for new,old in enumerate(used)}
 vertices=[vertices[i] for i in used];faces=[[remap[i] for i in f] for f in faces]
 edges=defaultdict(list)
 for fi,face in enumerate(faces):
  for a,b in zip(face,face[1:]+face[:1]):edges[tuple(sorted((a,b)))].append((fi,a<b))
 bad=[(e,ls) for e,ls in edges.items() if len(ls)!=2]
 assert not bad,('Non-manifold crown',bad[:6])
 reverse={0:False};queue=deque([0])
 while queue:
  fi=queue.popleft()
  for a,b in zip(faces[fi],faces[fi][1:]+faces[fi][:1]):
   links=edges[tuple(sorted((a,b)))];other=links[1] if links[0][0]==fi else links[0]
   value=reverse[fi]^((a<b)==other[1])
   if other[0] in reverse:assert reverse[other[0]]==value
   else:reverse[other[0]]=value;queue.append(other[0])
 assert len(reverse)==len(faces),'Crown is not one connected solid'
 for fi,flag in reverse.items():
  if flag:faces[fi].reverse()
 array=np.asarray(vertices,dtype=float)
 volume=sum(float(np.dot(array[f[0]],np.cross(array[f[1]],array[f[2]]))) for f in faces)/6
 if volume<0:
  for face in faces:face.reverse()
  volume=-volume
 assert volume>0 and np.isfinite(array).all()
 gradient_cache={}
 def outward_at(x,z,fallback):
  key=rounded_key((x,z))
  if key in gradient_cache:return gradient_cache[key]
  step=.000003
  def signed(px,pz):
   point=Point(px,pz);distance=footprint.boundary.distance(point)
   return -distance if footprint.covers(point) else distance
  value=np.array(((signed(x+step,z)-signed(x-step,z))/(2*step),
                  (signed(x,z+step)-signed(x,z-step))/(2*step)))
  length=np.linalg.norm(value)
  if length<1e-7:
   value=np.asarray((fallback[0],fallback[2]));length=np.linalg.norm(value)
  assert length>1e-9
  value/=length;gradient_cache[key]=value
  return value
 normals=[]
 inclination=[]
 for face,label in zip(faces,regions):
  a,b,c=array[face];normal=np.cross(b-a,c-a);norm=np.linalg.norm(normal);assert norm>1e-13
  normal/=norm
  if label.startswith('chamfer_'):
   inclination.append((math.degrees(math.acos(min(1,max(0,abs(normal[1]))))),norm*.5))
  face_normals=[]
  for vi in face:
   x,y,z=array[vi];side=1 if y>0 else -1
   if label.startswith('cap_'):corner=np.array((0,side,0))
   else:
    outward=outward_at(x,z,normal)
    corner=np.array((outward[0],side if label.startswith('chamfer_') else 0,outward[1]))
    corner/=np.linalg.norm(corner)
    # The distance-field gradient is ambiguous at a sharp terminal corner.
    # Split those few corners rather than interpolating a backward normal.
    if float(np.dot(corner,normal))<.5:corner=normal.copy()
   face_normals.append(corner.tolist())
  normals.append(face_normals)
 body_distance=[];nearest=[];layer_depth=[]
 for x,y,z in vertices:
  point=Point(x,z);distance=guard.boundary.distance(point)
  body_distance.append(-distance if guard.covers(point) else distance)
  q=nearest_points(point,guard.boundary)[1];nearest.append([q.x,q.y])
  layer_depth.append(abs(y)-.0083)
 report={'construction':'One connected crown casting replacing separated mirrored slabs',
  'vertices':len(vertices),'triangles':len(faces),'closed_manifold':True,'consistent_winding':True,
  'positive_volume_m3':volume,'projected_strips_checked':True,'original_footprint_area_m2':untrimmed_area,
  'trimmed_footprint_area_m2':footprint.area,'guard_overlap_m':.0018,
  'bevel_width_m':.0007,'bevel_angle_degrees':45,'half_depths_m':half_depths,
  'seat_baseline_m':.0083,'cap_components':len(components(shapes[-1])),
  'core_connected':True,'euler_characteristic':len(vertices)-len(edges)+len(faces),
  'corner_normals':'Planar caps;45degree chamfer normals follow traced footprint; smooth radial wall normals'}
 angles=np.asarray(inclination)
 normal_array=np.asarray(normals)
 assert np.isfinite(normal_array).all()
 assert float(np.max(abs(np.linalg.norm(normal_array,axis=2)-1)))<1e-10
 total=angles[:,1].sum()
 outside=float(angles[(angles[:,0]<35)|(angles[:,0]>55),1].sum()/total)
 report['chamfer_inclination_audit']={'triangle_angle_quantiles_degrees':np.percentile(angles[:,0],[0,1,5,50,95,99,100]).tolist(),
  'area_fraction_outside_35_55_degrees':outside,'area_fraction_above_75_degrees':float(angles[angles[:,0]>75,1].sum()/total),
  'area_fraction_inside_40_50_degrees':float(angles[(angles[:,0]>=40)&(angles[:,0]<=50),1].sum()/total),
  'area_weighted_mean_degrees':float(np.sum(angles[:,0]*angles[:,1])/total),
  'triangulation':'Constrained Delaunay plus six bounded local diagonal-optimization passes'}
 assert outside<.015,'Too much crown chamfer area deviates from45degrees'
 assert float(angles[:,0].max())<75,'Nearly vertical crown chamfer fold'
 return {'vertices':vertices,'faces':faces,'face_regions':regions,'corner_normals':normals,
  'layer_depth':layer_depth,'body_signed_distance_m':body_distance,'body_nearest_boundary_xz':nearest,'report':report}

if __name__=='__main__':
 payload=build();OUTPUT.parent.mkdir(parents=True,exist_ok=True)
 OUTPUT.write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
 print(json.dumps({'output':str(OUTPUT),**payload['report']},indent=2))
