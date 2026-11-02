"""Render the accepted head with cavity shading enabled/bypassed at fixed seed."""
import bpy,json,numpy as np
from pathlib import Path
R=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');W=R/'Saved/Diagnostics/ImperialSpear/PommelLotus/RefinementV4'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s
mat=bpy.data.materials['M_ImperialSpear_PBR'];ns=mat.node_tree.nodes;ls=mat.node_tree.links
pr=next(n for n in ns if n.type=='BSDF_PRINCIPLED');socket=pr.inputs['Base Color']
current=socket.links[0].from_socket;original=ns['PommelCavity_BaseOriginal'].outputs[0]
state=(s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage,s.render.filepath,s.cycles.samples,s.cycles.use_denoising,s.cycles.seed)
pixels=[]
try:
    s.render.resolution_x=320;s.render.resolution_y=240;s.render.resolution_percentage=100
    s.cycles.samples=16;s.cycles.use_denoising=False;s.cycles.seed=42
    s.render.threads_mode='FIXED';s.render.threads=3;s.cycles.device='CPU'
    for name,source in [('enabled',current),('bypassed',original)]:
        ls.new(source,socket);file=W/('ProtectedHead_'+name+'.png');s.render.filepath=str(file)
        bpy.ops.render.render(write_still=True)
        image=bpy.data.images.load(str(file),check_existing=False)
        pixels.append(np.array(image.pixels[:],dtype=np.float32));bpy.data.images.remove(image)
    delta=np.abs(pixels[0]-pixels[1]);assert delta.size==320*240*4
    report={'status':'PASS' if float(delta.max())<.001 and float(delta.mean())<1e-5 else 'FAIL',
            'maximum_channel_difference':float(delta.max()),'mean_channel_difference':float(delta.mean()),
            'pixels':320*240,'fixed_seed':42,'samples':16,'scope':'Accepted head camera; shared cavity node enabled versus bypassed'}
    (W/'Protected_Surface_Render_Check.json').write_text(json.dumps(report,indent=2))
    assert report['status']=='PASS',report
    print(json.dumps(report))
finally:
    ls.new(current,socket)
    s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage,s.render.filepath,s.cycles.samples,s.cycles.use_denoising,s.cycles.seed=state
