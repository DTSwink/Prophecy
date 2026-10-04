#include "ProphecyNNModifierDebugLibrary.h"
#include "ProphecyNNModifierDebug.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "Engine/Engine.h"
#include "Engine/Canvas.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "CanvasItem.h"
#include "Debug/DebugDrawService.h"
#include "GameFramework/PlayerController.h"

namespace ProphecyNNModifierDebug
{
void FReport::Add(const TCHAR* Key,const TCHAR* Stage,const TCHAR* Label,FString Details)
{
    const uint32 Hash=FCrc::StrCrc32(Key);
    FColor Color(112+(Hash&127),112+((Hash>>8)&127),112+((Hash>>16)&127));
    // Stable colors by feature; resolve the unlikely collision within this report.
    while(Rows.ContainsByPredicate([&](const FRow& Row){return Row.Color==Color;}))
    {Color.R=uint8(96+(Color.R+37)%160);Color.G=uint8(96+(Color.G+61)%160);}
    Rows.Add({Key,Stage,Label,MoveTemp(Details),Color});
}
FString FReport::Text() const
{
    FString Out;
    for(const FRow& Row:Rows)Out+=FString::Printf(TEXT("[%s] %s: %s\n"),*Row.Stage,*Row.Label,*Row.Details);
    return Out;
}
struct FScreenReport {TWeakObjectPtr<const AProphecyAgent> Agent;uint64 Frame=0;FReport Report;};
static TArray<FScreenReport> ScreenReports;
static FDelegateHandle DrawHandle,TickHandle,CleanupHandle;
static bool ReportPaused(const UWorld* World)
{
    return World && (World->IsPaused() || World->bDebugPauseExecution);
}
static bool Visible(const FScreenReport& S,const UWorld* World)
{
    return S.Agent.IsValid() && S.Agent->GetWorld()==World &&
        (S.Frame==GFrameCounter || ReportPaused(World));
}
static void UnregisterIfEmpty()
{
    if(!ScreenReports.IsEmpty())return;
    UDebugDrawService::Unregister(DrawHandle);DrawHandle.Reset();
    FWorldDelegates::OnWorldTickStart.Remove(TickHandle);TickHandle.Reset();
    FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();
}
static void Draw(UCanvas* Canvas,APlayerController* PC)
{
    if(!Canvas || !GEngine)return;
    UWorld* World=PC?PC->GetWorld():Canvas->GetWorld();
    TArray<const FScreenReport*> Reports;
    int32 Lines=0;
    for(const auto& S:ScreenReports)if(Visible(S,World))
    {Reports.Add(&S);Lines+=S.Report.Rows.Num()+2;}
    if(Lines==0)return;
    float FontWidth=0,FontHeight=0;
    Canvas->StrLen(GEngine->GetSmallFont(),TEXT("Ag"),FontWidth,FontHeight);
    const float LineHeight=FMath::Max(16.f,FMath::CeilToFloat(FontHeight*1.15f));
    const float Height=FMath::Max(40.f,float(Canvas->SizeY)-48.f);
    const int32 PerColumn=FMath::Max(1,FMath::FloorToInt(Height/LineHeight));
    const int32 Columns=FMath::Max(1,FMath::DivideAndRoundUp(Lines,PerColumn));
    const float Width=FMath::Max(1.f,(float(Canvas->SizeX)-32.f)/Columns);
    int32 Line=0;
    auto Print=[&](const FString& Text,FColor Color)
    {
        const float X=FMath::RoundToFloat(16.f+(Line/PerColumn)*Width),Y=24.f+(Line%PerColumn)*LineHeight;
        FString Display=Text;
        float TW=0,TH=0;Canvas->StrLen(GEngine->GetSmallFont(),Text,TW,TH);
        if(TW>Width-10.f)
        {
            int32 Low=0,High=Text.Len();
            while(Low<High)
            {
                const int32 Mid=(Low+High+1)/2;
                Canvas->StrLen(GEngine->GetSmallFont(),Text.Left(Mid)+TEXT("..."),TW,TH);
                if(TW<=Width-10.f)Low=Mid;else High=Mid-1;
            }
            Display=Text.Left(Low)+TEXT("...");
        }
        // Match Print String: full-size SmallFont and opaque color with a black shadow.
        FCanvasTextItem Item(FVector2D(X,Y),FText::FromString(Display),GEngine->GetSmallFont(),FLinearColor(Color));
        Item.Scale=FVector2D(1.f,1.f);Item.EnableShadow(FLinearColor::Black);Canvas->DrawItem(Item);++Line;
    };
    for(const auto* S:Reports)
    {
        Print(S->Agent->GetName()+TEXT(" | NN modifiers (current accepted state)"),FColor::White);
        for(const auto& Row:S->Report.Rows)
            Print(FString::Printf(TEXT("[%s] %s: %s"),*Row.Stage,*Row.Label,*Row.Details),Row.Color);
        Print(TEXT("Active constraints may be idle inside their limits. Full text is on the Report pin."),FColor(180,180,180));
    }
}
static void Show(const AProphecyAgent* Agent,FReport&& Report)
{
    ScreenReports.RemoveAll([&](const FScreenReport& S){return !S.Agent.IsValid() || S.Agent==Agent;});
    ScreenReports.Add({Agent,GFrameCounter,MoveTemp(Report)});
    if(DrawHandle.IsValid())return;
    DrawHandle=UDebugDrawService::Register(TEXT("Game"),FDebugDrawDelegate::CreateStatic(&Draw));
    TickHandle=FWorldDelegates::OnWorldTickStart.AddLambda([](UWorld* World,ELevelTick,float)
    {
        ScreenReports.RemoveAll([&](const FScreenReport& S)
        {return !S.Agent.IsValid() || (S.Agent->GetWorld()==World && !ReportPaused(World) && S.Frame<GFrameCounter);});
        UnregisterIfEmpty();
    });
    CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        ScreenReports.RemoveAll([&](const FScreenReport& S){return !S.Agent.IsValid() || S.Agent->GetWorld()==World;});
        UnregisterIfEmpty();
    });
}
}

int32 UProphecyNNModifierDebugLibrary::PrintNNModifiers(AProphecyAgent* Agent,FString& Report)
{
    using namespace ProphecyNNModifierDebug;
    Report.Reset();
    if(!IsInGameThread() || !IsValid(Agent) || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown)
    {Report=TEXT("No valid agent/world.");return 0;}
    FReport R;R.Agent=Agent;bool Found=false;
    for(TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
        if(It->DescribeNNModifiers(Agent,R)){Found=true;break;}
    if(Found)
    {
        Roots(R);Lower(R);Pinning(R);Drag(R);PelvisInertia(R);HandInertia(R);
        EntryCore(R);EntryHands(R);AttackMotion(R);Armed(R);FKReturn(R);Forearm(R);
        Entry(R);ClampBlends(R);Presentation(R);Fists(R);PosePresentation(R);
    }
    else R.Add(TEXT("Unregistered"),TEXT("STATE"),TEXT("No registered NN lane"),TEXT("No inference modifier state is available for this agent."));
    R.Add(TEXT("Scope"),TEXT("SCOPE"),TEXT("Runtime snapshot"),TEXT("Reads accepted state; no history rewind, raw-output delta attribution or arbitrary Blueprint/AnimGraph tracing."));
    Report=R.Text();const int32 Count=R.Rows.Num();Show(Agent,MoveTemp(R));return Count;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyBlendClock.h"
#include "GameFramework/WorldSettings.h"
#include "GameFramework/PlayerState.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNNModifierPauseTest,"Prophecy.NN.Modifiers.PausePersistence",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FNNModifierPauseTest::RunTest(const FString&)
{
    using namespace ProphecyNNModifierDebug;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    auto* Pauser=W->SpawnActor<APlayerState>();
    for(bool EditorPause:{true,false})
    {
        FString Text;UProphecyNNModifierDebugLibrary::PrintNNModifiers(A,Text);
        ScreenReports.Last().Frame=GFrameCounter-1;
        W->bDebugPauseExecution=EditorPause;
        W->GetWorldSettings()->SetPauserPlayerState(EditorPause?nullptr:Pauser);
        TestTrue(TEXT("Both pause mechanisms recognized"),ReportPaused(W));
        for(int I=0;I<3;++I)FWorldDelegates::OnWorldTickStart.Broadcast(W,LEVELTICK_All,1.f/60);
        const auto* S=ScreenReports.FindByPredicate([&](const FScreenReport& V){return V.Agent==A;});
        TestNotNull(TEXT("Paused ticks retain report"),S);
        if(S)
        {
            TestTrue(TEXT("Old render frame remains visible while paused"),Visible(*S,W));
            TestEqual(TEXT("Pause retains the captured text"),S->Report.Text(),Text);
        }
        W->bDebugPauseExecution=false;W->GetWorldSettings()->SetPauserPlayerState(nullptr);
        FWorldDelegates::OnWorldTickStart.Broadcast(W,LEVELTICK_All,1.f/60);
        TestFalse(TEXT("Resume expires old report"),ScreenReports.ContainsByPredicate([&](const FScreenReport& V){return V.Agent==A;}));
    }
    W->DestroyWorld(false);
    TestFalse(TEXT("No draw callback after resume/cleanup"),DrawHandle.IsValid());
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNNModifierReportTest,"Prophecy.NN.Modifiers.ReportAndLifetime",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FNNModifierReportTest::RunTest(const FString&)
{
    using namespace ProphecyNNModifierDebug;
    FReport Colors;TSet<uint32> Seen;
    for(int I=0;I<256;++I)
    {
        const FString Key=FString::Printf(TEXT("feature%d"),I);
        Colors.Add(*Key,TEXT("TEST"),TEXT("Feature"),Key);
        TestFalse(TEXT("Every displayed row has a distinct color"),Seen.Contains(Colors.Rows.Last().Color.DWColor()));
        Seen.Add(Colors.Rows.Last().Color.DWColor());
    }
    TestTrue(TEXT("Full report includes final row"),Colors.Text().Contains(TEXT("feature255")));
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    // Pure observers must leave pending authored time available for the real consumer.
    A->SetFistClosedLevels(1,.5f,1);
    for(int I=0;I<3;++I)FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/5);
    FReport First;First.Agent=A;Fists(First);FReport Second;Second.Agent=A;Fists(Second);
    TestEqual(TEXT("Repeated finger read is stable"),First.Text(),Second.Text());
    TestEqual(TEXT("Read did not spend pending fist ticks"),ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::Fists),3./60.);
    FString Text;UProphecyNNModifierDebugLibrary::PrintNNModifiers(A,Text);
    UProphecyNNModifierDebugLibrary::PrintNNModifiers(A,Text);
    TestEqual(TEXT("Same-agent calls replace one screen snapshot"),ScreenReports.Num(),1);
    TestTrue(TEXT("One-shot draw registered"),DrawHandle.IsValid());
    ScreenReports[0].Frame=GFrameCounter-1;
    FWorldDelegates::OnWorldTickStart.Broadcast(W,LEVELTICK_All,1.f/60);
    TestTrue(TEXT("Report removed next tick"),ScreenReports.IsEmpty());
    TestFalse(TEXT("No idle draw callback"),DrawHandle.IsValid());
    TestFalse(TEXT("No idle tick callback"),TickHandle.IsValid());
    UProphecyNNModifierDebugLibrary::PrintNNModifiers(A,Text);
    A->ReleaseAttackFists();W->DestroyWorld(false);
    TestTrue(TEXT("World cleanup removes snapshot and callbacks"),ScreenReports.IsEmpty()&&!DrawHandle.IsValid()&&!TickHandle.IsValid());
    return !HasAnyErrors();
}
#endif
