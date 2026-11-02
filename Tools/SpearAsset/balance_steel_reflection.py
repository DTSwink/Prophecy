"""Presentation-only steel reflection card; excludes other material receivers."""
import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(r'C:/Users/singerie/Documents/Unreal Projects/Prophecy'); OUT=ROOT/'Exports/ImperialSpear'
s=bpy.data.scenes['Scene'];bpy.context.window.scene=s;art=bpy.data.collections['SPEAR • editable components'];blade=next(o for o in art.objects if o.name.startswith('06 •'))
name='Steel • broad reflection strip';ob=bpy.data.objects.get(name)
if ob is None:
 data=bpy.data.lights.new(name,'AREA');ob=bpy.data.objects.new(name,data);bpy.data.collections['STUDIO • presentation only'].objects.link(ob)
assert hasattr(ob,'light_linking')
receivers=bpy.data.collections.get('STUDIO • steel reflection receivers') or bpy.data.collections.new('STUDIO • steel reflection receivers')
if blade.name not in receivers.objects:receivers.objects.link(blade)
ob.light_linking.receiver_collection=receivers
ob.data.shape='RECTANGLE';ob.data.energy=135;ob.data.size=.9;ob.data.size_y=.5;ob.data.color=(1,1,1)
ob.location=(1.3,-1.2,2.3);ob.rotation_euler=(Vector((0,0,1.9))-ob.location).to_track_quat('-Z','Y').to_euler()
s['Steel_reflection_light']='Presentation only:135W rectangle.9x.5m, receiving blade only, no asset material edits.'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Saved/Diagnostics/ImperialSpear/ImperialSpear_ReferenceWork.blend'))
s.render.filepath=str(OUT/'Comparison_Current.png');bpy.ops.render.render(write_still=True)
print(s['Steel_reflection_light'])
