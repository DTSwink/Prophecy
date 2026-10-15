// Isolated experiment only. A tagged body opts out of response to separated
// manifolds; re-evaluate persisted contacts so real contact becomes solid again.
struct RigContactFilter : ContactListener
{
    uint64 added=0,persisted=0,suppressed=0,solid=0;
    bool enabled=true;
    static constexpr uint64 Tag=0x5249473135ULL;
    void Apply(const Body& a,const Body& b,const ContactManifold& m,ContactSettings& s)
    {
        if(!enabled || (a.GetUserData()!=Tag && b.GetUserData()!=Tag))return;
        if(m.mPenetrationDepth<0){s.mIsSensor=true;++suppressed;}
        else ++solid; // Leave the settings initialized by Jolt untouched.
    }
    void OnContactAdded(const Body& a,const Body& b,const ContactManifold& m,ContactSettings& s) override
    {++added;Apply(a,b,m,s);}
    void OnContactPersisted(const Body& a,const Body& b,const ContactManifold& m,ContactSettings& s) override
    {++persisted;Apply(a,b,m,s);}
};

static int RigContactSelfTest()
{
    using Row=std::array<double,4>;
    std::vector<Row> samples[4];uint64 taggedSuppressed=0,taggedSolid=0,taggedPersisted=0;
    for(int mode=0;mode<4;++mode){
        Layers layers;BroadFilter broad;PairFilter pair;PhysicsSystem physics;
        physics.Init(16,0,64,64,layers,broad,pair);physics.SetGravity(Vec3(0,0,-9.81f));
        TempAllocatorImpl alloc(8*1024*1024);JobSystemSingleThreaded jobs(128);
        RigContactFilter filter;if(mode==1||mode==3)physics.SetContactListener(&filter);
        if(mode==2){auto ps=physics.GetPhysicsSettings();ps.mSpeculativeContactDistance=0;physics.SetPhysicsSettings(ps);}
        auto& bi=physics.GetBodyInterface();
        BodyCreationSettings floor(new BoxShape(Vec3(10,10,.1f),0),RVec3(0,0,-.1),Quat::sIdentity(),EMotionType::Static,0);
        floor.mRestitution=0;bi.CreateAndAddBody(floor,EActivation::DontActivate);
        Body* body[2];
        for(int i=0;i<2;++i){
            BodyCreationSettings s(new SphereShape(.1f),RVec3(i*2-1,0,.112),Quat::sIdentity(),EMotionType::Dynamic,1);
            s.mUserData=i==0?RigContactFilter::Tag:0;s.mLinearVelocity=Vec3(0,0,-1);
            s.mRestitution=.3f;s.mLinearDamping=0;s.mAngularDamping=0;s.mAllowSleeping=false;
            body[i]=bi.CreateBody(s);bi.AddBody(body[i]->GetID(),EActivation::Activate);
        }
        for(int tick=0;tick<120;++tick){
            if(mode==3&&tick==12)filter.enabled=false;
            physics.Update(1.f/240,1,&alloc,&jobs);
            samples[mode].push_back({body[0]->GetPosition().GetZ(),body[0]->GetLinearVelocity().GetZ(),body[1]->GetPosition().GetZ(),body[1]->GetLinearVelocity().GetZ()});
        }
        if(mode==1){taggedSuppressed=filter.suppressed;taggedSolid=filter.solid;taggedPersisted=filter.persisted;}
        physics.SetContactListener(nullptr);
    }
    double untouched=0,reference=0,effect=0,minHeight=1;
    for(size_t i=0;i<samples[0].size();++i){
        for(int c=0;c<2;++c){
            untouched=std::max(untouched,std::abs(samples[1][i][c+2]-samples[0][i][c+2]));
            reference=std::max(reference,std::abs(samples[1][i][c]-samples[2][i][c]));
            effect=std::max(effect,std::abs(samples[1][i][c]-samples[0][i][c]));
        }
        minHeight=std::min(minHeight,std::min(samples[1][i][0],samples[3][i][0]));
    }
    const bool pass=untouched==0&&reference<1e-6&&effect>1e-3&&taggedSuppressed>0&&taggedSolid>0&&taggedPersisted>0&&minHeight>.09;
    std::cout<<"{\"passed\":"<<(pass?"true":"false")<<",\"unmarked_max_error\":"<<untouched
        <<",\"tagged_vs_global_zero_max_error\":"<<reference<<",\"tagged_vs_default_max_difference\":"<<effect
        <<",\"suppressed_contacts\":"<<taggedSuppressed<<",\"solid_contacts\":"<<taggedSolid
        <<",\"persisted_callbacks\":"<<taggedPersisted<<",\"minimum_center_height_m\":"<<minHeight<<"}"<<std::endl;
    return pass?0:7;
}
