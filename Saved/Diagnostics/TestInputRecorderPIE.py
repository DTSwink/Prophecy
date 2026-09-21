import unreal,pathlib,json,time,traceback,struct
ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not ed.get_game_world()
folder=pathlib.Path(unreal.Paths.project_saved_dir())/'DebugInputRecordings'
folder.mkdir(parents=True,exist_ok=True)
report=pathlib.Path(unreal.Paths.project_saved_dir())/'Diagnostics/InputRecorderPIE.json'
slots=[2147483001,2147483002]
paths=[folder/f'Slot_{n}.input' for n in slots]
assert all(not p.exists() for p in paths),'Reserved fixture slot already exists; preserve it'
keys=["bA","bB","bC","bD","bE","bF","bG","bH","bI","bJ","bK","bL","bM","bN","bO","bP","bQ","bR","bS","bT","bU","bV","bW","bX","bY","bZ","bZero","bOne","bTwo","bThree","bFour","bFive","bSix","bSeven","bEight","bNine","bSpaceBar","bEnter","bTab","bBackSpace","bEscape","bLeftShift","bRightShift","bLeftControl","bRightControl","bLeftAlt","bRightAlt","bUp","bDown","bLeft","bRight","bGamepad_LeftThumbstick","bGamepad_RightThumbstick","bGamepad_Special_Left","bGamepad_Special_Right","bGamepad_Special_Left_Touched","bGamepad_FaceButton_Bottom","bGamepad_FaceButton_Right","bGamepad_FaceButton_Left","bGamepad_FaceButton_Top","bGamepad_LeftShoulder","bGamepad_RightShoulder","bGamepad_LeftTrigger","bGamepad_RightTrigger","bGamepad_DPad_Up","bGamepad_DPad_Down","bGamepad_DPad_Right","bGamepad_DPad_Left","bGamepad_LeftStick_Up","bGamepad_LeftStick_Down","bGamepad_LeftStick_Right","bGamepad_LeftStick_Left","bGamepad_RightStick_Up","bGamepad_RightStick_Down","bGamepad_RightStick_Right","bGamepad_RightStick_Left"]
axes=["Gamepad_LeftX","Gamepad_LeftY","Gamepad_RightX","Gamepad_RightY","Gamepad_LeftTriggerAxis","Gamepad_RightTriggerAxis","Gamepad_Special_Left_X","Gamepad_Special_Left_Y"]
motions=['Tilt','RotationRate','Gravity','Acceleration']
def packed(value):
    bits=[0,0]
    for i,k in enumerate(keys):
        if value.get_editor_property(k):bits[i//64]|=1<<(i%64)
    floats=[value.get_editor_property(k) for k in axes]
    doubles=[]
    for k in motions:
        v=value.get_editor_property(k);doubles.extend([v.x,v.y,v.z])
    return struct.pack('<QQ8f12d',*bits,*floats,*doubles)
expected=[]
for i in range(7):
    expected.append(struct.pack('<QQ8f12d',1<<i,1<<(i+1),*[float((j+i)%9)/16 for j in range(8)],*[float(j-i)/8 for j in range(12)]))
paths[0].write_bytes(struct.pack('<IIi',0x50524931,1,len(expected))+b''.join(expected))
s={'start':time.monotonic(),'phase':'start','rows':[],'play_index':0,'recorded':[],'last_t':-1}
recorder_class=unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyInputRecorderComponent')
def finish(result,error=''):
    unreal.unregister_slate_post_tick_callback(s['cb'])
    if ed.get_game_world():level.editor_request_end_play()
    report.write_text(json.dumps({'result':result,'error':error,'checks':s['rows']},indent=2))
    # Finished recordings are closed before this point. On failure leave fixture
    # files for diagnosis; never delete an active recorder's file.
    if result=='passed':
        for p in paths:
            if p.exists():p.unlink()
    print('INPUT_RECORDER_PIE',result,error)
def tick(_):
    try:
        assert time.monotonic()-s['start']<90,'Timeout'
        w=ed.get_game_world()
        if not w:return
        t=unreal.GameplayStatics.get_time_seconds(w)
        if t==s['last_t']:return
        s['last_t']=t
        if s['phase']=='start':
            if t<.7:return
            a=unreal.GameplayStatics.get_player_pawn(w,0);s['agent']=a
            assert not a.get_components_by_class(recorder_class),'Recorder was initialized without user wiring'
            a.call_method('InitializeInputRecording')
            assert len(a.get_components_by_class(recorder_class))==1
            a.call_method('InitializeInputRecording')
            assert len(a.get_components_by_class(recorder_class))==1,'Initialization must be idempotent'
            a.set_editor_property('RecordingSlot',slots[0]);a.set_editor_property('PlayingInput',True)
            s['rows'].append('No component before initialization; one after repeated initialization')
            s['phase']='seed_play';return
        a=s['agent']
        value=packed(a.get_editor_property('ReplayedInput'))
        if s['phase']=='seed_play':
            assert value==expected[s['play_index']],('Playback frame mismatch',s['play_index'])
            assert a.get_editor_property('PlayingInput'),'Last playback frame must remain visible while Playing Input is true'
            s['play_index']+=1
            if s['play_index']==len(expected):s['phase']='eof'
        elif s['phase']=='eof':
            assert not a.get_editor_property('PlayingInput'),'EOF should return to live input'
            s['rows'].append('Seven full-channel fixture frames replayed exactly; EOF returned to live input')
            a.set_editor_property('RecordingSlot',slots[1]);a.set_editor_property('RecordingInput',True)
            s['phase']='record'
        elif s['phase']=='record':
            s['recorded'].append(value)
            if len(s['recorded'])==6:
                a.set_editor_property('RecordingInput',False);s['phase']='save'
        elif s['phase']=='save':
            raw=paths[1].read_bytes()
            assert raw==struct.pack('<IIi',0x50524931,1,6)+b''.join(s['recorded']),'Recorded file is not the exact six published input frames'
            s['rows'].append('Recording captured exactly one published input structure per tick')
            a.set_editor_property('PlayingInput',True);s['play_index']=0;s['phase']='record_play'
        elif s['phase']=='record_play':
            assert value==s['recorded'][s['play_index']],('Recorded input replay mismatch',s['play_index'])
            s['play_index']+=1
            if s['play_index']==6:s['phase']='final_eof'
        elif s['phase']=='final_eof':
            assert not a.get_editor_property('PlayingInput')
            # Re-record an existing slot; the next recording must replace it.
            a.set_editor_property('RecordingSlot',slots[0]);a.set_editor_property('RecordingInput',True)
            s['replacement']=[];s['phase']='overwrite'
        elif s['phase']=='overwrite':
            s['replacement'].append(value)
            if len(s['replacement'])==2:
                a.set_editor_property('RecordingInput',False);s['phase']='overwritten'
        elif s['phase']=='overwritten':
            assert paths[0].read_bytes()==struct.pack('<IIi',0x50524931,1,2)+b''.join(s['replacement'])
            s['rows'].append('Recorded playback exact and new recording replaced the existing slot')
            finish('passed')
    except Exception:finish('failed',traceback.format_exc())
s['cb']=unreal.register_slate_post_tick_callback(tick)
level.editor_request_begin_play()

