# Head-ray fixture repair

`HeadRayOcclusion.merge.patch` applies to the promoted helper and MultiJolt report. It is source-only; no active files, builds or Unreal launches were changed here.

The first DuringPhysics two-agent smoke failed because its chosen ray genuinely hit `neck_01` about 2.0216 cm before the expected head surface. All query body X/R checks had already passed. That result diagnoses a fixture occlusion assumption, not stale query data.

The repair independently selects a candidate using the current native geometry of all 22 bodies at their completed bone poses. It tries both directions of each of three head-local axes. A different body containing the ray start counts as an immediate zero-distance occluder (`FImplicitObject::Overlap`, UE5.7 `Chaos/ImplicitObject.h:372`); otherwise native ray intersections at or before the head entry reject that candidate. Equal-distance contacts within the existing 0.02 cm tolerance are treated as ambiguous and also rejected. Invalid native intersection data returns an error. Candidate selection never performs a UE scene query.

Once a candidate independently predicts the head first, exactly one strict UE world trace is made. A failure returns immediately; no later direction can hide it. The disjoint-previous-AABB edge probe uses the same occlusion check in both segment directions. Its clearance, geometry, identity and impact tolerances remain unchanged.

The helper includes one pure native-geometry automation test with 22 bodies: a nearer neck rejects one direction, the reverse direction predicts the head entry, and a body containing the ray start rejects the reverse candidate at time zero. It does not require an editor world or execute scene queries. Root must compile and run it, then rerun the actual moving smoke and crowd cases.

The summary field is renamed to `motion_edge_evidence_present`; it still means at least one independently qualifying ray anywhere in the measured cohort. The separate distinct-agent count remains available. No all-agent motion-edge coverage is implied or newly required.
