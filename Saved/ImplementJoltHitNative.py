from pathlib import Path
import subprocess
root=Path('Intermediate/JoltMigration/Upstream')
def edit(file, old, new):
    p=root/file
    s=p.read_text()
    assert s.count(old)==1,(file,old[:80],s.count(old))
    p.write_text(s.replace(old,new),newline='\n')
# A separate solved-impulse observer avoids pre-solve contact callbacks entirely.
edit('Jolt/Physics/Collision/ContactListener.h','class ContactListener\n{', '''/// Prophecy opt-in observer of actual rigid contact solver impulses. Worker-thread,
/// read-only callback; no body locking, UObject access or physics mutations allowed.
/// Normal points from body 1 to body 2; positive impulse acts on body 2.
class ContactImpulseListener
{
public:
    virtual ~ContactImpulseListener() = default;
    virtual bool WantsContactImpulse(const Body &inBody1, const Body &inBody2) const = 0;
    virtual void OnContactImpulse(const Body &inBody1, const Body &inBody2,
        const SubShapeID &inShape1, const SubShapeID &inShape2,
        RVec3Arg inPoint1, RVec3Arg inPoint2, Vec3Arg inNormal, float inImpulse) = 0;
};

class ContactListener
{''')
edit('Jolt/Physics/Constraints/ContactConstraintManager.h','struct PhysicsSettings;', 'struct PhysicsSettings;\nclass ContactImpulseListener;')
edit('Jolt/Physics/Constraints/ContactConstraintManager.h','\t/// Callback function to combine the restitution or friction of two bodies','''    void SetContactImpulseListener(ContactImpulseListener *inListener) { mContactImpulseListener = inListener; }
    ContactImpulseListener *GetContactImpulseListener() const { return mContactImpulseListener; }

\t/// Callback function to combine the restitution or friction of two bodies''')
p=root/'Jolt/Physics/Constraints/ContactConstraintManager.h'
s=p.read_text(); anchor=next(l for l in s.splitlines() if 'mContactListener = nullptr' in l)
edit('Jolt/Physics/Constraints/ContactConstraintManager.h',anchor,anchor+'\n    ContactImpulseListener *mContactImpulseListener = nullptr;')
edit('Jolt/Physics/PhysicsSystem.h','\t/// Set the soft body contact listener','\t/// Set the soft body contact listener') if False else None
p=root/'Jolt/Physics/PhysicsSystem.h';s=p.read_text();anchor=next(l for l in s.splitlines() if 'GetContactListener() const' in l)
edit('Jolt/Physics/PhysicsSystem.h',anchor,anchor+'\n    void SetContactImpulseListener(ContactImpulseListener *inListener) { mContactManager.SetContactImpulseListener(inListener); }')
anchor='\t\ttable[(int)constraint.mBody1->GetMotionType()][(int)constraint.mBody2->GetMotionType()](constraint, *mWriteCache);'
edit('Jolt/Physics/Constraints/ContactConstraintManager.cpp',anchor,anchor+'''
        if (mContactImpulseListener != nullptr && mContactImpulseListener->WantsContactImpulse(*constraint.mBody1, *constraint.mBody2))
        {
            const auto *entry = mWriteCache->FromHandle(constraint.mCachedManifoldHandle);
            const auto &cached = entry->GetValue();
            float impulse = 0.0f;
            Vec3 point1 = Vec3::sZero(), point2 = Vec3::sZero();
            for (uint32 i = 0; i < constraint.mNumContactPoints; ++i)
            {
                const auto &point = cached.mContactPoints[i];
                const float weight = max(0.0f, point.mNonPenetrationLambda);
                impulse += weight;
                point1 += weight * Vec3::sLoadFloat3Unsafe(point.mPosition1);
                point2 += weight * Vec3::sLoadFloat3Unsafe(point.mPosition2);
            }
            if (impulse > 0.0f)
            {
                const auto &key = entry->GetKey();
                mContactImpulseListener->OnContactImpulse(*constraint.mBody1, *constraint.mBody2,
                    key.GetSubShapeID1(), key.GetSubShapeID2(),
                    constraint.mBody1->GetCenterOfMassTransform() * (point1 / impulse),
                    constraint.mBody2->GetCenterOfMassTransform() * (point2 / impulse),
                    constraint.GetWorldSpaceNormal(), impulse);
            }
        }''')
# CCD uses its own one-contact solver; publish its actual lambda as well.
p=root/'Jolt/Physics/PhysicsUpdateContext.h';s=p.read_text();anchor=next(l for l in s.splitlines() if 'SubShapeID' in l and 'mSubShapeID2;' in l)
edit('Jolt/Physics/PhysicsUpdateContext.h',anchor,'            SubShapeID mSubShapeID1;\n'+anchor)
edit('Jolt/Physics/PhysicsSystem.cpp','\t\t\tmanifold.mSubShapeID1 = cast_shape_result.mSubShapeID1;', '\t\t\tccd_body.mSubShapeID1 = cast_shape_result.mSubShapeID1;\n\t\t\tmanifold.mSubShapeID1 = cast_shape_result.mSubShapeID1;')
for f in ['Jolt/Physics/PhysicsSystem.cpp','Jolt/Physics/PhysicsSystem.h']:
    p=root/f;s=p.read_text();anchor=next(l for l in s.splitlines() if 'sSolveCCDContact(Body &' in l)
    new=anchor.replace('void PhysicsSystem::','float PhysicsSystem::').replace('static void','static float')
    edit(f,anchor,new)
edit('Jolt/Physics/PhysicsSystem.cpp','\n}\n\nvoid PhysicsSystem::JobResolveCCDContacts', '\n    return contact_constraint.GetTotalLambda();\n}\n\nvoid PhysicsSystem::JobResolveCCDContacts')
edit('Jolt/Physics/PhysicsSystem.cpp','using DispatchFunc = void (*)(Body &, float, Mat44Arg, Vec3Arg, Body &, Vec3Arg, Vec3Arg, float, Vec3Arg, const ContactSettings &);','using DispatchFunc = float (*)(Body &, float, Mat44Arg, Vec3Arg, Body &, Vec3Arg, Vec3Arg, float, Vec3Arg, const ContactSettings &);')
anchor='\t\t\t\t\t\ttable[(int)body2.GetMotionType()](body1, inv_m1, inv_i1, r1_plus_u, body2, r2, ccd_body->mContactNormal, normal_velocity_bias, friction_direction, contact_settings);'
edit('Jolt/Physics/PhysicsSystem.cpp',anchor,anchor.replace('table[','const float impulse = table[')+'''
                        auto *listener = mContactManager.GetContactImpulseListener();
                        if (listener != nullptr && impulse > 0.0f && listener->WantsContactImpulse(body1, body2))
                            listener->OnContactImpulse(body1, body2, ccd_body->mSubShapeID1, ccd_body->mSubShapeID2,
                                ccd_body->mContactPointOn2, ccd_body->mContactPointOn2, ccd_body->mContactNormal, impulse);''')
patch=subprocess.check_output(['git','-C',str(root),'diff','--no-ext-diff','--binary'])
Path('Tools/Jolt/Patches/NumericalSafety.patch').write_bytes(patch)
print('Updated reviewed native patch, including solved discrete and CCD contact impulses.')
