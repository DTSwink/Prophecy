import unreal
from pathlib import Path
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text(encoding='utf-8')
source=source.replace("if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
source=source.replace("'HandChain-'","'SlashSword-'")
source=source.replace("                self.rows.append(",'''                sword=a.get_held_sword()
                weapon=None
                if sword:
                    meshes=sword.get_components_by_class(unreal.StaticMeshComponent)
                    blade=next((m for m in meshes if m.get_name()=='sword'),None)
                    if blade and blade.static_mesh:
                        box=blade.static_mesh.get_bounding_box()
                        grip=a.get_editor_property('sword_grip_transform')
                        weapon={'actual':tr(blade.get_world_transform()),'grip':tr(grip),'scale':[grip.scale3d.x,grip.scale3d.y,grip.scale3d.z],
                            'min':[box.min.x,box.min.y,box.min.z],'max':[box.max.x,box.max.y,box.max.z]}
                self.rows.append(''')
source=source.replace("'bones':bones}","'bones':bones,'weapon':weapon}")
source=source.replace("'weapon':weapon}","'weapon':weapon,'actor_forward':[a.get_actor_forward_vector().x,a.get_actor_forward_vector().y,a.get_actor_forward_vector().z]}")
exec(source,globals())
