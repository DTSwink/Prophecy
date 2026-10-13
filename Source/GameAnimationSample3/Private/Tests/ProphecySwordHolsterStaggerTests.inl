IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterStagger,"Prophecy.SwordHolster.Stagger",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterStagger::RunTest(const FString&)
{
 using namespace ProphecySwordHolsterSchedule;
 const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordAcceptedPort20261013/stagger");IFileManager::Get().MakeDirectory(*Dir,true);
 // Exercise real reservations/delegates in independent worlds, without meshes,
 // inference or physical bodies. These actors never start gameplay.
 UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);UWorld* Other=UWorld::CreateWorld(EWorldType::Editor,false);
 TArray<AProphecyAgent*> Agents;for(int I=0;I<100;++I)Agents.Add(W->SpawnActor<AProphecyAgent>());
 auto* Separate=Other->SpawnActor<AProphecyAgent>();Reserve(Separate);
 for(auto* A:Agents)Reserve(A);
 TestEqual(TEXT("One reservation per agent"),Reservations.Num(),101);
 for(auto* A:Agents)Reserve(A);
 TestEqual(TEXT("Repeated requests do not accumulate"),Reservations.Num(),101);
 TestFalse(TEXT("Admission waits for a previous-tick sample"),Ready(Agents[0]));AdvanceClock(W,LEVELTICK_All,1.f/60);
 for(int Phase=0;Phase<4;++Phase){int Due=0;for(auto* A:Agents)Due+=Ready(A);TestEqual(TEXT("25 starts per slot"),Due,25*(Phase+1));if(Phase<3)AdvanceClock(W,LEVELTICK_All,1.f/60);}
 TestEqual(TEXT("World clocks isolated"),Tick(Separate),uint64(0));
 const uint64 Before=Tick(Agents[0]);AdvanceClock(W,LEVELTICK_PauseTick,1.f/60);AdvanceClock(W,LEVELTICK_All,0);
 TestEqual(TEXT("No paused or zero-delta advancement"),Tick(Agents[0]),Before);
 for(auto* A:Agents){ProphecySwordHolsterSchedule::Remove(A);ProphecySwordHolsterSchedule::Remove(A);}ProphecySwordHolsterSchedule::Remove(Separate);
 TestTrue(TEXT("No idle scheduling work"),Worlds.IsEmpty()&&Reservations.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
 // Unsynchronized requests, early cancellation and re-entry. Allocation uses
 // the bounded admission window; target refreshes have no world-slot state.
 FRandomStream Random(74203);
 for(int Step=0;Step<300;++Step){AdvanceClock(W,LEVELTICK_All,1.f/60);auto* A=Agents[Random.RandRange(0,99)];ProphecySwordHolsterSchedule::Remove(A);Reserve(A);
  const auto R=Reservations.FindChecked(A);TestTrue(TEXT("Bounded request delay"),R.Due>Tick(A)&&R.Due-Tick(A)<=4);
  TestEqual(TEXT("Diagnostic reports admission slot"),Slot(A),int32(R.Due&3));
 }
 W->DestroyWorld(false);Other->DestroyWorld(false);
 TestTrue(TEXT("World cleanup retires reservations and delegates"),Worlds.IsEmpty()&&Reservations.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
 // Admission spreads a burst and expires stale bookings.
 FSlots Uneven;int StartCounts[4]={};
 for(int I=0;I<100;++I){++StartCounts[Uneven.BookStart(40)-40];}
 for(int N:StartCounts)TestEqual(TEXT("Start load evenly distributed"),N,25);
 TestEqual(TEXT("Expired bookings disappear even after skipped ticks"),Uneven.BookStart(100),uint64(100));

 FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabPort20261010/parity.json"))))return false;
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
 const auto& Rows=Root->GetArrayField(TEXT("rows"));
 double MaxPose=0,MaxPosition=0;int TimingMismatch=0,Completed=0;
 for(const auto& RV:Rows){const FActive Seed=OptimizationFixture(Root,RV->AsObject());
  // Delaying admission must not change any action-relative sample. Exercise
  // moving inputs with each admission phase, comparing complete trajectories.
  for(int StartPhase=0;StartPhase<4;++StartPhase)for(int Moving=0;Moving<2;++Moving){
   FActive Reference=Seed,Delayed=Seed;OptimizationPlan(Reference,false);Delayed=Reference;
   for(int WorldTick=0;WorldTick<264&&!Delayed.Status.Finished;++WorldTick){
    if(WorldTick<=StartPhase)continue;const int T=WorldTick-StartPhase;
    if(Moving){OptimizationMovingBase(Reference,Seed.Base,T/60.);Delayed.Base=Reference.Base;
     Reference.Clear=Delayed.Clear=FTransform(Seed.Clear.GetRotation(),Seed.Clear.GetLocation()+FVector(2*FMath::Sin(T*.09),0,0));}
    if(Reference.Status.ReachDone&&!Reference.Sliding){Reference.Sliding=Delayed.Sliding=true;Reference.SlideStart=Delayed.SlideStart=Reference.Status.Tick;}
    Advance(Reference,1);Advance(Delayed,1);
    TimingMismatch+=(Reference.Status.ReachDone!=Delayed.Status.ReachDone)||(Reference.Status.Returning!=Delayed.Status.Returning)||(Reference.Status.Finished!=Delayed.Status.Finished);
    for(int J:Reference.Upper){MaxPose=FMath::Max(MaxPose,Angle(Reference.Pose[J].GetRotation(),Delayed.Pose[J].GetRotation()));MaxPosition=FMath::Max(MaxPosition,FVector::Distance(Reference.Pose[J].GetLocation(),Delayed.Pose[J].GetLocation()));}
   }
   TestTrue(TEXT("Delayed motion completes"),Delayed.Status.Finished);++Completed;
  }
  // A multi-tick consume performs the same tick-relative refits as sequential
  // consumes when both receive the same base input. Duplicate reads do nothing.
  FActive Batched=Seed;OptimizationPlan(Batched,false);FActive Sequential=Batched;
  Advance(Batched,9);for(int T=0;T<9;++T)Advance(Sequential,1);
  TestEqual(TEXT("Catch-up preserves elapsed ticks"),Batched.Status.Tick,9);
  for(int J:Batched.Upper)TestTrue(TEXT("Catch-up preserves refits and pose"),Batched.Pose[J].Equals(Sequential.Pose[J],1.e-8));
  const FVector Body=Batched.Body;const FQuat Head=Batched.Head;Advance(Batched,0);
  TestTrue(TEXT("Duplicate update leaves motion untouched"),Batched.Body==Body&&Batched.Head==Head&&Batched.Status.Tick==9);
 }
 TestEqual(TEXT("Event timing from actual start"),TimingMismatch,0);TestTrue(TEXT("Pose unchanged after staggered admission"),MaxPose<.0001&&MaxPosition<1.e-8);

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
    if(Due[I]<0){if(Stagger){Due[I]=int(Slots.BookStart(Frame+1));}else Due[I]=Frame+1;}
    if(Frame<Due[I])continue;
    if(LastRead[I]<0){OptimizationPlan(C,false);LastRead[I]=Frame;++Starts;continue;}
    if(C.Status.ReachDone&&!C.Sliding){C.Sliding=true;C.SlideStart=C.Status.Tick;}
    Refits+=!C.Sliding&&(C.Status.Tick+1)%4==0;
    Advance(C,Frame-LastRead[I]);LastRead[I]=Frame;
   }
   const double Ms=(FPlatformTime::Seconds()-Start)*1000;if(!Running)break;
   ++Frames;Total+=Ms;Peak=FMath::Max(Peak,Ms);if(Starts)StartPeak=FMath::Max(StartPeak,Ms);else CyclePeak=FMath::Max(CyclePeak,Ms);MaxStarts=FMath::Max(MaxStarts,Starts);MaxRefits=FMath::Max(MaxRefits,Refits);
  }
  for(const auto& C:Crowd)TestTrue(TEXT("Entire timed crowd completes"),C.Status.Finished);
  if(Stagger&&Scenario<5){TestEqual(TEXT("Synchronized start peak count"),MaxStarts,25);TestTrue(TEXT("Synchronized refit peak count"),MaxRefits<=25);}
  if(Repeat>=0)Bench+=FString::Printf(TEXT("%d,%d,%d,%d,%.9f,%.9f,%.9f,%.9f,%d,%d\n"),Scenario,Repeat,Stagger,Frames,Total,Peak,StartPeak,CyclePeak,MaxStarts,MaxRefits);
 }
 const FString Result=FString::Printf(TEXT("cycles=%d pose_deg=%.12g position_cm=%.12g timing_mismatch=%d\n"),Completed,MaxPose,MaxPosition,TimingMismatch);
 AddInfo(Result);FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("parity.txt")));FFileHelper::SaveStringToFile(Bench,*(Dir/TEXT("benchmark.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
 return !HasAnyErrors();
}
