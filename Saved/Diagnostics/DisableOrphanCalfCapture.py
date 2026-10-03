import gc,types
def inert_calf_capture(dt):
 pass
count=0
for callback in gc.get_objects():
 if isinstance(callback,types.FunctionType) and callback.__name__=='tick' and 'SHARED_CALF_STARTED' in str(callback.__globals__.get('finish').__code__.co_consts if isinstance(callback.__globals__.get('finish'),types.FunctionType) else ''):
  pass
 # Identify only this capture by its callback constants and shared state keys.
 if isinstance(callback,types.FunctionType) and callback.__name__=='tick' and 'Prophecy.Debug.SharedCalfRecovery 1' in callback.__code__.co_consts and 'clock' in callback.__code__.co_varnames:
  callback.__code__=inert_calf_capture.__code__;count+=1
print('DISABLED_ORPHAN_CALF_CALLBACKS',count)
