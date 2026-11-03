#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "BonePose.h"
#include "BirdTypes.h"
#include "BirdAnimInstance.generated.h"

class UAnimSequence;

/** Worker-thread side of UBirdAnimInstance: samples the five clips, blends them, then adds beak + head look. */
struct FBirdAnimProxy : public FAnimInstanceProxy
{
	FBirdAnimProxy() = default;
	explicit FBirdAnimProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}

	virtual void Initialize(UAnimInstance* Instance) override;
	virtual void PreUpdate(UAnimInstance* Instance, float DeltaSeconds) override;
	virtual bool Evaluate(FPoseContext& Output) override;

private:
	const UAnimSequence* Clips[5] = { nullptr, nullptr, nullptr, nullptr, nullptr };	// Perch, Walk, Glide, Flap, Hover
	FBirdAnimParams P;
	// mesh bone indices (INDEX_NONE when the bone does not exist)
	int32 Jaw = INDEX_NONE, Head = INDEX_NONE, Neck2 = INDEX_NONE, Neck3 = INDEX_NONE;
	int32 Neck1 = INDEX_NONE, Spine1 = INDEX_NONE, Spine2 = INDEX_NONE, Tail = INDEX_NONE;
	TArray<FQuat> RefCS;	// reference-pose component-space rotations (mesh bone index)
	TArray<int32> RefParent;

	// Perch and Glide are single poses: decompressed once and copied afterwards (re-sampled when the clip or the required
	// bones change, e.g. a LOD switch)
	struct FStaticPose { const UAnimSequence* Seq = nullptr; uint16 Serial = 0; int32 NumBones = -1; TArray<FTransform> Bones; };
	FStaticPose StaticPoses[2];
	void SampleStatic(int32 Slot, const UAnimSequence* Seq, FPoseContext& Ctx);
	void Sample(const UAnimSequence* Seq, float Phase01, FPoseContext& Ctx) const;
	void BlendInto(FPoseContext& A, FPoseContext& B, float AlphaB);
	FQuat CSRotation(const FCompactPose& Pose, FCompactPoseBoneIndex Bone) const;
	void RotateCS(FCompactPose& Pose, int32 MeshBone, const FVector& RefAxisCS, float Radians) const;
	/** Applies a rotation given in component space (about the bone's joint) to a bone and its children. */
	void ApplyCS(FCompactPose& Pose, int32 MeshBone, const FQuat& DeltaCS) const;
	FQuat CurrentCS(const FCompactPose& Pose, int32 MeshBone) const;
};

/**
 * Native, graph-less anim instance for the ambient birds. Clips: Perch (static, wings folded), Walk (1 s cycle = 2 steps),
 * Glide (static, wings spread), Flap (1 s cycle), Hover (1 s braking / take-off cycle). Blend weights and phases come from
 * ABird every frame (SetParams). Beak (jaw bone) and head look are applied procedurally on top.
 */
UCLASS(Transient, NotBlueprintable)
class PROPHECYAMBIENT_API UBirdAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	void SetClips(UAnimSequence* Perch, UAnimSequence* Walk, UAnimSequence* Glide, UAnimSequence* Flap, UAnimSequence* Hover);
	void SetParams(const FBirdAnimParams& InParams) { Params = InParams; }
	const FBirdAnimParams& GetParams() const { return Params; }

	UPROPERTY(Transient) TArray<TObjectPtr<UAnimSequence>> Clips;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override { return new FBirdAnimProxy(this); }
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override { delete InProxy; }

private:
	FBirdAnimParams Params;
	friend struct FBirdAnimProxy;
};
