from pathlib import Path
p=Path('Source/ProphecyEditor/Private/ProphecySpecialRecoverySetup.cpp');s=p.read_text(encoding='utf-8')
a=s.index('    auto* Choice=Cast<UK2Node_IfThenElse>',s.index('void SplitRegions'))
b=s.index('    Event->NodeComment=',a)
s=s[:a]+'''    auto* HandEnd=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_204")));
    auto* TimerBranch=Cast<UK2Node_IfThenElse>(Find(TEXT("K2Node_IfThenElse_20")));
    if(!Arm || !Lower || !EndLower || !Hand || !HandEnd || !TimerBranch
        || Arm->FunctionReference.GetMemberName()!=TEXT("SetSlashRightArmReturnToNeutral")
        || Lower->FunctionReference.GetMemberName()!=TEXT("SetLocomotionLowerBodyTempering")
        || EndLower->FunctionReference.GetMemberName()!=TEXT("SetAttackToLocomotionBlend")
        || Hand->FunctionReference.GetMemberName()!=TEXT("SetLocomotionHandTempering"))
    { UE_LOG(LogTemp,Error,TEXT("Regional recovery: functions differ from the current audited graph; no edits"));return; }
    auto* ArmIn=Arm->FindPinChecked(TEXT("execute"));auto* ArmOut=Arm->FindPinChecked(TEXT("then"));
    auto* HandIn=Hand->FindPinChecked(TEXT("execute"));auto* HandOut=HandEnd->FindPinChecked(TEXT("then"));
    auto* TimerIn=TimerBranch->GetExecPin();
    // The user has already separated the current lower and hand/arm chains.
    // Preserve that newer layout rather than restoring the earlier mixed chain.
    if(HandIn->LinkedTo.Num()!=0 || ArmIn->LinkedTo.Num()!=1 || ArmIn->LinkedTo[0]!=HandOut
        || HandOut->LinkedTo.Num()!=1 || ArmOut->LinkedTo.Num()!=0
        || EndLower->FindPinChecked(TEXT("then"))->LinkedTo.Num()!=0 || TimerIn->LinkedTo.Num()!=1)
    { UE_LOG(LogTemp,Error,TEXT("Regional recovery: prepared chain links changed; no edits"));return; }
    TSet<UObject*> Nodes;for(UEdGraphNode* N:Graph->Nodes) Nodes.Add(N);
    FString Backup;FEdGraphUtilities::ExportNodesToText(Nodes,Backup);
    FFileHelper::SaveStringToFile(Backup,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/BeforeRegionalRecovery-")+FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"))+TEXT(".txt")));
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","SplitRegionalRecovery","Split upper and lower special recovery"));
    BP->Modify();Graph->Modify();for(UEdGraphNode* N:Graph->Nodes) N->Modify();
    Event->EventReference.SetExternalMember(TEXT("OnNNLowerSpecialEnded"),Interface);Event->ReconstructNode();
    FGraphNodeCreator<UK2Node_Event> EC(*Graph);auto* Upper=EC.CreateNode();
    Upper->EventReference.SetExternalMember(TEXT("OnNNUpperSpecialEnded"),Interface);Upper->bOverrideFunction=true;
    Upper->NodePosX=Event->NodePosX;Upper->NodePosY=Event->NodePosY-450;EC.Finalize();
    FGraphNodeCreator<UK2Node_IfThenElse> GC(*Graph);auto* Gate=GC.CreateNode();
    Gate->NodePosX=Upper->NodePosX+300;Gate->NodePosY=Upper->NodePosY;GC.Finalize();
    Upper->FindPinChecked(TEXT("then"))->MakeLinkTo(Gate->GetExecPin());
    Upper->FindPinChecked(TEXT("ReturningToLocomotion"))->MakeLinkTo(Gate->GetConditionPin());
    Gate->GetThenPin()->MakeLinkTo(HandIn);
    // Cleanup of the ongoing attack timer belongs to upper completion.
    TimerIn->BreakAllPinLinks();ArmOut->MakeLinkTo(TimerIn);
'''+s[b:]
p.write_text(s,encoding='utf-8',newline='\n')
