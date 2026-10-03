import json, pathlib, math
p=pathlib.Path(__file__).parent
r=json.loads((p/'emitters.json').read_text(encoding='utf-8-sig'))
assert r['success'],r['error']
assert len(r['trials'])==81
rows={(t['asset'],t['round'],t['mode']):t for t in r['trials']}
def exports(t):return sum(s['exports'] for s in t['sites'])
for (asset,repeat,mode),t in rows.items():
    assert all(math.isfinite(t[k]) for k in ['tick_ms','query_ms','max_export_position_error_cm','max_export_velocity_error','max_export_size_error'])
    stock=rows[asset,repeat,0]
    assert exports(stock)>0
    if mode in [1,8]:
        assert t['export_count_matches_stock'] and t['particle_ticks']==stock['particle_ticks']
        assert t['max_export_position_error_cm']==t['max_export_velocity_error']==t['max_export_size_error']==0
    if mode==4:
        assert t['mismatches']==0
        assert t['max_hit_position_error_cm']<0.0001 and t['max_hit_normal_error']<0.0001
    if mode==2 and asset=='NS_bloodwound':
        assert t['export_count_matches_stock'] and t['max_export_position_error_cm']<0.001
    if mode==5:
        native=rows[asset,repeat,2]
        for k in ['particle_ticks','native_hits','max_export_position_error_cm','max_export_velocity_error','max_export_size_error']:
            assert t[k]==native[k],(asset,k,t[k],native[k])
        assert exports(t)==exports(native)
    if mode==7 and asset=='NS_bloodwound':assert exports(t)==0
result=dict(passed=True,trials=len(rows),exact_hybrid_export_parity=True,native_no_ue_query_geometry_parity=True,native_wound_position_tolerance_cm=0.001,pure_native_arc_rejected_max_displacement_cm=max(t['max_export_position_error_cm'] for t in r['trials'] if t['asset']=='NS_bloodarc' and t['mode']==2))
(p/'validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
