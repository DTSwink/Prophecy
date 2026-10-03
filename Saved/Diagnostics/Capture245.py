import pathlib,unreal
p=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/Head24520261003'
p.mkdir(exist_ok=True)
src=(p.parent/'CaptureNNEntry.py').read_text(encoding='utf-8-sig')
src=src.replace("exec(compile(source,'CaptureNNEntry.py','exec'))", "source=source.replace('Diagnostics/NNEntry20261003','Diagnostics/Head24520261003').replace(\"s['frames']>=550\",\"s['frames']>=300\")\nexec(compile(source,'Capture245.py','exec'))")
old=unreal.SystemLibrary.get_console_variable_int_value('Prophecy.FKReturn.Audit')
unreal.SystemLibrary.execute_console_command(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(),'Prophecy.FKReturn.Audit 1')
src=src.replace("exec(compile(source,'Capture245.py','exec'))", "source=source.replace(\" print('HEAD_ENTRY_DONE'\",\" unreal.SystemLibrary.execute_console_command(ed.get_editor_world(),'Prophecy.FKReturn.Audit "+str(old)+"')\\n print('HEAD_ENTRY_DONE'\")\nexec(compile(source,'Capture245.py','exec'))")
exec(compile(src,'Capture245-wrapper.py','exec'))
