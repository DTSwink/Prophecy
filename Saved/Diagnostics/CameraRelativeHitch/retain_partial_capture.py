import builtins,json,pathlib
state=getattr(builtins,'_prophecy_camera_relative_hitch',None)
if state and state.get('rows') and not pathlib.Path(state['path']).exists():
    pathlib.Path(state['path']).write_text(json.dumps({k:v for k,v in state.items() if k not in ('handle','finish')},separators=(',',':')))
    print('Retained incomplete capture',state['path'])
