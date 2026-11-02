import bpy,json,os
from pathlib import Path
OUT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Exports/ImperialSpear')
art=bpy.data.collections['SPEAR • editable components']; blade=next(o for o in art.objects if o.name.startswith('06 •')); mat=blade.data.materials[0]
report={'blend':bpy.data.filepath,'scene':bpy.context.scene.name,'material':mat.name,'nodes':[],'objects':[]}
for n in mat.node_tree.nodes:
 d={'name':n.name,'type':n.type}
 if n.type=='TEX_IMAGE':
  im=n.image;d.update(image=im.name,filepath=im.filepath,packed=bool(im.packed_file),colorspace=im.colorspace_settings.name,alpha_mode=im.alpha_mode,size=list(im.size),interpolation=n.interpolation)
 if n.type=='BSDF_PRINCIPLED':d['inputs']={s.name:str(s.default_value) for s in n.inputs if s.name in ['Metallic','Roughness','Specular IOR Level','Coat Weight','Alpha']}
 report['nodes'].append(d)
report['links']=[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in mat.node_tree.links]
for ob in art.objects:
 if not ob.name.startswith(('05 •','01 •','07 •','Socket • continuous','Tassel • rough','Tassel • pierced small')):continue
 uv=ob.data.uv_layers[0]; data=[]
 for p in ob.data.polygons:
  if p.normal.y<-.4 and len(data)<8:
   co=p.center; u=sum(uv.data[li].uv.x for li in p.loop_indices)/len(p.loop_indices);v=sum(uv.data[li].uv.y for li in p.loop_indices)/len(p.loop_indices)
   samples={}
   for key in ['base','orm','normal']:
    im=mat.node_tree.nodes['Atlas_'+key].image; xx=min(im.size[0]-1,max(0,int(u*im.size[0])));yy=min(im.size[1]-1,max(0,int(v*im.size[1]))); offset=(yy*im.size[0]+xx)*4
    samples[key]=[round(c,4) for c in im.pixels[offset:offset+4]]
   data.append({'face':p.index,'co':list(co),'uv':[u,v],'samples':samples})
  if len(data)==8:break
 report['objects'].append({'name':ob.name,'material':ob.data.materials[0].name,'uv_name':uv.name,'uv_min':[min(x.uv[i] for x in uv.data) for i in [0,1]],'uv_max':[max(x.uv[i] for x in uv.data) for i in [0,1]],'sample':data})
(OUT/'Material_Probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report))
