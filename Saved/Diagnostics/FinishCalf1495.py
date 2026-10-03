import builtins
s = getattr(builtins, '_calf1495', None)
if s is not None:
    s.get('rows', []).clear()
    del builtins._calf1495
print('CALF1495_CAPTURE_MEMORY_RELEASED')
