import bpy,json
from pathlib import Path
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy');WORK=ROOT/'Saved/Diagnostics/ImperialSpear/HandleFinish'
expected=json.loads((WORK/'Live_Pixel_Expected.json').read_text());nodes=bpy.data.materials['M_ImperialSpear_PBR'].node_tree.nodes;report={}
for suffix,node_name in (('NormalGL','Atlas_normal'),('ORM','Atlas_orm')):
    im=nodes[node_name].image;errors=[];examples=[]
    for row in expected[suffix]:
        x,y=row['xy'];offset=((im.size[1]-1-y)*im.size[0]+x)*im.channels
        actual=list(im.pixels[offset:offset+im.channels]);target=[v/255 for v in row['value']]
        errors.extend(abs(a-b) for a,b in zip(actual,target))
        if len(examples)<3:examples.append({'expected':target,'actual':actual})
    report[suffix]={'filepath':im.filepath,'packed':bool(im.packed_file),'channels':im.channels,'max_pixel_error':max(errors),'examples':examples}
print(json.dumps(report));(WORK/'Live_Material_Pixel_Check.json').write_text(json.dumps(report,indent=2))
