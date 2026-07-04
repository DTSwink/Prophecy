#include "ProphecySkinnedMeshBlueprintLibrary.h"

#include "Components/SkinnedMeshComponent.h"

void UProphecySkinnedMeshBlueprintLibrary::GetBoneParentAndChildren(
	USkinnedMeshComponent* SkinnedComp,
	FName BoneName,
	FName& OutParent,
	TArray<FName>& OutChildren,
	bool bRecursive)
{
	OutParent = NAME_None;
	OutChildren.Reset();

	if (!SkinnedComp || BoneName.IsNone() || SkinnedComp->GetBoneIndex(BoneName) == INDEX_NONE)
	{
		return;
	}

	OutParent = SkinnedComp->GetParentBone(BoneName);

	const int32 NumBones = SkinnedComp->GetNumBones();
	TMap<FName, TArray<FName>> ChildrenByParent;
	ChildrenByParent.Reserve(NumBones);

	for (int32 BoneIndex = 0; BoneIndex < NumBones; ++BoneIndex)
	{
		const FName ChildBone = SkinnedComp->GetBoneName(BoneIndex);
		const FName ParentBone = SkinnedComp->GetParentBone(ChildBone);
		if (!ParentBone.IsNone())
		{
			ChildrenByParent.FindOrAdd(ParentBone).Add(ChildBone);
		}
	}

	const TArray<FName>* DirectChildren = ChildrenByParent.Find(BoneName);
	if (!DirectChildren)
	{
		return;
	}

	if (!bRecursive)
	{
		OutChildren.Append(*DirectChildren);
		return;
	}

	TArray<FName> PendingChildren = *DirectChildren;
	TSet<FName> VisitedChildren;
	VisitedChildren.Reserve(NumBones);

	int32 PendingIndex = 0;
	while (PendingIndex < PendingChildren.Num())
	{
		const FName ChildBone = PendingChildren[PendingIndex++];
		if (VisitedChildren.Contains(ChildBone))
		{
			continue;
		}

		VisitedChildren.Add(ChildBone);
		OutChildren.Add(ChildBone);

		if (const TArray<FName>* GrandChildren = ChildrenByParent.Find(ChildBone))
		{
			for (const FName GrandChildBone : *GrandChildren)
			{
				PendingChildren.Add(GrandChildBone);
			}
		}
	}
}
