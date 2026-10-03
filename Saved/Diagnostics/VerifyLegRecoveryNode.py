import unreal
lib=unreal.get_default_object(unreal.load_class(None,'/Script/GameAnimationSample3.ProphecyLegChainDebugLibrary'))
print('NODE_REFLECTED_INVALID_AGENT_REJECTED',lib.call_method('SetLegReconstructionRecovery',(None,1.,180.)))
