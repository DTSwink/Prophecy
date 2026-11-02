"""Match the user's working animation-only Unreal-to-Cascadeur export format."""
import json, traceback, hashlib
from pathlib import Path
import unreal as u

root=Path(u.Paths.project_dir()).resolve()
audit=root/'Saved/Diagnostics/MixamoThrows20261024'
out=Path('C:/Users/singerie/Documents/UEFN_Throws_Cascadeur_20261024')
report={'exports':[],'export_preview_mesh':False}
try:
    for name in ['Throwing','Throw_Object']:
        anim=u.load_asset('/Game/_mygame/animations/MixamoThrows20261024/UEFN_'+name)
        assert isinstance(anim,u.AnimSequence)
        options=u.FbxExportOption()
        options.ascii=False
        options.collision=False
        options.level_of_detail=False
        options.export_morph_targets=False
        options.export_preview_mesh=False
        options.map_skeletal_motion_to_root=False
        options.export_local_time=True
        options.force_front_x_axis=False
        task=u.AssetExportTask()
        task.object=anim
        task.filename=str(out/('UEFN_'+name+'_AnimationOnly.fbx'))
        task.automated=True
        task.prompt=False
        task.replace_identical=False
        task.options=options
        assert u.Exporter.run_asset_export_task(task),list(task.errors)
        path=Path(task.filename)
        report['exports'].append({'file':str(path),'asset':anim.get_path_name(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    report['success']=True
except Exception:
    report['error']=traceback.format_exc()
    u.log_error(report['error'])
finally:
    (audit/'animation-only-export.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    u.SystemLibrary.quit_editor()
