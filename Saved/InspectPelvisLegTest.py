import builtins,json,unreal
s=getattr(builtins,'_pelvis_leg_chain_test',{})
print(json.dumps({k:v for k,v in s.items() if k not in ('cb','actor','baseline')},default=str))
