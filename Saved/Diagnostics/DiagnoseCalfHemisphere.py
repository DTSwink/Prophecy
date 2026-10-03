exec(open('Saved/Diagnostics/MeasureCalfRoll.py').read().split('stats={};last={};events=[]')[0])
native=json.loads(Path('Content/locomotion/NN/prophecy_slash_native.json').read_text())['lower_geometry']
def legacy(row,side):
    i=0 if side=='l' else 1;b=row['bones'];t=b['thigh_'+side][0];c=b['calf_'+side][0];f=b['foot_'+side][0]
    la=unit(np.array(native['local_offsets'][names.index('foot_'+side)])*mirror);poles=np.array(native['ik_local_pole_axis'][i])*mirror
    tr=R.from_quat(t[3:]);wa=unit(np.array(f[:3])-c[:3]);wp=tr.apply(poles[0])
    def basis(main,pole):
        side=unit(pole-main*np.dot(pole,main));up=unit(np.cross(main,side));return np.stack([main,unit(np.cross(up,main)),up],axis=1)
    q=R.from_matrix(basis(wa,wp)@basis(la,poles[1]).T);cz=q.apply([0,0,1]);tz=tr.apply([0,0,1]);gate=cz@tz
    turn=0.
    if gate<0:
        u=unit(cz-wa*np.dot(cz,wa));v=unit(tz-wa*np.dot(tz,wa));turn=np.arctan2(np.dot(np.cross(u,v),wa),u@v)
        q=R.from_rotvec(wa*turn)*q
    return {'hemisphere_dot':float(gate),'hemisphere_correction_deg':float(np.rad2deg(turn)),'legacy_match_error_deg':float(np.rad2deg((q.inv()*R.from_quat(c[3:])).magnitude())), 'pole_projection_length':float(np.linalg.norm(wp-wa*np.dot(wp,wa)))}
out=[]
for row in d['rows']:
    if row['agent']=='BP_ProphecyManualPoseAgent_C_1' and row['frame'] in [111,113,115,117,561,563,565,567]:
        out.append({'frame':row['frame'],'attack':row['attack'],'hemisphere_dot_roll_correction_error':legacy(row,'l')})
print(json.dumps(out,indent=2));Path(sys.argv[1]).with_suffix('.hemisphere.json').write_text(json.dumps(out,indent=2))
