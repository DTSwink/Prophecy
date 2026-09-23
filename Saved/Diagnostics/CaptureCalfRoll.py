import unreal
from pathlib import Path
source=(Path(unreal.Paths.project_dir())/'Saved/Diagnostics/CaptureHandChain.py').read_text()
source=source.replace("if str(n) in ('upperarm_l','lowerarm_l','hand_l','upperarm_r','lowerarm_r','hand_r')",'')
source=source.replace("'HandChain-'","'CalfRoll-'").replace('self.frame>=360','self.frame>=600')
source=source.replace("                self.rows.append(",'''                physical=next((m for m in a.get_components_by_class(unreal.SkeletalMeshComponent) if m.get_name()=='PhysicalMesh'),None)
                actual={str(n):tr(physical.get_socket_transform(str(n),unreal.RelativeTransformSpace.RTS_WORLD)) for n in names} if physical else {}
                self.rows.append(''')
source=source.replace("'bones':bones}","'bones':bones,'physical':actual}")
exec(source,globals())
