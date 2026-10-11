IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterStagger,"Prophecy.SwordHolster.Stagger",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterStagger::RunTest(const FString&)
{
 using namespace ProphecySwordHolsterSchedule;
 const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordStagger20261011");IFileManager::Get().MakeDirectory(*Dir,true);
 // Exercise real reservations/delegates in independent worlds, without meshes,
 // inference or physical bodies. These actors never start gameplay.
 UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);UWorld* Other=UWorld::CreateWorld(EWorldType::Editor,false);
 TArray<AProphecyAgent*> Agents;for(int I=0;I<100;++I)Agents.Add(W->SpawnActor<AProphecyAgent>());
 auto* Separate=Other->SpawnActor<AProphecyAgent>();Reserve(Separate);
 for(auto* A:Agents)Reserve(A);
 TestEqual(TEXT("One reservation per agent"),Reservations.Num(),101);
 for(auto* A:Agents)Reserve(A);
 TestEqual(TEXT("Repeated requests do not accumulate"),Reservations.Num(),101);
 for(int Phase=0;Phase<4;++Phase){int Due=0;for(auto* A:Agents)Due+=Ready(A);TestEqual(TEXT("25 starts per slot"),Due,25*(Phase+1));if(Phase<3)AdvanceClock(W,LEVELTICK_All,1.f/60);}
 TestEqual(TEXT("World clocks isolated"),Tick(Separate),uint64(0));
 const uint64 Before=Tick(Agents[0]);AdvanceClock(W,LEVELTICK_PauseTick,1.f/60);AdvanceClock(W,LEVELTICK_All,0);
 TestEqual(TEXT("No paused or zero-delta advancement"),Tick(Agents[0]),Before);
 for(int I=0;I<100;I+=2){LeaveReach(Agents[I]);LeaveReach(Agents[I]);}
 int Load=0;for(int N:Worlds.FindChecked(W).Slots.Load)Load+=N;TestEqual(TEXT("Leaving reach releases load once"),Load,50);
 for(auto* A:Agents){ProphecySwordHolsterSchedule::Remove(A);ProphecySwordHolsterSchedule::Remove(A);}ProphecySwordHolsterSchedule::Remove(Separate);
 TestTrue(TEXT("No idle scheduling work"),Worlds.IsEmpty()&&Reservations.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
 // Unsynchronized requests, early cancellation and re-entry. Allocation uses
 // current reach load, not total spawns or action-local tick modulo.
 FRandomStream Random(74203);
 for(int Step=0;Step<300;++Step){AdvanceClock(W,LEVELTICK_All,1.f/60);auto* A=Agents[Random.RandRange(0,99)];ProphecySwordHolsterSchedule::Remove(A);Reserve(A);
  const auto R=Reservations.FindChecked(A);TestTrue(TEXT("Bounded request delay"),R.Due>=Tick(A)&&R.Due-Tick(A)<=3);
  const auto& Counts=Worlds.FindChecked(W).Slots;for(int I=0;I<4;++I)TestTrue(TEXT("Least-loaded slot chosen"),Counts.Load[R.Slot]<=Counts.Load[I]+1);
 }
 W->DestroyWorld(false);Other->DestroyWorld(false);
 TestTrue(TEXT("World cleanup retires reservations and delegates"),Worlds.IsEmpty()&&Reservations.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
 // A depleted reach slot must not absorb an entire new burst of planning.
 FSlots Uneven;Uneven.Load[1]=Uneven.Load[2]=Uneven.Load[3]=100;int StartCounts[4]={};
 for(int I=0;I<100;++I){Uneven.Acquire(40);++StartCounts[Uneven.BookStart(40)-40];}
 for(int N:StartCounts)TestEqual(TEXT("Start load independent of reach imbalance"),N,25);
 TestEqual(TEXT("Expired bookings disappear even after skipped ticks"),Uneven.BookStart(100),uint64(100));

 FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabPort20261010/parity.json"))))return false;
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
 const auto& Rows=Root->GetArrayField(TEXT("rows"));
 double MaxPose=0,MaxPosition=0,OffsetPose=0,OffsetPosition=0;int TimingMismatch=0,Completed=0,OffsetTicks=0;
 for(const auto& RV:Rows){const FActive Seed=OptimizationFixture(Root,RV->AsObject());
  // Each start phase matches the old local cadence; motion and event timing
  // remain identical relative to that actual start, including live targets.
  for(int SlotIndex=0;SlotIndex<4;++SlotIndex)for(int Moving=0;Moving<2;++Moving){FActive Old=Seed,New=Seed;OptimizationPlan(Old,false);New=Old;New.RefreshSlot=SlotIndex;New.NextRefresh=SlotIndex+4;
   for(int T=1;T<260&&!Old.Status.Finished;++T){if(Moving){OptimizationMovingBase(Old,Seed.Base,T/60.);New.Base=Old.Base;Old.Clear=New.Clear=FTransform(Seed.Clear.GetRotation(),Seed.Clear.GetLocation()+FVector(2*FMath::Sin(T*.09),0,0));}
    if(Old.Status.ReachDone&&!Old.Sliding){Old.Sliding=New.Sliding=true;Old.SlideStart=New.SlideStart=Old.Status.Tick;}
    Advance(Old,1);Advance(New,1,T+SlotIndex);
    TimingMismatch+=(Old.Status.ReachDone!=New.Status.ReachDone)||(Old.Status.Returning!=New.Status.Returning)||(Old.Status.Finished!=New.Status.Finished);
    for(int J:Old.Upper){MaxPose=FMath::Max(MaxPose,Angle(Old.Pose[J].GetRotation(),New.Pose[J].GetRotation()));MaxPosition=FMath::Max(MaxPosition,FVector::Distance(Old.Pose[J].GetLocation(),New.Pose[J].GetLocation()));}
   }
   TestTrue(TEXT("Scheduled motion completes"),New.Status.Finished);++Completed;
  }
  // A consumer that skips frames gets only one fresh search, then returns to
  // its slot. Duplicate reads do nothing. Head and return still use all ticks.
  FActive Missed=Seed;OptimizationPlan(Missed,false);Missed.RefreshSlot=2;Missed.NextRefresh=6;
  Advance(Missed,9,11);TestEqual(TEXT("Catch-up preserves elapsed ticks"),Missed.Status.Tick,9);TestEqual(TEXT("Missed slot reanchors"),Missed.NextRefresh,uint64(14));
  const FVector Body=Missed.Body;const FQuat Head=Missed.Head;Advance(Missed,0,11);
  TestTrue(TEXT("Duplicate update leaves motion untouched"),Missed.Body==Body&&Missed.Head==Head&&Missed.Status.Tick==9);
  Advance(Missed,3,14);TestEqual(TEXT("Subsequent slot"),Missed.NextRefresh,uint64(18));
  // Start bookings and reach slots are deliberately independent. Exercise
  // every offset with continuously moving targets and each action's own gates.
  for(int StartPhase=0;StartPhase<4;++StartPhase)for(int SlotIndex=0;SlotIndex<4;++SlotIndex){
   FActive Old=Seed;OptimizationPlan(Old,false);FActive New=Old;New.RefreshSlot=SlotIndex;New.NextRefresh=NextSlot(StartPhase+1,SlotIndex);
   for(int T=1;T<260&&(!Old.Status.Finished||!New.Status.Finished);++T){
    for(auto* C:{&Old,&New})if(!C->Status.Finished){OptimizationMovingBase(*C,Seed.Base,T/60.);C->Clear=FTransform(Seed.Clear.GetRotation(),Seed.Clear.GetLocation()+FVector(2*FMath::Sin(T*.09),0,0));
     if(C->Status.ReachDone&&!C->Sliding){C->Sliding=true;C->SlideStart=C->Status.Tick;}
     Advance(*C,1,T+StartPhase);TestTrue(TEXT("Head velocity retained across slot offsets"),C->Status.HeadStep<=(C->HeadOut?C->Profile.HeadOutSpeed:C->Profile.HeadInSpeed)/60+.0001);
    }
    if(!Old.Status.Returning&&!New.Status.Returning)for(int J:Old.Upper){OffsetPose=FMath::Max(OffsetPose,Angle(Old.Pose[J].GetRotation(),New.Pose[J].GetRotation()));OffsetPosition=FMath::Max(OffsetPosition,FVector::Distance(Old.Pose[J].GetLocation(),New.Pose[J].GetLocation()));}
   }
   TestTrue(TEXT("Off-phase action completes"),Old.Status.Finished&&New.Status.Finished);OffsetTicks=FMath::Max(OffsetTicks,FMath::Abs(Old.Status.Tick-New.Status.Tick));
  }
 }
 TestEqual(TEXT("Event timing from actual start"),TimingMismatch,0);TestTrue(TEXT("Pose unchanged on regular updates"),MaxPose<.0001&&MaxPosition<1.e-8);
 TestTrue(TEXT("Off-phase live-input difference stays within grip tolerance"),OffsetPosition<2);TestTrue(TEXT("Off-phase arrival remains within one refresh interval"),OffsetTicks<=4);

 // Seven same-process alternating pairs after warmup. Include planning in the
 // frame that actually admits it, unlike the earlier cycle-only benchmark.
 FString Bench=TEXT("scenario,repeat,stagger,frames,total_ms,peak_ms,start_peak_ms,cycle_peak_ms,max_starts,max_refits\n");
 for(int Scenario=0;Scenario<6;++Scenario)for(int Repeat=-1;Repeat<7;++Repeat)for(int Pass=0;Pass<2;++Pass){const bool Stagger=((Pass+(Repeat&1))%2)!=0;
  TArray<FActive> Crowd;TArray<int> Request,Due,LastRead;FSlots Slots;
  for(int I=0;I<100;++I){const int Row=Scenario<4?Scenario:I%Rows.Num();Crowd.Add(OptimizationFixture(Root,Rows[Row]->AsObject()));Request.Add(Scenario==5?(I*7)%19:0);Due.Add(-1);LastRead.Add(-1);}
  double Total=0,Peak=0,StartPeak=0,CyclePeak=0;int Frames=0,MaxStarts=0,MaxRefits=0;
  for(int Frame=0;Frame<320;++Frame){bool Running=false;int Starts=0,Refits=0;const double Start=FPlatformTime::Seconds();
   for(int I=0;I<100;++I){auto& C=Crowd[I];if(C.Status.Finished)continue;Running=true;
    if(Frame<Request[I])continue;
    if(Due[I]<0){if(Stagger){C.RefreshSlot=Slots.Acquire(Frame);Due[I]=int(Slots.BookStart(Frame));}else Due[I]=Frame;}
    if(Frame<Due[I])continue;
    if(LastRead[I]<0){OptimizationPlan(C,false);C.NextRefresh=NextSlot(Frame+1,C.RefreshSlot);LastRead[I]=Frame;++Starts;continue;}
    if(C.Status.ReachDone&&!C.Sliding){C.Sliding=true;C.SlideStart=C.Status.Tick;if(Stagger)Slots.Release(C.RefreshSlot);}
    Refits+=!C.Sliding&&(Stagger?uint64(Frame)>=C.NextRefresh:(C.Status.Tick+1)%4==0);
    Advance(C,Frame-LastRead[I],Frame);LastRead[I]=Frame;
   }
   const double Ms=(FPlatformTime::Seconds()-Start)*1000;if(!Running)break;
   ++Frames;Total+=Ms;Peak=FMath::Max(Peak,Ms);if(Starts)StartPeak=FMath::Max(StartPeak,Ms);else CyclePeak=FMath::Max(CyclePeak,Ms);MaxStarts=FMath::Max(MaxStarts,Starts);MaxRefits=FMath::Max(MaxRefits,Refits);
  }
  for(const auto& C:Crowd)TestTrue(TEXT("Entire timed crowd completes"),C.Status.Finished);
  if(Stagger&&Scenario<5){TestEqual(TEXT("Synchronized start peak count"),MaxStarts,25);TestTrue(TEXT("Synchronized refit peak count"),MaxRefits<=25);}
  if(Repeat>=0)Bench+=FString::Printf(TEXT("%d,%d,%d,%d,%.9f,%.9f,%.9f,%.9f,%d,%d\n"),Scenario,Repeat,Stagger,Frames,Total,Peak,StartPeak,CyclePeak,MaxStarts,MaxRefits);
 }
 const FString Result=FString::Printf(TEXT("cycles=%d pose_deg=%.12g position_cm=%.12g timing_mismatch=%d offset_pose_deg=%.12g offset_position_cm=%.12g offset_completion_ticks=%d\n"),Completed,MaxPose,MaxPosition,TimingMismatch,OffsetPose,OffsetPosition,OffsetTicks);
 AddInfo(Result);FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("parity.txt")));FFileHelper::SaveStringToFile(Bench,*(Dir/TEXT("benchmark.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
 return !HasAnyErrors();
}
