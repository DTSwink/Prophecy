import builtins, json
s=builtins._foot_clamp_probe
print(json.dumps({'last':s['last'],'events':s['events'][-3:],'rows':s['rows'][-2:]},indent=2))
