import builtins, unreal
s=getattr(builtins,'_wrist_snap_capture',None)
print('WRIST_CAPTURE_STATE',None if not s else dict(rows=len(s['rows']),start=s['start'],last=s['last'],latest=s['rows'][-1]['limits'] if s['rows'] else None))
