import gc,types,builtins
for o in gc.get_objects():
 if isinstance(o,types.FunctionType) and o.__name__=='tick':
  print('CAPTURE_CALLBACK',id(o),id(o.__globals__),o.__globals__.get('mode'),o.__globals__.get('s',{}).get('cb'))
for o in gc.get_objects():
 if isinstance(o,dict) and 'cb' in o and 'enabled' in o and 'rows' in o:
  print('CAPTURE_STATE',id(o),o.get('cb'),len(o.get('rows',[])),o.get('frame'))
