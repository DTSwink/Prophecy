import builtins
c=getattr(builtins,'_sharedcalfcapture',{})
print('SHARED_CAPTURE',c.get('frame'),len(c.get('rows',[])),c.get('rows',[])[-1]['clock'] if c.get('rows') else None)
