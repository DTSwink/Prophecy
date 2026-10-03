# Endpoint alias fallback — isolated draft

Apply `EndpointAlias.apply-patch.txt` after review. It changes only the existing endpoint cache cpp and adds one automation test to the existing physical-target tests. No active source, build or UE process was changed/run while preparing this draft.

The fallback runs before any output reset and calls the unchanged public wrapper for shared transform outputs, either transform output aliasing any of the snapshot's three transform arrays, or output names aliasing input names. It sets `bReady=false` and leaves the cache-hit observation false. Ordinary distinct-array callers retain the existing cached path.

This preserves two concrete original behaviors: aliased future/previous outputs receive interleaved additions (not two appended copies of a previously shared result), and layout capture precedes the original evaluator's output clearing when names alias the input. Input/output aliasing can intentionally produce failed/empty results on later calls; the fallback preserves that result and its input mutations instead of inventing a new success contract.

`Prophecy.NN.PhysicalTargets.EndpointCacheAliasingMatchesUncached` exhausts 47 alias combinations with cold and primed caches and three successive calls per combination. It compares return status, output names/transform scalar bits and every potentially mutated snapshot array against separate state run through the unchanged wrapper. It verifies that every alias call bypasses reuse and invalidates the previous ready answer, followed by normal miss/hit recovery. This is one focused test, not a new gameplay fixture or API.

Source-only review checks are recorded in `Verification.json`; the parent owns compilation and test execution.
