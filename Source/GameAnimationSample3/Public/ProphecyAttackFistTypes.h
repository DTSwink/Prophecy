#pragma once

#include "CoreMinimal.h"
#include "ProphecyAttackFistTypes.generated.h"

/** Levels are reference A-pose (0) to the authored closed-fist pose (1).
 * Durations are seconds for the entire transition, not units per second. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyAttackFistSettings
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fists", meta=(ClampMin="0", ClampMax="1"))
	float LeftClosedLevel = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fists", meta=(ClampMin="0", ClampMax="1"))
	float RightClosedLevel = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fists", meta=(ClampMin="0", Units="s"))
	float ClosingStartSeconds = 0.4f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Fists", meta=(ClampMin="0", Units="s"))
	float OpeningEndSeconds = 1.0f;
};
