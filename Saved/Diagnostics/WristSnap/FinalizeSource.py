from pathlib import Path
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltWorldSubsystem.cpp')
s=p.read_text()
s=s.replace('#include "HAL/IConsoleManager.h"\n','')
start=s.index('static TAutoConsoleVariable<int32> CWristWarmStart')
end=s.index('THIRD_PARTY_INCLUDES_START',start)
s=s[:start]+s[end:]
start=s.index('        auto DiagnosticSettings=') if '        auto DiagnosticSettings=' in s else s.index('        auto DiagnosticSettings =')
end=s.index('\n',s.index('Physics.SetPhysicsSettings(DiagnosticSettings);',start))+1
s=s[:start]+s[end:]
start=s.index('            if (CWristProject.GetValueOnGameThread() != 0)')
end=s.index('\n        }\n        // PublishRigVelocityTargets',start)
s=s[:start]+s[end:]
s=s.replace('        if (CWristSpeculative.GetValueOnGameThread())\n            Constraint = new ProphecyJolt::FSpeculativeJoint', '        Constraint = new ProphecyJolt::FSpeculativeJoint')
s=s.replace('struct FChange { JPH::SixDOFConstraint* Constraint;', 'struct FChange { ProphecyJolt::FSpeculativeJoint* Constraint;')
s=s.replace('Changes.Add({ Constraint, Minimum, Maximum });', 'Changes.Add({ static_cast<ProphecyJolt::FSpeculativeJoint*>(Base), Minimum, Maximum });')
start=s.index('    if (CWristTrace.GetValueOnGameThread() && !Changes.IsEmpty())')
end=s.index('    for (const auto& Change : Changes)',start)
s=s[:start]+s[end:]
start=s.index('    auto TraceWrist =')
end=s.index('    TraceWrist(0);',start)+len('    TraceWrist(0);\n')
s=s[:start]+s[end:]
s=s.replace('    TraceWrist(1);\n','')
p.write_text(s)
log=Path('Saved/Logs/GameAnimationSample3.log').read_text(errors='replace')
Path('Saved/Diagnostics/WristSnap/NativeTrace.log').write_text('\n'.join(x for x in log.splitlines() if 'WristNative' in x or 'WristLimitChange' in x))
